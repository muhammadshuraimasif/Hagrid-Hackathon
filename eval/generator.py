"""Deterministic synthetic dataset generator for Amaanat Evaluation Harness.

Generates 3,000 synthetic claim cases with ground truth labels and diverse edge cases:
- 1,500 clean eligible
- 400 clean ineligible
- 250 name variants / transliterations
- 200 missing fields / blurry documents (fixable)
- 200 duplicates and fraud rings
- 150 forged / edited documents
- 150 wrong destination account
- 150 service failure / chaos edge cases
Total: 3,000 cases.
Plus 800 synthetic SMS/WhatsApp messages (400 genuine, 400 scam) for Module 6.

All generation is strictly deterministic given a fixed random seed.
"""
import random
from typing import Any, Dict, List, Tuple


COMMON_FIRST_NAMES = [
    "Muhammad", "Mohammad", "Ahmed", "Ali", "Fatima", "Ayesha", "Zainab",
    "Usman", "Bilal", "Hamza", "Maryam", "Sana", "Khadija", "Tariq", "Imran"
]

COMMON_LAST_NAMES = [
    "Khan", "Bibi", "Ahmed", "Ali", "Hussain", "Shah", "Malik", "Rehman",
    "Akram", "Iqbal", "Siddiqui", "Abbasi", "Qureshi", "Ansari", "Bano"
]

DISTRICTS = [
    "Peshawar", "Nowshera", "Charsadda", "Swat", "Dera Ismail Khan",
    "Karachi Central", "Larkana", "Sukkur", "Thatta", "Badin"
]


def generate_synthetic_dataset(seed: int = 42) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Generates 3,000 synthetic cases and 800 messages with deterministic seed."""
    rng = random.Random(seed)
    cases: List[Dict[str, Any]] = []

    def make_cnic(idx: int) -> str:
        d1 = 10000 + (idx % 90000)
        d2 = 1000000 + (idx * 7 % 9000000)
        d3 = 1 + (idx % 9)
        return f"{d1}-{d2}-{d3}"

    def make_iban(idx: int) -> str:
        return f"PK{10 + (idx % 89):02d}HABB0000{idx:010d}"

    case_id_counter = 1

    # Distribution of channels: 50% self, 35% helper, 15% voice
    channels = ["self", "helper", "voice"]
    channel_weights = [0.50, 0.35, 0.15]

    # Category 1: 1,500 Clean Eligible
    for _ in range(1500):
        first = rng.choice(COMMON_FIRST_NAMES)
        last = rng.choice(COMMON_LAST_NAMES)
        name = f"{first} {last}"
        cnic = make_cnic(case_id_counter)
        iban = make_iban(case_id_counter)
        channel = rng.choices(channels, weights=channel_weights, k=1)[0]
        district = rng.choice(DISTRICTS)

        cases.append({
            "case_id": f"CASE-CLN-{case_id_counter:05d}",
            "category": "clean_eligible",
            "channel": channel,
            "district": district,
            "name_variant_group": "standard",
            "name": name,
            "canonical_name": name.upper(),
            "father_name": f"{rng.choice(COMMON_FIRST_NAMES)} {last}",
            "cnic": cnic,
            "iban": iban,
            "claim_amount": 25000.0,
            "monthly_income": rng.randint(15000, 24000),  # Under 25,000 cutoff
            "family_size": rng.randint(4, 9),             # At least 4 members
            "has_cnic_document": True,
            "doc_clarity": "clear",
            "doc_authenticity": 0.98,
            "account_title_match": True,
            "identity_match_exact": True,
            "no_rule_unknown": True,
            "anomaly_flag": False,
            "services_healthy": True,
            "ground_truth_eligible": True,
            "ground_truth_fraud": False,
        })
        case_id_counter += 1

    # Category 2: 400 Clean Ineligible (Income > 25,000 or small family)
    for _ in range(400):
        first = rng.choice(COMMON_FIRST_NAMES)
        last = rng.choice(COMMON_LAST_NAMES)
        name = f"{first} {last}"
        cnic = make_cnic(case_id_counter)
        iban = make_iban(case_id_counter)
        channel = rng.choices(channels, weights=channel_weights, k=1)[0]
        district = rng.choice(DISTRICTS)

        # Ineligible due to high income or low family size
        high_income = rng.choice([True, False])
        monthly_income = rng.randint(35000, 75000) if high_income else 20000
        family_size = 2 if not high_income else 5

        cases.append({
            "case_id": f"CASE-INEL-{case_id_counter:05d}",
            "category": "clean_ineligible",
            "channel": channel,
            "district": district,
            "name_variant_group": "standard",
            "name": name,
            "canonical_name": name.upper(),
            "father_name": f"{rng.choice(COMMON_FIRST_NAMES)} {last}",
            "cnic": cnic,
            "iban": iban,
            "claim_amount": 25000.0,
            "monthly_income": monthly_income,
            "family_size": family_size,
            "has_cnic_document": True,
            "doc_clarity": "clear",
            "doc_authenticity": 0.96,
            "account_title_match": True,
            "identity_match_exact": True,
            "no_rule_unknown": True,
            "anomaly_flag": False,
            "services_healthy": True,
            "ground_truth_eligible": False,
            "ground_truth_fraud": False,
        })
        case_id_counter += 1

    # Category 3: 250 Name Variants / Transliterations (Eligible, but non-exact string match)
    for _ in range(250):
        # Muhammad vs Mohammad / Ahmad vs Ahmed
        v_pair = rng.choice([("Muhammad", "Mohammad"), ("Ahmed", "Ahmad"), ("Usman", "Othman")])
        last = rng.choice(COMMON_LAST_NAMES)
        app_name = f"{v_pair[0]} {last}"
        nadra_name = f"{v_pair[1]} {last}"
        cnic = make_cnic(case_id_counter)
        iban = make_iban(case_id_counter)
        channel = rng.choices(channels, weights=channel_weights, k=1)[0]
        district = rng.choice(DISTRICTS)

        cases.append({
            "case_id": f"CASE-VAR-{case_id_counter:05d}",
            "category": "name_variant",
            "channel": channel,
            "district": district,
            "name_variant_group": "transliteration_variant",
            "name": app_name,
            "canonical_name": app_name.upper(),
            "nadra_name": nadra_name.upper(),
            "father_name": f"{rng.choice(COMMON_FIRST_NAMES)} {last}",
            "cnic": cnic,
            "iban": iban,
            "claim_amount": 25000.0,
            "monthly_income": rng.randint(15000, 22000),
            "family_size": rng.randint(4, 7),
            "has_cnic_document": True,
            "doc_clarity": "clear",
            "doc_authenticity": 0.95,
            "account_title_match": True,
            "identity_match_exact": False,  # Non-exact!
            "no_rule_unknown": True,
            "anomaly_flag": False,
            "services_healthy": True,
            "ground_truth_eligible": True,
            "ground_truth_fraud": False,
        })
        case_id_counter += 1

    # Category 4: 200 Missing Fields / Blurry Documents (Fixable, ASK candidates)
    for _ in range(200):
        first = rng.choice(COMMON_FIRST_NAMES)
        last = rng.choice(COMMON_LAST_NAMES)
        name = f"{first} {last}"
        cnic = make_cnic(case_id_counter)
        iban = make_iban(case_id_counter)
        channel = rng.choices(channels, weights=channel_weights, k=1)[0]
        district = rng.choice(DISTRICTS)

        cases.append({
            "case_id": f"CASE-ASK-{case_id_counter:05d}",
            "category": "missing_or_blurry",
            "channel": channel,
            "district": district,
            "name_variant_group": "standard",
            "name": name,
            "canonical_name": name.upper(),
            "father_name": f"{rng.choice(COMMON_FIRST_NAMES)} {last}",
            "cnic": cnic,
            "iban": iban,
            "claim_amount": 25000.0,
            "monthly_income": rng.randint(16000, 23000),
            "family_size": rng.randint(4, 8),
            "has_cnic_document": True,
            "doc_clarity": "blurry",
            "doc_authenticity": 0.65,
            "account_title_match": True,
            "identity_match_exact": True,
            "no_rule_unknown": True,
            "anomaly_flag": False,
            "services_healthy": True,
            "ground_truth_eligible": True,
            "ground_truth_fraud": False,
        })
        case_id_counter += 1

    # Category 5: 200 Duplicates & Fraud Rings
    for _ in range(200):
        first = rng.choice(COMMON_FIRST_NAMES)
        last = rng.choice(COMMON_LAST_NAMES)
        name = f"{first} {last}"
        cnic = make_cnic(case_id_counter)
        iban = make_iban(case_id_counter)
        channel = rng.choices(channels, weights=channel_weights, k=1)[0]
        district = rng.choice(DISTRICTS)

        cases.append({
            "case_id": f"CASE-DUP-{case_id_counter:05d}",
            "category": "duplicate_or_ring",
            "channel": channel,
            "district": district,
            "name_variant_group": "standard",
            "name": name,
            "canonical_name": name.upper(),
            "father_name": f"{rng.choice(COMMON_FIRST_NAMES)} {last}",
            "cnic": cnic,
            "iban": iban,
            "claim_amount": 25000.0,
            "monthly_income": rng.randint(15000, 24000),
            "family_size": 5,
            "has_cnic_document": True,
            "doc_clarity": "clear",
            "doc_authenticity": 0.90,
            "account_title_match": True,
            "identity_match_exact": True,
            "no_rule_unknown": True,
            "anomaly_flag": True,  # Hard anomaly!
            "services_healthy": True,
            "ground_truth_eligible": False,
            "ground_truth_fraud": True,
        })
        case_id_counter += 1

    # Category 6: 150 Forged / Edited Documents
    for _ in range(150):
        first = rng.choice(COMMON_FIRST_NAMES)
        last = rng.choice(COMMON_LAST_NAMES)
        name = f"{first} {last}"
        cnic = make_cnic(case_id_counter)
        iban = make_iban(case_id_counter)
        channel = rng.choices(channels, weights=channel_weights, k=1)[0]
        district = rng.choice(DISTRICTS)

        cases.append({
            "case_id": f"CASE-FRG-{case_id_counter:05d}",
            "category": "forged_document",
            "channel": channel,
            "district": district,
            "name_variant_group": "standard",
            "name": name,
            "canonical_name": name.upper(),
            "father_name": f"{rng.choice(COMMON_FIRST_NAMES)} {last}",
            "cnic": cnic,
            "iban": iban,
            "claim_amount": 25000.0,
            "monthly_income": rng.randint(15000, 24000),
            "family_size": 5,
            "has_cnic_document": True,
            "doc_clarity": "forged",
            "doc_authenticity": 0.25,
            "account_title_match": True,
            "identity_match_exact": True,
            "no_rule_unknown": True,
            "anomaly_flag": False,
            "services_healthy": True,
            "ground_truth_eligible": False,
            "ground_truth_fraud": True,
        })
        case_id_counter += 1

    # Category 7: 150 Wrong Destination Account (Account Title Mismatch)
    for _ in range(150):
        first = rng.choice(COMMON_FIRST_NAMES)
        last = rng.choice(COMMON_LAST_NAMES)
        name = f"{first} {last}"
        cnic = make_cnic(case_id_counter)
        iban = make_iban(case_id_counter)
        channel = rng.choices(channels, weights=channel_weights, k=1)[0]
        district = rng.choice(DISTRICTS)

        cases.append({
            "case_id": f"CASE-ACC-{case_id_counter:05d}",
            "category": "wrong_account",
            "channel": channel,
            "district": district,
            "name_variant_group": "standard",
            "name": name,
            "canonical_name": name.upper(),
            "father_name": f"{rng.choice(COMMON_FIRST_NAMES)} {last}",
            "cnic": cnic,
            "iban": iban,
            "claim_amount": 25000.0,
            "monthly_income": rng.randint(15000, 24000),
            "family_size": 5,
            "has_cnic_document": True,
            "doc_clarity": "clear",
            "doc_authenticity": 0.95,
            "account_title_match": False,  # Mismatch!
            "identity_match_exact": True,
            "no_rule_unknown": True,
            "anomaly_flag": False,
            "services_healthy": True,
            "ground_truth_eligible": True,
            "ground_truth_fraud": True,
        })
        case_id_counter += 1

    # Category 8: 150 Service Failure / Chaos Edge Cases
    for _ in range(150):
        first = rng.choice(COMMON_FIRST_NAMES)
        last = rng.choice(COMMON_LAST_NAMES)
        name = f"{first} {last}"
        cnic = make_cnic(case_id_counter)
        iban = make_iban(case_id_counter)
        channel = rng.choices(channels, weights=channel_weights, k=1)[0]
        district = rng.choice(DISTRICTS)

        cases.append({
            "case_id": f"CASE-SRV-{case_id_counter:05d}",
            "category": "service_failure",
            "channel": channel,
            "district": district,
            "name_variant_group": "standard",
            "name": name,
            "canonical_name": name.upper(),
            "father_name": f"{rng.choice(COMMON_FIRST_NAMES)} {last}",
            "cnic": cnic,
            "iban": iban,
            "claim_amount": 25000.0,
            "monthly_income": rng.randint(15000, 24000),
            "family_size": 5,
            "has_cnic_document": True,
            "doc_clarity": "clear",
            "doc_authenticity": 0.95,
            "account_title_match": True,
            "identity_match_exact": True,
            "no_rule_unknown": True,
            "anomaly_flag": False,
            "services_healthy": False,  # Down!
            "ground_truth_eligible": True,
            "ground_truth_fraud": False,
        })
        case_id_counter += 1

    # Shuffle deterministically
    rng.shuffle(cases)

    # 800 synthetic messages (400 genuine, 400 scam) for Module 6
    messages: List[Dict[str, Any]] = []
    
    genuine_templates = [
        "Amaanat Relief: Your application {case_id} has been registered. No payment is required for relief.",
        "Your grant of PKR 25,000 is ready for review. Official portal: https://relief.gov.pk/status",
        "NADRA verification completed for application {case_id}. Please wait for officer review.",
        "Amaanat Alert: Please do not share your OTP with anyone. Our officers never ask for your PIN.",
    ]
    hard_genuine_templates = [
        "Urgent: Flood relief grant distribution starts tomorrow at Municipal High School. Bring original CNIC.",
        "Important notification regarding Benazir Income Support Program disbursement schedule.",
    ]
    scam_templates = [
        "CONGRATULATIONS! You won PKR 50,000 from Benazir Relief! Send PKR 1,500 advance tax via EasyPaisa to claim.",
        "Amaanat Alert: Your grant is blocked! Send your ATM PIN and CNIC copy to 0300-1234567 immediately.",
        "Prime Minister Relief Fund: Click bit.ly/pm-cash-free to withdraw PKR 25,000 cash instantly.",
        "Urgent fee required: Pay 2,000 PKR registration charges to receive BISP flood compensation.",
    ]

    for m_idx in range(400):
        if m_idx < 100:
            tmpl = rng.choice(hard_genuine_templates)
            subcat = "hard_genuine"
        else:
            tmpl = rng.choice(genuine_templates)
            subcat = "standard_genuine"
        text = tmpl.format(case_id=f"CASE-{m_idx:04d}")
        messages.append({
            "msg_id": f"MSG-GEN-{m_idx:04d}",
            "text": text,
            "label": "GENUINE",
            "subcategory": subcat,
            "ground_truth_scam": False
        })

    for m_idx in range(400):
        tmpl = rng.choice(scam_templates)
        messages.append({
            "msg_id": f"MSG-SCM-{m_idx:04d}",
            "text": tmpl,
            "label": "SCAM",
            "subcategory": "advance_fee_or_phishing",
            "ground_truth_scam": True
        })

    rng.shuffle(messages)

    return cases, messages
