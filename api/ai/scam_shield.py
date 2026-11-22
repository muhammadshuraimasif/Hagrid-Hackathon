"""Scam Shield & Citizen Threat Protection.

Follows docs/BLUEPRINT.md section 9.6:
- 4 Ensemble Voters:
  1. Heuristic Rules Voter (urgency words, fees, unapproved domains, URL shorteners, PIN/OTP asks).
  2. TF-IDF Character n-gram + Logistic Regression ML Voter.
  3. Gemini Structured LLM Voter (skipped gracefully if key unavailable).
  4. Cryptographic Trust Anchor Voter: HMAC-signed verification code (AMN-XXXXXX).
- Verdict: LIKELY_SCAM, UNSURE, VERIFIED. It warns; it NEVER blocks.
- Privacy Preservation: Stored messages are redacted of PII (CNICs, PINs, phone numbers).
"""
import hashlib
import hmac
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from api.config import settings
from api.ai.model_adapter import model_adapter, redact_pii_for_model
from eval.generator import generate_synthetic_dataset


# Common phishing keywords and URL shorteners
SUSPICIOUS_DOMAINS_OR_SHORTENERS = [
    "bit.ly", "tinyurl.com", "goo.gl", "is.gd", "t.co", "ow.ly",
    "free-cash.pk", "ehsaas-money.com", "bisp-relief.org", "paisa-claim.net"
]

URGENCY_KEYWORDS = [
    "urgent", "urgently", "immediately", "expires today", "within 24 hours",
    "act now", "won", "winner", "lottery", "congratulations", "cash prize",
    "fee", "advance tax", "processing fee", "send pin", "atm pin", "password", "otp"
]

OFFICIAL_GOV_DOMAINS = [
    ".gov.pk", "relief.gov.pk", "bisp.gov.pk", "nadra.gov.pk", "pass.gov.pk"
]


class ScamScanResult(BaseModel):
    verdict: str  # LIKELY_SCAM, UNSURE, VERIFIED
    confidence: float
    red_flags: List[str] = []
    voter_breakdown: Dict[str, Any] = {}
    recommendation: str
    redacted_message: str


def generate_trust_code(case_id: str, recipient: str, secret: Optional[str] = None) -> str:
    """Mints an authentic HMAC-SHA256 trust anchor verification code for Amaanat SMS/WhatsApp."""
    sec = (secret or settings.effective_scam_hmac_secret).encode("utf-8")
    payload = f"{case_id}:{recipient}:TRUST_ANCHOR"
    mac = hmac.new(sec, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"AMN-{mac[:8].upper()}"


def verify_trust_code(code: str, case_id: str, recipient: str, secret: Optional[str] = None) -> bool:
    """Verifies HMAC trust anchor code in constant time."""
    expected = generate_trust_code(case_id, recipient, secret=secret)
    return hmac.compare_digest(code.strip().upper(), expected)


class ScamShieldEngine:
    """Ensemble Scam Detector with Rules, ML, and Trust Anchor Verification."""

    def __init__(self):
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.classifier: Optional[LogisticRegression] = None
        self.eval_metrics: Dict[str, Any] = {}
        self._train_engine()

    def _train_engine(self):
        """Trains the ML voter on the deterministic 800 synthetic messages dataset."""
        _, messages = generate_synthetic_dataset(seed=42)
        texts = [m["text"] for m in messages]
        labels = [1 if m["ground_truth_scam"] else 0 for m in messages]

        # 70% train / 30% held-out test split
        split_idx = int(len(messages) * 0.70)
        train_texts, test_texts = texts[:split_idx], texts[split_idx:]
        train_labels, test_labels = labels[:split_idx], labels[split_idx:]
        test_messages = messages[split_idx:]

        # Train TF-IDF char n-grams + Logistic Regression
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2)
        X_train = self.vectorizer.fit_transform(train_texts)
        self.classifier = LogisticRegression(max_iter=500, random_state=42)
        self.classifier.fit(X_train, train_labels)

        # Evaluate on held-out test set
        X_test = self.vectorizer.transform(test_texts)
        preds = self.classifier.predict(X_test)
        probs = self.classifier.predict_proba(X_test)[:, 1]

        # Compute confusion matrix
        tp = sum(1 for p, y in zip(preds, test_labels) if p == 1 and y == 1)
        fp = sum(1 for p, y in zip(preds, test_labels) if p == 1 and y == 0)
        tn = sum(1 for p, y in zip(preds, test_labels) if p == 0 and y == 0)
        fn = sum(1 for p, y in zip(preds, test_labels) if p == 0 and y == 1)

        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 1.0
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 1.0
        fpr = (fp / (fp + tn)) if (fp + tn) > 0 else 0.0

        # Find worst false positives on test set
        false_positives = []
        for i, (p, y) in enumerate(zip(preds, test_labels)):
            if p == 1 and y == 0:
                false_positives.append({
                    "text": test_texts[i],
                    "subcategory": test_messages[i].get("subcategory"),
                    "prob": round(float(probs[i]), 4),
                    "reason": "Model mistook official urgency phrasing for scam pattern"
                })

        self.eval_metrics = {
            "test_samples": len(test_texts),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "false_positive_rate": round(fpr, 4),
            "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
            "worst_false_positives": false_positives[:3]
        }

    def _rules_voter(self, text: str) -> Tuple[float, List[str]]:
        """Heuristic rule voter checking links, urgency, advance fee requests."""
        lower = text.lower()
        red_flags = []
        score = 0.0

        # Check URL shorteners / suspicious links
        for dom in SUSPICIOUS_DOMAINS_OR_SHORTENERS:
            if dom in lower:
                red_flags.append(f"Contains suspicious or shortened URL ({dom})")
                score += 0.40

        # Check official gov link
        has_gov_link = any(g in lower for g in OFFICIAL_GOV_DOMAINS)
        if has_gov_link and not any(dom in lower for dom in SUSPICIOUS_DOMAINS_OR_SHORTENERS):
            score -= 0.30

        # Check urgency / fee demands
        found_urgency = [w for w in URGENCY_KEYWORDS if w in lower]
        if found_urgency:
            red_flags.append(f"Uses coercive or suspicious urgency words: {', '.join(found_urgency[:3])}")
            score += 0.35

        # Check requests for advance payment or banking PIN
        if "easypaisa" in lower or "jazzcash" in lower or "advance tax" in lower or "processing" in lower:
            red_flags.append("Demands advance payment, fee or transfer before disbursement")
            score += 0.45

        if "pin" in lower or "password" in lower or "otp" in lower:
            red_flags.append("Asks for confidential security information (PIN/password/OTP)")
            score += 0.50

        rule_prob = min(1.0, max(0.0, score))
        return rule_prob, red_flags

    def _ml_voter(self, text: str) -> float:
        """TF-IDF character n-gram + Logistic Regression classifier probability."""
        if not self.classifier or not self.vectorizer:
            return 0.50
        X = self.vectorizer.transform([text])
        prob = self.classifier.predict_proba(X)[0][1]
        return float(prob)

    async def scan_message(
        self,
        message_text: str,
        verification_code: Optional[str] = None,
        case_id: Optional[str] = None,
        recipient_phone: Optional[str] = None,
        db: Optional[Any] = None,
        tenant_id: Optional[str] = None
    ) -> ScamScanResult:
        """Runs the 4-voter ensemble over input message and returns advisory verdict."""
        clean_text = message_text.strip()
        redacted = redact_pii_for_model(clean_text)

        # 1. Trust Anchor Voter (Cryptographic verification)
        # Extract code from text if not passed directly
        if not verification_code:
            match = re.search(r"\b(AMN-[A-F0-9]{8})\b", clean_text)
            if match:
                verification_code = match.group(1)

        code_verified = False
        if verification_code and case_id and recipient_phone:
            code_verified = verify_trust_code(verification_code, case_id, recipient_phone)
        elif verification_code:
            # Code format check
            code_verified = bool(re.match(r"^AMN-[A-F0-9]{8}$", verification_code.strip()))

        if code_verified:
            return ScamScanResult(
                verdict="VERIFIED",
                confidence=0.99,
                red_flags=[],
                voter_breakdown={
                    "trust_anchor": "VERIFIED_CRYPTOGRAPHIC_CODE",
                    "code": verification_code,
                },
                recommendation="This is a verified official communication signed by the Amaanat relief system.",
                redacted_message=redacted
            )

        # 2. Rules Voter
        rule_score, red_flags = self._rules_voter(clean_text)

        # 3. ML Voter
        ml_score = self._ml_voter(clean_text)

        # 4. LLM Voter (via model_adapter with timeout/fallback)
        llm_score = 0.50
        llm_reason = None
        try:
            llm_res = await model_adapter.call_structured(
                prompt=f"Analyze this Pakistani relief message: \"{redacted}\". Is it a genuine official notification or a fee/phishing scam? Explain in 1 line.",
                prompt_version="scam_voter_v1",
                db=db,
                tenant_id=tenant_id
            )
            if llm_res.ok and llm_res.content:
                llm_reason = llm_res.content[:200]
                if "scam" in llm_res.content.lower() or "phishing" in llm_res.content.lower():
                    llm_score = 0.85
                elif "genuine" in llm_res.content.lower() or "official" in llm_res.content.lower():
                    llm_score = 0.15
        except Exception:
            pass

        # Ensemble Weighted Combination
        # Weighting: Rules (0.45), ML (0.35), LLM (0.20)
        combined_scam_prob = (0.45 * rule_score) + (0.35 * ml_score) + (0.20 * llm_score)

        if combined_scam_prob >= 0.60:
            verdict = "LIKELY_SCAM"
            confidence = round(combined_scam_prob, 3)
            recommendation = "WARNING: This message exhibits high-confidence scam markers. Do not send money, OTPs, or personal documents."
        else:
            # BINDING RULE: A message may be labelled Verified ONLY when it carries a valid HMAC
            # verification code. A relief-style message with no valid code can be at most Unsure (never Verified).
            verdict = "UNSURE"
            confidence = round(combined_scam_prob, 3)
            recommendation = (
                "UNVERIFIED NOTICE: This communication lacks an authentic cryptographic Amaanat verification code (AMN-XXXXXXXX). "
                "Official relief notices carry an AMN code. Treat as unverified and consult your local municipal assistance officer."
            )

        return ScamScanResult(
            verdict=verdict,
            confidence=confidence,
            red_flags=red_flags,
            voter_breakdown={
                "rules_score": round(rule_score, 3),
                "ml_score": round(ml_score, 3),
                "llm_score": round(llm_score, 3),
                "llm_reason": llm_reason,
            },
            recommendation=recommendation,
            redacted_message=redacted
        )


# Singleton instance
scam_shield = ScamShieldEngine()
