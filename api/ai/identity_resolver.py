"""Identity Resolver and Matching Engine for Project Amaanat.

Follows docs/BLUEPRINT.md section 9.1 and AGENTS.md:
- Multilingual Normalisation: NFKC Unicode, honorific stripping, Urdu script transliteration,
  Pakistani variant normalization (Mohammad/Muhammad/Mohd), and Roman-Urdu phonetic keys.
- Fuzzy match scoring via RapidFuzz (Jaro-Winkler + Token Set ratio).
- Outcome Classification: EXACT, PROBABLE, CONFLICT, NO_RECORD.
- Asymmetric safety: Ties and conflicts strictly escalate to HUMAN; NEVER auto-merge.
- CNIC format and transposition detection.
- Blocking keys for duplicate detection and side-by-side comparison payloads.
"""
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple
from rapidfuzz.distance import JaroWinkler
from rapidfuzz import fuzz

from api.decision_engine.scorers import IdentityScorer


HONORIFICS = {
    "SYED", "SYEDA", "MST", "MST.", "BIBI", "HAJI", "CHAUDHRY", "MALIK",
    "SARDAR", "RAJA", "BEGUM", "KHAN", "MIR", "SHAIKH", "SHEIKH", "PIR",
    "AL-HAJ", "MUHTARAMA", "JANAB"
}

NAME_CANONICAL_MAP = {
    "MOHAMMAD": "MUHAMMAD",
    "MOHAMED": "MUHAMMAD",
    "MUHAMMED": "MUHAMMAD",
    "MOHD": "MUHAMMAD",
    "MD": "MUHAMMAD",
    "MD.": "MUHAMMAD",
    "M.": "MUHAMMAD",
    "AHMED": "AHMAD",
    "USMAN": "UTHMAN",
    "OTHMAN": "UTHMAN",
    "HUSSAIN": "HUSAIN",
    "HOSSEIN": "HUSAIN",
    "QURESHI": "QURAISHI",
    "SIDDIQUE": "SIDDIQUI",
}

URDU_TO_ROMAN_MAP = {
    "ا": "a", "آ": "aa", "ب": "b", "پ": "p", "ت": "t", "ٹ": "t",
    "ث": "s", "ج": "j", "چ": "ch", "ح": "h", "خ": "kh", "د": "d",
    "ڈ": "d", "ذ": "z", "ر": "r", "ڑ": "r", "ز": "z", "ژ": "zh",
    "س": "s", "ش": "sh", "ص": "s", "ض": "z", "ط": "t", "ظ": "z",
    "ع": "a", "غ": "gh", "ف": "f", "ق": "q", "ک": "k", "گ": "g",
    "ل": "l", "م": "m", "ن": "n", "ں": "n", "و": "o", "ہ": "h",
    "ھ": "h", "ء": "", "ی": "y", "ے": "e"
}


def normalize_urdu_to_roman(text: str) -> str:
    """Converts Urdu-script characters into Roman Urdu text."""
    res = []
    for char in text:
        if char in URDU_TO_ROMAN_MAP:
            res.append(URDU_TO_ROMAN_MAP[char])
        else:
            res.append(char)
    return "".join(res)


def roman_urdu_phonetic_key(word: str) -> str:
    """Computes a phonetic key for Roman Urdu names, collapsing phonetic ambiguities."""
    w = word.upper()
    # Normalize common digraphs
    w = re.sub(r"KH|Q", "K", w)
    w = re.sub(r"GH", "G", w)
    w = re.sub(r"SH", "S", w)
    w = re.sub(r"CH", "C", w)
    w = re.sub(r"TH", "T", w)
    w = re.sub(r"PH", "F", w)
    w = re.sub(r"DH", "D", w)
    w = re.sub(r"ZH|Z", "S", w)
    w = re.sub(r"[AEIOUY]", "", w)  # Remove interior vowels for phonetic skeleton
    return w


def extract_raw_clean_tokens(name: str) -> List[str]:
    """Cleans punctuation, transliterates Urdu to Roman, and strips honorifics without variant mapping."""
    if not name:
        return []
    n = unicodedata.normalize("NFKC", name).strip()
    if any("\u0600" <= c <= "\u06FF" for c in n):
        n = normalize_urdu_to_roman(n)
    n = re.sub(r"[^A-Za-z\s]", " ", n).upper()
    tokens = [t.strip() for t in n.split() if t.strip()]
    return [t for t in tokens if t not in HONORIFICS]


def normalize_pakistani_name(name: str) -> Tuple[str, List[str]]:
    """Cleans, strips honorifics, transliterates Urdu, maps variants, and normalises name."""
    if not name:
        return "", []

    # 1. Unicode NFKC
    n = unicodedata.normalize("NFKC", name).strip()

    # 2. Transliterate if Urdu script present
    if any("\u0600" <= c <= "\u06FF" for c in n):
        n = normalize_urdu_to_roman(n)

    # 3. Clean punctuation and uppercase
    n = re.sub(r"[^A-Za-z\s]", " ", n).upper()
    tokens = [t.strip() for t in n.split() if t.strip()]

    # 4. Strip leading/trailing honorifics
    filtered = []
    for t in tokens:
        if t not in HONORIFICS:
            # Map canonical variants
            filtered.append(NAME_CANONICAL_MAP.get(t, t))

    cleaned_str = " ".join(filtered) if filtered else n
    return cleaned_str, filtered


def validate_and_check_cnic(
    claimant_cnic: str,
    nadra_cnic: Optional[str] = None
) -> Tuple[bool, bool, Optional[str]]:
    """Validates 13-digit Pakistani CNIC format and checks for digit transpositions.
    
    Returns:
        (is_valid_format, is_transposition_detected, details_msg)
    """
    clean_c = re.sub(r"[^0-9]", "", claimant_cnic or "")
    if len(clean_c) != 13:
        return False, False, f"CNIC format invalid: Expected 13 digits, found {len(clean_c)}"

    if not nadra_cnic:
        return True, False, "CNIC format valid"

    clean_n = re.sub(r"[^0-9]", "", nadra_cnic)
    if clean_c == clean_n:
        return True, False, "Exact CNIC match"

    # Transposition check (swap of two adjacent digits)
    if len(clean_c) == len(clean_n):
        diff_indices = [i for i in range(len(clean_c)) if clean_c[i] != clean_n[i]]
        if len(diff_indices) == 2:
            i, j = diff_indices
            if abs(i - j) == 1 and clean_c[i] == clean_n[j] and clean_c[j] == clean_n[i]:
                return True, True, f"CNIC transposition detected between positions {i+1} and {j+1} ({clean_c[i]}{clean_c[j]} vs {clean_n[i]}{clean_n[j]})"

    return True, False, "CNIC mismatch between claimant and registry"


class RealIdentityResolver(IdentityScorer):
    """Production Identity Resolver replacing StubIdentityScorer.
    
    Abides by Blueprint 9.1:
    - Calculates hybrid similarity: RapidFuzz Jaro-Winkler + Token-Set ratio + Phonetic key.
    - Evaluates father name and DOB consistency.
    - Matches against versioned threshold bounds (default Exact >= 0.92, Probable >= 0.75).
    """

    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        cfg = thresholds or {}
        self.exact_threshold = float(cfg.get("identity_exact_min", 0.92))
        self.probable_threshold = float(cfg.get("identity_probable_min", 0.75))

    def score(
        self,
        person_data: Dict[str, Any],
        nadra_record: Optional[Dict[str, Any]]
    ) -> Tuple[float, Dict[str, Any]]:
        """Calculates c_identity and full verification telemetry for a case."""
        if not nadra_record:
            return 0.40, {
                "scorer": "REAL_AI_IDENTITY_RESOLVER",
                "match_type": "NO_RECORD",
                "identity_match_exact": False,
                "notes": "No matching record returned from civil registry"
            }

        claimant_raw_name = person_data.get("canonical_name") or person_data.get("name") or ""
        nadra_raw_name = nadra_record.get("name") or ""

        # 1. Raw cleaned tokens (without dictionary substitution)
        c_raw_tokens = extract_raw_clean_tokens(claimant_raw_name)
        n_raw_tokens = extract_raw_clean_tokens(nadra_raw_name)
        c_raw_str = " ".join(c_raw_tokens)
        n_raw_str = " ".join(n_raw_tokens)

        # 2. Canonical tokens (variant mapped: e.g. MOHD -> MUHAMMAD, MUHAMMED -> MUHAMMAD)
        claimant_norm, c_tokens = normalize_pakistani_name(claimant_raw_name)
        nadra_norm, n_tokens = normalize_pakistani_name(nadra_raw_name)

        # 3. Direct lexical similarity metrics on un-mapped tokens
        jw_sim = JaroWinkler.similarity(c_raw_str, n_raw_str)
        token_sim = fuzz.token_set_ratio(c_raw_str, n_raw_str) / 100.0
        raw_similarity = max(jw_sim, token_sim)

        # 4. Phonetic & Canonical equivalence
        c_phonetics = [roman_urdu_phonetic_key(t) for t in c_tokens]
        n_phonetics = [roman_urdu_phonetic_key(t) for t in n_tokens]
        phonetic_match = bool(c_phonetics and c_phonetics == n_phonetics)
        canonical_match = bool(claimant_norm and claimant_norm == nadra_norm)

        # 5. Combined composite name similarity
        if c_raw_str == n_raw_str:
            name_similarity = 1.0
        elif raw_similarity >= self.exact_threshold:
            # High lexical similarity (e.g. Muhammad vs Mohammad, JW=0.925 >= 0.92)
            name_similarity = raw_similarity
        elif canonical_match or phonetic_match:
            # Recognized Pakistani variant/abbreviation (e.g. Muhammed vs Mohd, Md vs Muhammad)
            # Evaluates into the PROBABLE band [0.75, 0.92) per Blueprint 9.1
            name_similarity = 0.85
        else:
            name_similarity = raw_similarity

        # 3. CNIC validation & transposition detection
        c_cnic = person_data.get("cnic") or ""
        n_cnic = nadra_record.get("cnic") or ""
        valid_fmt, is_transposed, cnic_msg = validate_and_check_cnic(c_cnic, n_cnic)

        # 4. Secondary checks: Father Name and DOB
        father_match = True
        c_father = person_data.get("father_name") or ""
        n_father = nadra_record.get("father_name") or ""
        if c_father and n_father:
            c_f_norm, _ = normalize_pakistani_name(c_father)
            n_f_norm, _ = normalize_pakistani_name(n_father)
            f_sim = max(JaroWinkler.similarity(c_f_norm, n_f_norm), fuzz.token_set_ratio(c_f_norm, n_f_norm) / 100.0)
            if f_sim < 0.70:
                father_match = False

        dob_match = True
        c_dob = person_data.get("dob") or ""
        n_dob = nadra_record.get("dob") or ""
        if c_dob and n_dob and c_dob != n_dob:
            dob_match = False

        # 5. Determine Outcome
        clean_c_cnic = re.sub(r"[^0-9]", "", c_cnic)
        clean_n_cnic = re.sub(r"[^0-9]", "", n_cnic)
        cnic_matches = (clean_c_cnic == clean_n_cnic)

        if not cnic_matches:
            if is_transposed:
                match_type = "PROBABLE"
                c_identity = 0.75
                notes = f"CNIC digit transposition detected: {cnic_msg}"
            else:
                match_type = "CONFLICT"
                c_identity = 0.30
                notes = "CNIC mismatch between claimant and civil registry"
        elif name_similarity >= self.exact_threshold and father_match and dob_match:
            match_type = "EXACT"
            c_identity = 0.99
            notes = "Exact identity match verified with registry"
        elif name_similarity >= self.probable_threshold:
            match_type = "PROBABLE"
            c_identity = round(0.80 + 0.15 * name_similarity, 3)
            notes = f"Probable name variation detected (similarity={name_similarity:.2f})"
        else:
            match_type = "CONFLICT"
            c_identity = 0.40
            notes = f"Significant name disparity with registry (similarity={name_similarity:.2f})"

        return c_identity, {
            "scorer": "REAL_AI_IDENTITY_RESOLVER",
            "match_type": match_type,
            "identity_match_exact": (match_type == "EXACT"),
            "name_similarity": round(name_similarity, 4),
            "jaro_winkler": round(jw_sim, 4),
            "token_set_ratio": round(token_sim, 4),
            "phonetic_match": phonetic_match,
            "father_name_consistent": father_match,
            "dob_consistent": dob_match,
            "is_transposition_detected": is_transposed,
            "notes": notes,
        }


def generate_duplicate_blocking_keys(
    person_data: Dict[str, Any],
    step_data: Dict[str, Any]
) -> Dict[str, str]:
    """Generates deterministic blocking keys for fast duplicate claim detection."""
    import hashlib
    clean_cnic = re.sub(r"[^0-9]", "", person_data.get("cnic") or "")
    cnic_hash = hashlib.sha256(clean_cnic.encode("utf-8")).hexdigest() if clean_cnic else ""

    phone = re.sub(r"[^0-9]", "", step_data.get("phone") or "")
    phone_hash = hashlib.sha256(phone.encode("utf-8")).hexdigest() if phone else ""

    account = (step_data.get("account_number") or step_data.get("iban") or "").strip().upper()

    name_norm, _ = normalize_pakistani_name(person_data.get("name") or "")
    father_norm, _ = normalize_pakistani_name(person_data.get("father_name") or "")
    dob = (person_data.get("dob") or "").strip()
    demographic_key = hashlib.sha256(f"{name_norm}|{father_norm}|{dob}".encode("utf-8")).hexdigest()

    return {
        "cnic_hash": cnic_hash,
        "phone_hash": phone_hash,
        "account_number": account,
        "demographic_key": demographic_key,
    }
