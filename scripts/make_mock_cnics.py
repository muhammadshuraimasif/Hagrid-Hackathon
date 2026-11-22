"""Script to generate realistic synthetic CNIC mock images with QR codes.

Follows docs/BLUEPRINT.md section 9.6:
- Creates synthetic Pakistani CNICs (Front & Back) with signed QR payloads.
- Generates test variants:
  1. genuine (clean, sharp, matching QR)
  2. blurry (low Laplacian variance, failing quality gate)
  3. glare (overexposed flash reflection)
  4. cropped (partial card boundary)
  5. text_edited (pasted region / forgery markers with bounding boxes)
  6. qr_mismatch (printed text disagrees with signed QR payload)
  7. low_res (sub-minimum resolution)
Saves outputs to /eval/fixtures/
"""
import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from mocks.synthetic_data import sign_qr_payload

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "eval" / "fixtures"


def draw_simple_qr(data_str: str, size: int = 180) -> np.ndarray:
    """Generates a high-contrast QR code image using OpenCV with standard quiet zone."""
    try:
        encoder = cv2.QRCodeEncoder.create()
        encoded = encoder.encode(data_str)
        if encoded is not None and len(encoded) > 0:
            bordered = cv2.copyMakeBorder(encoded, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=255)
            qr_raw = cv2.resize(bordered, (size, size), interpolation=cv2.INTER_NEAREST)
            return qr_raw
    except Exception:
        pass

    # Deterministic fallback QR-like matrix pattern with locator patterns
    block_size = size // 25
    # Outer borders
    for x in range(25):
        for y in range(25):
            # 3 locator corners (top-left, top-right, bottom-left)
            in_tl = (x < 7 and y < 7)
            in_tr = (x >= 18 and y < 7)
            in_bl = (x < 7 and y >= 18)
            if in_tl or in_tr or in_bl:
                lx = x if x < 7 else (x - 18 if in_tr else x)
                ly = y if y < 7 else (y if in_tr else y - 18)
                if lx == 0 or lx == 6 or ly == 0 or ly == 6 or (2 <= lx <= 4 and 2 <= ly <= 4):
                    cv2.rectangle(qr_img, (x * block_size, y * block_size),
                                  ((x + 1) * block_size, (y + 1) * block_size), 0, -1)
            else:
                # Pseudorandom data bits from hash of data_str
                bit = (hash(f"{data_str}_{x}_{y}") % 2 == 0)
                if bit:
                    cv2.rectangle(qr_img, (x * block_size, y * block_size),
                                  ((x + 1) * block_size, (y + 1) * block_size), 0, -1)

    return qr_img


def create_base_cnic_front(
    name: str = "MUHAMMAD TARIQ",
    father_name: str = "TARIQ MEHMOOD",
    cnic: str = "42101-1000001-1",
    dob: str = "1985-04-12",
    gender: str = "M",
    width: int = 856,
    height: int = 540
) -> Image.Image:
    """Renders a synthetic Pakistani CNIC Front."""
    img = Image.new("RGB", (width, height), color=(240, 248, 240))
    draw = ImageDraw.Draw(img)

    # Top header green band
    draw.rectangle([(0, 0), (width, 80)], fill=(0, 102, 51))
    draw.text((20, 15), "ISLAMIC REPUBLIC OF PAKISTAN", fill=(255, 255, 255))
    draw.text((20, 45), "NATIONAL IDENTITY CARD - PROTOTYPE ONLY", fill=(220, 240, 220))

    # Watermark / Emblem circle
    draw.ellipse([(680, 100), (820, 240)], outline=(200, 230, 200), width=4)

    # Photo Box
    draw.rectangle([(30, 110), (210, 330)], fill=(210, 220, 210), outline=(0, 102, 51), width=2)
    draw.text((60, 200), "[ PHOTO ]", fill=(80, 120, 80))

    # Printed Demographics
    draw.text((240, 110), "Name:", fill=(100, 100, 100))
    draw.text((240, 130), name, fill=(10, 10, 10))

    draw.text((240, 175), "Father Name:", fill=(100, 100, 100))
    draw.text((240, 195), father_name, fill=(10, 10, 10))

    draw.text((240, 240), "Gender:", fill=(100, 100, 100))
    draw.text((240, 260), gender, fill=(10, 10, 10))

    draw.text((360, 240), "Date of Birth:", fill=(100, 100, 100))
    draw.text((360, 260), dob, fill=(10, 10, 10))

    draw.text((240, 310), "Identity Number (CNIC):", fill=(100, 100, 100))
    draw.text((240, 335), cnic, fill=(0, 51, 102))

    # Bottom footer green band
    draw.rectangle([(0, height - 40), (width, height)], fill=(0, 102, 51))
    draw.text((20, height - 30), "HAGRID'S HACKATHON 2026 - SYNTHETIC DATASET", fill=(255, 255, 255))

    return img


def create_base_cnic_back(
    cnic: str = "42101-1000001-1",
    qr_payload_dict: Optional[dict] = None,
    width: int = 856,
    height: int = 540
) -> Image.Image:
    """Renders a synthetic Pakistani CNIC Back with signed QR code."""
    img = Image.new("RGB", (width, height), color=(245, 245, 240))
    draw = ImageDraw.Draw(img)

    # Address section
    draw.text((30, 40), "Present Address:", fill=(100, 100, 100))
    draw.text((30, 65), "House 123, Street 4, Sector G-9/1, Islamabad", fill=(20, 20, 20))

    draw.text((30, 115), "Permanent Address:", fill=(100, 100, 100))
    draw.text((30, 140), "Village & P.O. Nowshera Kalan, KPK", fill=(20, 20, 20))

    # Generate and paste QR code
    payload = qr_payload_dict or {
        "cnic": cnic,
        "name": "MUHAMMAD TARIQ",
        "father_name": "TARIQ MEHMOOD",
        "dob": "1985-04-12"
    }
    signed_qr_str = sign_qr_payload(payload)
    qr_cv = draw_simple_qr(signed_qr_str, size=160)
    qr_pil = Image.fromarray(qr_cv).convert("RGB")

    img.paste(qr_pil, (640, 60))
    draw.text((645, 230), "VERIFIED QR", fill=(0, 102, 51))

    # Bottom Machine Readable Zone (MRZ)
    clean_cnic = cnic.replace("-", "")
    mrz_line1 = f"I<PAK{clean_cnic}<<<<<<<<<<<<<<<"
    mrz_line2 = f"8504128M3001018PAK<<<<<<<<<<<4"
    draw.rectangle([(0, height - 100), (width, height)], fill=(230, 230, 220))
    draw.text((30, height - 85), mrz_line1, fill=(30, 30, 30))
    draw.text((30, height - 50), mrz_line2, fill=(30, 30, 30))

    return img


def generate_all_fixtures():
    """Builds and saves all genuine and anomalous CNIC card variants."""
    os.makedirs(FIXTURES_DIR, exist_ok=True)

    base_front = create_base_cnic_front()
    base_back = create_base_cnic_back()

    cv_front = cv2.cvtColor(np.array(base_front), cv2.COLOR_RGB2BGR)
    cv_back = cv2.cvtColor(np.array(base_back), cv2.COLOR_RGB2BGR)

    # 1. Genuine Front & Back
    cv2.imwrite(str(FIXTURES_DIR / "cnic_genuine_front.jpg"), cv_front)
    cv2.imwrite(str(FIXTURES_DIR / "cnic_genuine_back.jpg"), cv_back)

    # 2. Blurry Variant (Gaussian blur)
    blurry = cv2.GaussianBlur(cv_front, (21, 21), 0)
    cv2.imwrite(str(FIXTURES_DIR / "cnic_blurry_front.jpg"), blurry)

    # 3. Glare Variant (Bright specular reflection circle over text)
    glare = cv_front.copy()
    cv2.circle(glare, (350, 150), 75, (255, 255, 255), -1)
    cv2.imwrite(str(FIXTURES_DIR / "cnic_glare_front.jpg"), glare)

    # 4. Cropped Variant (Only top 45% of card)
    h, w = cv_front.shape[:2]
    cropped = cv_front[: int(h * 0.45), :]
    cv2.imwrite(str(FIXTURES_DIR / "cnic_cropped_front.jpg"), cropped)

    # 5. Low Resolution Variant (< 300px)
    low_res = cv2.resize(cv_front, (240, 150))
    cv2.imwrite(str(FIXTURES_DIR / "cnic_low_res_front.jpg"), low_res)

    # 6. Text Edited / Forgery Variant (Pasted rectangular region over name)
    edited = cv_front.copy()
    # Paste a mismatched gray box with text over the name
    cv2.rectangle(edited, (235, 125), (550, 160), (225, 230, 225), -1)
    cv2.rectangle(edited, (235, 125), (550, 160), (180, 180, 180), 1)  # Edges / paste artifacts
    cv2.putText(edited, "FAKHAR ZAMAN", (245, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.imwrite(str(FIXTURES_DIR / "cnic_edited_front.jpg"), edited)

    # 7. QR Mismatch Variant: Printed name is Muhammad Tariq, but QR is signed for Syed Ali Shah
    mismatch_back = create_base_cnic_back(
        cnic="42101-1000001-1",
        qr_payload_dict={
            "cnic": "35201-1000005-1",
            "name": "SYED ALI SHAH",
            "father_name": "GHULAM ALI SHAH",
            "dob": "1978-09-22"
        }
    )
    cv_mismatch_back = cv2.cvtColor(np.array(mismatch_back), cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(FIXTURES_DIR / "cnic_qr_mismatch_back.jpg"), cv_mismatch_back)

    print(f"Generated 7 CNIC fixtures successfully in {FIXTURES_DIR}")


if __name__ == "__main__":
    generate_all_fixtures()
