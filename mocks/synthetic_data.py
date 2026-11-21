"""
Synthetic NADRA and Raast database generator for Amaanat Hackathon Prototype.
PROTOTYPE ONLY - No real personal data.
Generates ~200 synthetic citizens with Pakistani name variants and signed QR payloads.
"""
import hmac
import hashlib
import json
import base64
from typing import Dict, Any, List

FAKE_NADRA_SECRET = "MOCK_NADRA_SECRET_KEY_FOR_PROTOTYPE_DEMO_2026"

def sign_qr_payload(data: Dict[str, Any]) -> str:
    serialized = json.dumps(data, sort_keys=True)
    sig = hmac.new(
        FAKE_NADRA_SECRET.encode("utf-8"),
        serialized.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    combined = f"{serialized}###{sig}"
    return base64.b64encode(combined.encode("utf-8")).decode("utf-8")

def verify_qr_payload(qr_b64: str) -> Dict[str, Any]:
    try:
        decoded = base64.b64decode(qr_b64.encode("utf-8")).decode("utf-8")
        serialized, sig = decoded.split("###", 1)
        expected_sig = hmac.new(
            FAKE_NADRA_SECRET.encode("utf-8"),
            serialized.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("QR Signature Mismatch - Possible Counterfeit Document")
        return json.loads(serialized)
    except Exception as e:
        raise ValueError(f"Invalid QR Payload: {str(e)}")

def generate_synthetic_citizens() -> Dict[str, Dict[str, Any]]:
    # Specific targeted pairs/triplets for Challenge 03 name-variant and canonical name testing
    name_variants_groups = [
        ("Muhammad Tariq", "Tariq Mehmood", "1985-04-12", "M", "42101-1000001-1"),
        ("Mohammad Tariq", "Tariq Mehmood", "1985-04-12", "M", "42101-1000002-1"),
        ("Muhammed Tariq", "Tariq Mehmood", "1985-04-12", "M", "42101-1000003-1"),
        ("Mohd Tariq", "Tariq Mehmood", "1985-04-12", "M", "42101-1000004-1"),
        ("Syed Ali Shah", "Ghulam Ali Shah", "1978-09-22", "M", "35201-1000005-1"),
        ("Sayyed Ali Shah", "Ghulam Ali Shah", "1978-09-22", "M", "35201-1000006-1"),
        ("Zainab Bibi", "Abdul Rasheed", "1992-11-05", "F", "42101-1000007-2"),
        ("Zaynab Bibi", "Abdul Rasheed", "1992-11-05", "F", "42101-1000008-2"),
        ("Abdul Rehman", "Muhammad Latif", "1965-01-15", "M", "35201-1000009-1"),
        ("Abdur Rahman", "Muhammad Latif", "1965-01-15", "M", "35201-1000010-1"),
        ("Fatima Noor", "Noor Muhammad", "1995-07-30", "F", "61101-1000011-2"),
        ("Fatimah Noor", "Noor Muhammad", "1995-07-30", "F", "61101-1000012-2"),
        ("Khadija Bibi", "Muhammad Ishaq", "1970-03-18", "F", "42101-1000013-2"),
        ("Amina Begum", "Muhammad Din", "1958-12-01", "F", "35201-1000014-2"),
        ("Aamina Begum", "Muhammad Din", "1958-12-01", "F", "35201-1000015-2"),
        ("Chaudhry Muhammad Asif", "Muhammad Hanif", "1980-06-25", "M", "35201-1000016-1"),
        ("Ch. Mohammad Asif", "Muhammad Hanif", "1980-06-25", "M", "35201-1000017-1"),
    ]

    first_names_m = ["Bilal", "Usman", "Hamza", "Zubair", "Rashid", "Imran", "Farhan", "Babar", "Shoaib", "Naveed", "Waseem", "Kamran", "Salman", "Asad", "Haris", "Fahad", "Danish", "Tahir"]
    first_names_f = ["Maryam", "Ayesha", "Sadia", "Rukhsana", "Bushra", "Uzma", "Tahira", "Parveen", "Nasreen", "Saima", "Hina", "Rabia", "Shaista", "Noreen", "Farzana", "Rubina"]
    last_names = ["Khan", "Ahmed", "Hussain", "Malik", "Butt", "Siddiqui", "Qureshi", "Akhtar", "Bhatti", "Raza", "Nawaz", "Iqbal", "Abbasi", "Chaudhry", "Ansari"]
    father_first = ["Muhammad", "Abdul", "Ghulam", "Nazir", "Sultan", "Bashir", "Ashraf", "Munir", "Arshad", "Liaquat"]

    citizens: Dict[str, Dict[str, Any]] = {}

    # Seed the named variants
    for name, father_name, dob, gender, cnic in name_variants_groups:
        qr_data = {
            "cnic": cnic,
            "name": name,
            "father_name": father_name,
            "dob": dob,
            "gender": gender,
            "issuer": "NADRA-MOCK"
        }
        citizens[cnic] = {
            "cnic": cnic,
            "name": name,
            "father_name": father_name,
            "dob": dob,
            "gender": gender,
            "address": "House 12, Street 4, Sector G-9, Islamabad",
            "family_head_cnic": "42101-1000001-1",
            "is_deceased": False,
            "qr_payload": sign_qr_payload(qr_data)
        }

    # Generate up to 200 synthetic citizens
    idx = len(citizens) + 1
    for i in range(idx, 205):
        is_female = (i % 2 == 0)
        gender = "F" if is_female else "M"
        first = first_names_f[(i * 3) % len(first_names_f)] if is_female else first_names_m[(i * 3) % len(first_names_m)]
        last = last_names[(i * 7) % len(last_names)]
        fname = f"{first} {last}"
        father = f"{father_first[(i * 5) % len(father_first)]} {last_names[(i * 2) % len(last_names)]}"
        year = 1950 + (i % 50)
        month = f"{(i % 12) + 1:02d}"
        day = f"{(i % 28) + 1:02d}"
        dob = f"{year}-{month}-{day}"
        district_code = "35201" if (i % 3 == 0) else ("42101" if (i % 3 == 1) else "61101")
        check_digit = "2" if is_female else "1"
        cnic = f"{district_code}-{i:07d}-{check_digit}"

        is_deceased = (i == 199) # mark one synthetic citizen as deceased for testing

        qr_data = {
            "cnic": cnic,
            "name": fname,
            "father_name": father,
            "dob": dob,
            "gender": gender,
            "issuer": "NADRA-MOCK"
        }
        citizens[cnic] = {
            "cnic": cnic,
            "name": fname,
            "father_name": father,
            "dob": dob,
            "gender": gender,
            "address": f"Plot {i}, Street {(i%20)+1}, Colony B, Lahore",
            "family_head_cnic": f"{district_code}-0000001-1",
            "is_deceased": is_deceased,
            "qr_payload": sign_qr_payload(qr_data)
        }

    return citizens

# Global precomputed mock database
SYNTHETIC_CITIZENS = generate_synthetic_citizens()

# Synthetic Raast Account Titles mapping IBAN -> Holder Name & CNIC
SYNTHETIC_RAAST_ACCOUNTS: Dict[str, Dict[str, Any]] = {}
for cnic, cit in SYNTHETIC_CITIZENS.items():
    iban = f"PK36MOCK000000{cnic.replace('-', '')}"
    SYNTHETIC_RAAST_ACCOUNTS[iban] = {
        "iban": iban,
        "account_title": cit["name"],
        "cnic": cnic,
        "bank_name": "MOCK_MICROFINANCE_BANK",
        "status": "ACTIVE"
    }

# Common demo test IBANs
SYNTHETIC_RAAST_ACCOUNTS["PK36MOCK12345678901234"] = {
    "iban": "PK36MOCK12345678901234",
    "account_title": "Zainab Bibi",
    "cnic": "42101-1000007-2",
    "bank_name": "HABIB_BANK_MOCK",
    "status": "ACTIVE"
}
SYNTHETIC_RAAST_ACCOUNTS["PK36MOCK99999999999999"] = {
    "iban": "PK36MOCK99999999999999",
    "account_title": "Muhammad Tariq",
    "cnic": "42101-1000001-1",
    "bank_name": "ALLIED_BANK_MOCK",
    "status": "ACTIVE"
}
