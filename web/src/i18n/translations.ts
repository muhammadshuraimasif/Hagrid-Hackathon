/**
 * Bilingual Translation Dictionary for Project Amaanat (English & Urdu).
 * Full RTL support for low-literacy citizens.
 */

export type Language = 'en' | 'ur';

export const translations = {
  en: {
    prototypeBanner: 'PROTOTYPE ONLY - FOR HAGRID\'S HACKATHON 2026. MOCKED DATA ONLY.',
    appName: 'Amaanat Relief Portal',
    langToggle: 'اردو',
    online: 'Online',
    offline: 'Offline (Saving Locally)',
    syncing: 'Syncing Data...',
    
    // Steps
    step1Title: 'Welcome to Amaanat',
    step1Desc: 'Apply for official emergency relief assistance with confidence.',
    step1StartBtn: 'Start Application',
    step1CheckScamBtn: 'Check a Suspicious Message',
    
    step2Title: 'Scam Shield Check',
    step2Desc: 'Paste any SMS, WhatsApp, or letter to verify if it is an authentic Amaanat notice or a scam.',
    step2Placeholder: 'Paste message here (e.g., You won PKR 50,000, send fee...)',
    step2ScanBtn: 'Verify Message',
    step2SkipBtn: 'Skip & Continue Application',
    step2ResultTitle: 'Verification Result',
    step2RedFlags: 'Detected Red Flags:',
    
    step3Title: 'Universal Consent',
    step3Desc: 'We strictly protect your sovereignty. You choose what data is verified and can withdraw anytime.',
    step3ScopeIdentity: 'National Identity & CNIC verification with NADRA',
    step3ScopeFamily: 'Household size verification for grant eligibility',
    step3ScopePayment: 'Account title check with Raast for direct payout',
    step3Retention: 'Purpose: Flood Relief Payout | Valid for: 12 months',
    step3YesBtn: 'Haan / Agree (ہاں)',
    step3NoBtn: 'Nahin / Decline (نہیں)',
    
    step4Title: 'Capture CNIC Photos',
    step4Desc: 'Please take clear, un-obscured photos of your original CNIC front and back.',
    step4FrontLabel: 'CNIC Front (Photo & Name)',
    step4BackLabel: 'CNIC Back (QR Code & Address)',
    step4BlurWarning: 'Photo is blurry! Please hold camera steady and retake.',
    step4SuccessCompress: 'Image compressed under 200 KB.',
    step4UploadBtn: 'Next Step',
    
    step5Title: 'Confirm Extracted Details',
    step5Desc: 'Please review your extracted identity details. Tap tick to confirm or keypad to edit.',
    step5NameLabel: 'Claimant Full Name',
    step5CnicLabel: 'CNIC Number',
    step5ConfirmBtn: 'Confirm Details & Submit',
    step5RejectBtn: 'Edit with Keypad',
    
    step6Title: 'Application Status & Decision',
    step6Desc: 'Your emergency relief claim has been processed by the transparent decision engine.',
    step6AutoNotice: 'Approved on 60-Second Reversible Hold (Direct Payout Initiated)',
    step6AskNotice: 'Additional Information Required (Next Best Evidence)',
    step6HumanNotice: 'Escalated to Human Relief Officer for Review',
    step6NextStep: 'Next Steps:',
    step6ReplayAudio: 'Replay Explanation Audio',
    
    // My Data
    myDataTitle: 'My Data Sovereignty',
    myDataDesc: 'View and manage personal data access permissions granted to the relief department.',
    withdrawAllBtn: 'Withdraw All Consent Immediately',
    withdrawalNotice: 'Withdrawal takes effect immediately on the server upon next sync.',
    requestCorrectionBtn: 'Request Data Correction',
  },
  ur: {
    prototypeBanner: 'صرف پروٹوٹائپ - ہیکاتھون 2026 کے لیے فرضی ڈیٹا',
    appName: 'امانت ریلیف پورٹل',
    langToggle: 'English',
    online: 'آن لائن',
    offline: 'آف لائن (ڈیٹا محفوظ ہے)',
    syncing: 'ڈیٹا سرور پر بھیجا جا رہا ہے...',
    
    // Steps
    step1Title: 'امانت ریلیف پورٹل میں خوش آمدید',
    step1Desc: 'حکومتی ہنگامی مالی امداد کے لیے آسان اور محفوظ درخواست۔',
    step1StartBtn: 'درخواست شروع کریں',
    step1CheckScamBtn: 'مشکوک میسج چیک کریں',
    
    step2Title: 'دھوکہ دہی سے بچاؤ (اسکیم شیلڈ)',
    step2Desc: 'موصول ہونے والا میسج یہاں درج کریں تاکہ تصدیق ہو سکے کہ آیا یہ اصل ہے یا فراڈ۔',
    step2Placeholder: 'میسج یہاں لکھیں یا پیسٹ کریں...',
    step2ScanBtn: 'میسج کی جانچ کریں',
    step2SkipBtn: 'چھوڑیں اور آگے بڑھیں',
    step2ResultTitle: 'جانچ کا نتیجہ',
    step2RedFlags: 'مشکوک نشانیاں:',
    
    step3Title: 'ڈیٹا کے استعمال کی اجازت (رضامندی)',
    step3Desc: 'آپ اپنے ڈیٹا کے مکمل مالک ہیں۔ آپ کی اجازت کے بغیر کوئی معلومات چیک نہیں کی جا سکتیں۔',
    step3ScopeIdentity: 'نادرا کے ذریعے شناختی کارڈ کی تصدیق',
    step3ScopeFamily: 'اہلیت کے لیے خاندان کے افراد کی تصدیق',
    step3ScopePayment: 'براہ راست رقم منتقلی کے لیے راست (Raast) بینک اکاؤنٹ تصدیق',
    step3Retention: 'مقصد: ہنگامی امداد | مدت: 12 ماہ',
    step3YesBtn: 'ہاں (منظور ہے)',
    step3NoBtn: 'نہیں (منسوخ کریں)',
    
    step4Title: 'شناختی کارڈ کی تصاویر',
    step4Desc: 'اپنے اصل قومی شناختی کارڈ کے سامنے اور پیچھے کی صاف تصاویر لیں۔',
    step4FrontLabel: 'شناختی کارڈ کا سامنے کا رخ',
    step4BackLabel: 'شناختی کارڈ کی پشت (کیو آر کوڈ)',
    step4BlurWarning: 'تصویر دھندلی ہے! براہ کرم کیمرہ ساکت رکھ کر دوبارہ تصویر لیں۔',
    step4SuccessCompress: 'تصویر کو 200 کے بی سے کم سائز میں کمپریس کر لیا گیا ہے۔',
    step4UploadBtn: 'تصاویر محفوظ کریں اور آگے بڑھیں',
    
    step5Title: 'کوائف کی تصدیق',
    step5Desc: 'براہ کرم اپنے نام اور شناختی کارڈ نمبر کی تصدیق کریں۔ درست ہونے پر سبز بٹن دبائیں۔',
    step5NameLabel: 'درخواست گزار کا نام',
    step5CnicLabel: 'شناختی کارڈ نمبر',
    step5ConfirmBtn: 'کوائف درست ہیں (تصدیق)',
    step5RejectBtn: 'درستگی کریں',
    
    step6Title: 'درخواست کی صورتحال اور فیصلہ',
    step6Desc: 'آپ کی درخواست کا جائزہ مکمل کر لیا گیا ہے۔ شفافیت کے اصولوں کے تحت تفصیل نیچے درج ہے۔',
    step6AutoNotice: 'مبارک ہو! درخواست 60 سیکنڈ کے عارضی ہولڈ پر خودکار منظور ہو چکی ہے۔',
    step6AskNotice: 'درخواست کی جانچ کے لیے ایک اضافی دستاویز درکار ہے۔',
    step6HumanNotice: 'آپ کی درخواست سرکاری افسر کے پاس جانچ کے لیے بھیج دی گئی ہے۔',
    step6NextStep: 'آئندہ کا لائحہ عمل:',
    step6ReplayAudio: 'آڈیو دوبارہ سنیں',
    
    // My Data
    myDataTitle: 'میرا ڈیٹا اور رضامندی',
    myDataDesc: 'دیکھیں کہ آپ کی کون سی معلومات ریلیف ڈپارٹمنٹ کے پاس ہیں اور جب چاہیں منسوخ کریں۔',
    withdrawAllBtn: 'تمام رضامندی فوری منسوخ کریں',
    withdrawalNotice: 'رضامندی کی منسوخی سرور کے ساتھ رابطہ ہوتے ہی نافذ العمل ہو جائے گی۔',
    requestCorrectionBtn: 'غلط کوائف کی درستگی کی درخواست',
  },
};
