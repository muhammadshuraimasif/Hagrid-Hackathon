"""Generates authentic Urdu audio clips for Project Amaanat accessibility using edge-tts.

Voice: ur-PK-UzmaNeural (Microsoft Edge TTS Urdu Pakistan).
If network or edge-tts is unavailable, provides a graceful silent MP3 stub so build never fails.
"""
import asyncio
import os
import sys
from pathlib import Path

AUDIO_DIR = Path(__file__).resolve().parent.parent / "web" / "public" / "audio"

PHRASES = {
    # Digits 0 to 9 in Urdu
    "digit_0.mp3": "صفر",
    "digit_1.mp3": "ایک",
    "digit_2.mp3": "دو",
    "digit_3.mp3": "تین",
    "digit_4.mp3": "چار",
    "digit_5.mp3": "پانچ",
    "digit_6.mp3": "چھ",
    "digit_7.mp3": "سات",
    "digit_8.mp3": "آٹھ",
    "digit_9.mp3": "نو",
    # Main screen prompts
    "greeting.mp3": "السلام علیکم۔ امانت پورٹل میں خوش آمدید۔ امداد کی درخواست کے لیے آگے بڑھیں۔",
    "scam_check.mp3": "اگر آپ کو امداد کا کوئی مشکوک پیغام موصول ہوا ہے تو یہاں درج کر کے تصدیق کریں۔",
    "consent.mp3": "کیا آپ ریلیف گرانٹ کی جانچ کے لیے اپنے شناختی اور بینک کوائف کی تصدیق کی رضامندی دیتے ہیں؟ ہاں یا نہیں میں جواب دیں۔",
    "capture_cnic.mp3": "اپنے قومی شناختی کارڈ کے سامنے اور پشت کے رخ کی صاف تصویر لیں۔ دھندلا پن نہ ہو۔",
    "confirm_details.mp3": "اپنے شناختی کارڈ نمبر اور نام کی تصدیق کریں۔ درست ہونے پر سبز بٹن دبائیں۔",
    "status_result.mp3": "آپ کی درخواست موصول ہو گئی ہے۔ موجودہ صورتحال اور تفصیلی وجہ اسکرین پر درج ہے۔",
    "haan.mp3": "ہاں",
    "nahin.mp3": "نہیں",
}


async def generate_clip(filename: str, text: str, voice: str = "ur-PK-UzmaNeural"):
    out_path = AUDIO_DIR / filename
    if out_path.exists() and out_path.stat().st_size > 500:
        return
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(out_path))
        print(f"Generated {filename} ({out_path.stat().st_size} bytes)")
    except Exception as exc:
        print(f"Warning: edge-tts generation failed for {filename}: {exc}")
        # Write minimal valid silent MP3 frame (128kbps, 44.1kHz, layer 3)
        silent_mp3_frame = bytes([
            0xFF, 0xFB, 0x90, 0x64, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        ] * 32)
        out_path.write_bytes(silent_mp3_frame)
        print(f"Fallback: Created stub {filename}")


async def main():
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    tasks = [generate_clip(fname, text) for fname, text in PHRASES.items()]
    await asyncio.gather(*tasks)
    print(f"Completed audio setup for {len(PHRASES)} clips in {AUDIO_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
