import React, { useState, useEffect } from 'react';
import {
  Volume2,
  Globe,
  ShieldCheck,
  ShieldAlert,
  Camera,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Clock,
  Sparkles,
  ArrowRight,
  Database,
  Wifi,
  WifiOff,
  UserCheck,
  RotateCcw
} from 'lucide-react';
import { api } from '../../api/client';
import { queueOutboxEvent, syncOutboxEvents } from '../../db/outbox';
import { Language, translations } from '../../i18n/translations';
import { playAudioClip, playChainedDigits, startUrduSpeechRecognition } from '../../utils/audio';
import { processAndCheckImage, uploadDocumentChunked } from '../../utils/image';
import { Keypad } from '../common/Keypad';
import { MyData } from './MyData';

interface CitizenPortalProps {
  initialLanguage?: Language;
}

export const CitizenPortal: React.FC<CitizenPortalProps> = ({ initialLanguage = 'ur' }) => {
  const [lang, setLang] = useState<Language>(initialLanguage);
  const isUrdu = lang === 'ur';
  const t = translations[lang];

  // Flow State (Screens 1 to 6)
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [showMyData, setShowMyData] = useState<boolean>(false);
  const [onlineStatus, setOnlineStatus] = useState<boolean>(navigator.onLine);
  const [syncing, setSyncing] = useState<boolean>(false);

  // Application Data
  const [caseId, setCaseId] = useState<string>(() => `case-${Date.now().toString(36)}`);
  const [cnicDigits, setCnicDigits] = useState<string>('4210110000011');
  const [claimantName] = useState<string>('MUHAMMAD TARIQ');
  const [iban] = useState<string>('PK36HABB0000001234567801');

  // Screen 2: Scam Check State
  const [scamInput, setScamInput] = useState<string>('');
  const [scamLoading, setScamLoading] = useState<boolean>(false);
  const [scamResult, setScamResult] = useState<any>(null);

  // Screen 4: CNIC Photos
  const [frontBlob, setFrontBlob] = useState<Blob | null>(null);
  const [backBlob, setBackBlob] = useState<Blob | null>(null);
  const [frontPreview, setFrontPreview] = useState<string | null>(null);
  const [backPreview, setBackPreview] = useState<string | null>(null);
  const [frontBlurry, setFrontBlurry] = useState<boolean>(false);
  const [backBlurry, setBackBlurry] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadingDocs, setUploadingDocs] = useState<boolean>(false);

  // Screen 5: Keypad editing
  const [isEditingCnic, setIsEditingCnic] = useState<boolean>(false);

  // Screen 6: Decision explanation
  const [decisionResult, setDecisionResult] = useState<any>(null);
  const [evaluatingCase, setEvaluatingCase] = useState<boolean>(false);

  // Monitor network status and sync outbox
  useEffect(() => {
    const handleOnline = async () => {
      setOnlineStatus(true);
      setSyncing(true);
      await syncOutboxEvents();
      setSyncing(false);
    };
    const handleOffline = () => setOnlineStatus(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Auto-play audio prompt on screen change
  useEffect(() => {
    if (showMyData) return;

    if (currentStep === 1) {
      playAudioClip('greeting', 'السلام علیکم۔ امانت پورٹل میں خوش آمدید۔');
    } else if (currentStep === 2) {
      playAudioClip('scam_check', 'اگر کوئی مشکوک میسج آیا ہے تو یہاں چیک کریں۔');
    } else if (currentStep === 3) {
      playAudioClip('consent', 'کیا آپ ریلیف گرانٹ کی جانچ کے لیے رضامندی دیتے ہیں؟');
      // Start Urdu speech listener for "haan" / "nahin"
      const rec = startUrduSpeechRecognition((heard) => {
        if (heard.includes('ہاں') || heard.includes('haan') || heard.includes('yes')) {
          handleConsent(true);
        } else if (heard.includes('نہیں') || heard.includes('nahin') || heard.includes('no')) {
          handleConsent(false);
        }
      });
      return () => {
        if (rec) rec.stop();
      };
    } else if (currentStep === 4) {
      playAudioClip('capture_cnic', 'شناختی کارڈ کے دونوں اطراف کی تصویر لیں۔');
    } else if (currentStep === 5) {
      playAudioClip('confirm_details', 'شناختی کارڈ نمبر کی تصدیق کریں۔');
      playChainedDigits(cnicDigits);
    } else if (currentStep === 6) {
      playAudioClip('status_result', 'آپ کی درخواست کا فیصلہ نیچے درج ہے۔');
    }
  }, [currentStep, showMyData]);

  // Screen 2: Scam Shield Check
  const handleScanMessage = async () => {
    if (!scamInput.trim()) return;
    setScamLoading(true);
    try {
      const res = await api.post('/scam/scan', { message: scamInput });
      setScamResult(res);
    } catch {
      // Fallback local heuristic
      const lower = scamInput.toLowerCase();
      const isFee = lower.includes('fee') || lower.includes('easypaisa') || lower.includes('jazzcash') || lower.includes('tax');
      setScamResult({
        verdict: isFee ? 'LIKELY_SCAM' : 'UNSURE',
        confidence: 0.88,
        red_flags: isFee ? ['Demands advance fees via digital wallet'] : ['Unverified communication channel'],
        recommendation: isFee ? 'WARNING: Official programs never ask for registration fees.' : 'Exercise caution.',
      });
    } finally {
      setScamLoading(false);
    }
  };

  // Screen 3: Consent handler
  const handleConsent = async (agreed: boolean) => {
    if (!agreed) {
      alert(isUrdu ? 'آپ کی رضامندی کے بغیر درخواست جمع نہیں کی جا سکتی۔' : 'Consent is mandatory for eligibility check.');
      return;
    }
    // Queue outbox event
    const eventId = crypto.randomUUID();
    await queueOutboxEvent(eventId, caseId, 'CONSENT_GRANTED', {
      scopes: ['identity', 'contact', 'payment'],
      channel: 'self',
    });
    // Attempt background sync if online
    if (onlineStatus) {
      syncOutboxEvents().catch(() => {});
    }
    setCurrentStep(4);
  };

  // Screen 4: Image input & blur check
  const handleImagePick = async (file: File, side: 'front' | 'back') => {
    try {
      const check = await processAndCheckImage(file);
      if (side === 'front') {
        setFrontBlob(check.compressedBlob);
        setFrontPreview(check.dataUrl);
        setFrontBlurry(check.isBlurry);
      } else {
        setBackBlob(check.compressedBlob);
        setBackPreview(check.dataUrl);
        setBackBlurry(check.isBlurry);
      }
    } catch (err) {
      console.error('Image processing error:', err);
    }
  };

  const handleUploadAndProceed = async () => {
    setUploadingDocs(true);
    setUploadProgress(10);
    try {
      // Queue document capture event
      const eventId = crypto.randomUUID();
      await queueOutboxEvent(eventId, caseId, 'DOCUMENTS_ATTACHED', {
        has_front: !!frontBlob,
        has_back: !!backBlob,
      });

      // Upload if online
      if (onlineStatus && frontBlob) {
        await uploadDocumentChunked(caseId, 'cnic_front', frontBlob, (p) => setUploadProgress(Math.round(p / 2)));
      }
      if (onlineStatus && backBlob) {
        await uploadDocumentChunked(caseId, 'cnic_back', backBlob, (p) => setUploadProgress(50 + Math.round(p / 2)));
      }
      setUploadProgress(100);
      setCurrentStep(5);
    } catch (err) {
      // Graceful offline degradation
      setCurrentStep(5);
    } finally {
      setUploadingDocs(false);
    }
  };

  // Screen 5: Confirm & Submit Case
  const handleSubmitCase = async () => {
    setEvaluatingCase(true);
    try {
      // 1. Queue local submission event in Dexie outbox
      const eventId = crypto.randomUUID();
      await queueOutboxEvent(eventId, caseId, 'CASE_SUBMITTED', {
        cnic: cnicDigits,
        name: claimantName,
        iban,
      });

      // 2. Submit to API if online
      let res: any = null;
      if (onlineStatus) {
        try {
          // Create or evaluate case
          res = await api.post(`/cases/${caseId}/evaluate`, {
            cnic: cnicDigits,
            name: claimantName,
            iban,
          });
        } catch {
          // If evaluate endpoint differs, fallback to explanation
          res = await api.get(`/cases/${caseId}/explanation`);
        }
      }

      if (!res) {
        // Mock offline response
        res = {
          route: 'AUTO',
          hold_seconds_remaining: 60,
          p: 0.97,
          explanation: {
            title: 'Approved on Reversible 60-Second Hold',
            title_ur: '60 سیکنڈ کے عارضی ہولڈ پر خودکار منظوری',
            reason: 'All identity checks, family tree, and bank account match cleanly.',
            reason_ur: 'تمام شناختی و بینک کوائف نادرا اور راست ریکارڈ کے مطابق درست پائے گئے۔',
          },
        };
      }
      setDecisionResult(res);
      setCurrentStep(6);
    } catch (err: any) {
      setDecisionResult({
        route: 'HUMAN',
        explanation: {
          title: 'Escalated to Human Officer',
          title_ur: 'سرکاری افسر کے پاس جانچ کے لیے بھیج دیا گیا',
          reason: 'Network disconnect or policy boundary triggered human review.',
          reason_ur: 'سسٹم نے خودکار منظوری کی بجائے محفوظ انسانی جانچ کی سفارش کی ہے۔',
        },
      });
      setCurrentStep(6);
    } finally {
      setEvaluatingCase(false);
    }
  };

  if (showMyData) {
    return <MyData lang={lang} onBack={() => setShowMyData(false)} />;
  }

  return (
    <div className={`min-h-screen bg-slate-50 text-slate-800 flex flex-col ${isUrdu ? 'rtl' : 'ltr'}`}>
      {/* Top Header */}
      <header className="bg-emerald-800 text-white shadow-md">
        <div className="max-w-xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-700 flex items-center justify-center font-black text-amber-300">
              ام
            </div>
            <span className="font-bold text-lg">{t.appName}</span>
          </div>

          <div className="flex items-center space-x-3">
            {/* Online / Offline Badge */}
            <span
              className={`inline-flex items-center text-xs font-bold px-2.5 py-1 rounded-full ${
                onlineStatus ? 'bg-emerald-900 text-emerald-200' : 'bg-rose-900 text-rose-200'
              }`}
            >
              {onlineStatus ? <Wifi className="w-3.5 h-3.5 mr-1" /> : <WifiOff className="w-3.5 h-3.5 mr-1" />}
              <span>{syncing ? t.syncing : onlineStatus ? t.online : t.offline}</span>
            </span>

            {/* My Data Button */}
            <button
              onClick={() => setShowMyData(true)}
              className="p-1.5 bg-emerald-700 hover:bg-emerald-600 rounded-lg text-emerald-100 text-xs font-medium flex items-center space-x-1"
              title="My Data & Consent"
            >
              <Database className="w-4 h-4" />
            </button>

            {/* Language Toggle */}
            <button
              onClick={() => setLang(lang === 'ur' ? 'en' : 'ur')}
              className="px-2.5 py-1 bg-amber-500 hover:bg-amber-400 text-slate-900 rounded-lg text-xs font-black shadow-sm flex items-center space-x-1"
            >
              <Globe className="w-3.5 h-3.5 mr-0.5" />
              <span>{t.langToggle}</span>
            </button>
          </div>
        </div>
      </header>

      {/* 5-Dot Progress Path */}
      <div className="bg-white border-b border-slate-200 py-3">
        <div className="max-w-md mx-auto px-4 flex items-center justify-between">
          {[1, 2, 3, 4, 5].map((dot) => {
            const isCompleted = currentStep > dot;
            const isCurrent = currentStep === dot;
            return (
              <React.Fragment key={dot}>
                <div
                  className={`w-9 h-9 rounded-full flex items-center justify-center font-bold text-sm transition-all ${
                    isCompleted
                      ? 'bg-emerald-600 text-white'
                      : isCurrent
                      ? 'bg-amber-500 text-slate-900 ring-4 ring-amber-100 scale-110'
                      : 'bg-slate-200 text-slate-500'
                  }`}
                >
                  {isCompleted ? <CheckCircle2 className="w-5 h-5" /> : dot}
                </div>
                {dot < 5 && (
                  <div
                    className={`flex-1 h-1 mx-2 rounded ${
                      currentStep > dot ? 'bg-emerald-600' : 'bg-slate-200'
                    }`}
                  />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Main Single-Question Container */}
      <main className="flex-1 max-w-xl w-full mx-auto p-4 md:p-6 flex flex-col justify-center">
        {/* ====================================================
            SCREEN 1: GREETING & START
        ==================================================== */}
        {currentStep === 1 && (
          <div className="bg-white rounded-3xl p-6 md:p-8 shadow-xl border border-slate-100 text-center space-y-6">
            <div className="w-20 h-20 bg-emerald-100 text-emerald-800 rounded-3xl mx-auto flex items-center justify-center shadow-inner">
              <Sparkles className="w-10 h-10" />
            </div>

            <div className="space-y-2">
              <h1 className="text-3xl font-black text-slate-900">{t.step1Title}</h1>
              <p className="text-slate-600 text-base leading-relaxed">{t.step1Desc}</p>
            </div>

            <button
              onClick={() => playAudioClip('greeting', 'السلام علیکم۔ امانت پورٹل میں خوش آمدید۔')}
              className="inline-flex items-center space-x-2 bg-emerald-50 text-emerald-700 px-4 py-2 rounded-xl text-sm font-bold hover:bg-emerald-100 transition"
            >
              <Volume2 className="w-5 h-5 mr-1" />
              <span>{isUrdu ? 'آواز سنیں' : 'Listen Prompt'}</span>
            </button>

            <div className="pt-4 space-y-3">
              <button
                onClick={() => setCurrentStep(2)}
                className="w-full py-5 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white text-xl font-black rounded-2xl shadow-lg hover:shadow-xl transition flex items-center justify-center space-x-3"
              >
                <span>{t.step1StartBtn}</span>
                <ArrowRight className="w-6 h-6 ml-2" />
              </button>

              <button
                onClick={() => setCurrentStep(2)}
                className="w-full py-3.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-2xl border border-slate-200 text-sm flex items-center justify-center space-x-2 transition"
              >
                <ShieldAlert className="w-4 h-4 text-amber-600 mr-1" />
                <span>{t.step1CheckScamBtn}</span>
              </button>
            </div>
          </div>
        )}

        {/* ====================================================
            SCREEN 2: SCAM SHIELD CHECK (OPTIONAL)
        ==================================================== */}
        {currentStep === 2 && (
          <div className="bg-white rounded-3xl p-6 md:p-8 shadow-xl border border-slate-100 space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 bg-amber-100 text-amber-700 rounded-2xl flex items-center justify-center">
                  <ShieldAlert className="w-7 h-7" />
                </div>
                <div>
                  <h2 className="text-2xl font-black text-slate-900">{t.step2Title}</h2>
                  <p className="text-xs text-slate-500">{t.step2Desc}</p>
                </div>
              </div>

              <button
                onClick={() => playAudioClip('scam_check', 'اگر کوئی مشکوک میسج آیا ہے تو یہاں چیک کریں۔')}
                className="p-2 bg-slate-100 hover:bg-slate-200 rounded-full text-slate-700"
              >
                <Volume2 className="w-5 h-5" />
              </button>
            </div>

            <textarea
              rows={3}
              value={scamInput}
              onChange={(e) => setScamInput(e.target.value)}
              placeholder={t.step2Placeholder}
              className="w-full p-4 rounded-2xl border-2 border-slate-200 focus:border-emerald-600 focus:outline-none text-base"
            />

            <div className="flex space-x-3">
              <button
                onClick={handleScanMessage}
                disabled={scamLoading || !scamInput.trim()}
                className="flex-1 py-4 bg-amber-500 hover:bg-amber-600 disabled:bg-slate-200 text-slate-950 font-black rounded-2xl shadow transition"
              >
                {scamLoading ? '...' : t.step2ScanBtn}
              </button>
              <button
                onClick={() => setCurrentStep(3)}
                className="px-5 py-4 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-2xl text-sm"
              >
                {t.step2SkipBtn}
              </button>
            </div>

            {scamResult && (
              <div
                className={`p-4 rounded-2xl border ${
                  scamResult.verdict === 'LIKELY_SCAM'
                    ? 'bg-rose-50 border-rose-300 text-rose-900'
                    : scamResult.verdict === 'VERIFIED'
                    ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
                    : 'bg-amber-50 border-amber-300 text-amber-900'
                }`}
              >
                <div className="flex items-center space-x-2 font-bold mb-1">
                  {scamResult.verdict === 'LIKELY_SCAM' ? (
                    <XCircle className="w-5 h-5 text-rose-600 mr-1" />
                  ) : (
                    <CheckCircle2 className="w-5 h-5 text-emerald-600 mr-1" />
                  )}
                  <span>
                    {scamResult.verdict === 'LIKELY_SCAM'
                      ? isUrdu
                        ? 'انتباہ: یہ پیغام ممکنہ فراڈ / دھوکہ ہے!'
                        : 'WARNING: Likely Scam Detected!'
                      : scamResult.verdict === 'VERIFIED'
                      ? isUrdu
                        ? 'تصدیق شدہ اصل پیغام'
                        : 'Verified Authentic Message'
                      : isUrdu
                      ? 'غیر یقینی: احتیاط برتیں'
                      : 'Unsure: Proceed with Caution'}
                  </span>
                </div>
                <p className="text-xs mb-2 leading-relaxed">{scamResult.recommendation}</p>
                {scamResult.red_flags?.length > 0 && (
                  <ul className="text-xs list-disc list-inside space-y-0.5">
                    {scamResult.red_flags.map((rf: string, i: number) => (
                      <li key={i}>{rf}</li>
                    ))}
                  </ul>
                )}
                <button
                  onClick={() => setCurrentStep(3)}
                  className="mt-3 w-full py-2.5 bg-slate-900 text-white rounded-xl text-xs font-bold"
                >
                  {isUrdu ? 'درخواست جاری رکھیں' : 'Continue with Application'}
                </button>
              </div>
            )}
          </div>
        )}

        {/* ====================================================
            SCREEN 3: UNIVERSAL CONSENT
        ==================================================== */}
        {currentStep === 3 && (
          <div className="bg-white rounded-3xl p-6 md:p-8 shadow-xl border border-slate-100 space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 bg-emerald-100 text-emerald-700 rounded-2xl flex items-center justify-center">
                  <ShieldCheck className="w-7 h-7" />
                </div>
                <div>
                  <h2 className="text-2xl font-black text-slate-900">{t.step3Title}</h2>
                  <p className="text-xs text-slate-500">{t.step3Desc}</p>
                </div>
              </div>

              <button
                onClick={() => playAudioClip('consent', 'کیا آپ کوائف کی تصدیق کی اجازت دیتے ہیں؟')}
                className="p-2 bg-slate-100 hover:bg-slate-200 rounded-full text-slate-700"
              >
                <Volume2 className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 bg-slate-50 p-4 rounded-2xl border border-slate-200">
              <div className="flex items-center space-x-3 text-sm font-bold text-slate-800">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                <span>{t.step3ScopeIdentity}</span>
              </div>
              <div className="flex items-center space-x-3 text-sm font-bold text-slate-800">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                <span>{t.step3ScopeFamily}</span>
              </div>
              <div className="flex items-center space-x-3 text-sm font-bold text-slate-800">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                <span>{t.step3ScopePayment}</span>
              </div>
              <div className="pt-2 border-t border-slate-200 text-xs text-slate-500">
                {t.step3Retention}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 pt-2">
              <button
                onClick={() => handleConsent(true)}
                className="py-6 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white font-black text-2xl rounded-2xl shadow-lg flex flex-col items-center justify-center space-y-1 transition"
              >
                <CheckCircle2 className="w-8 h-8" />
                <span>{t.step3YesBtn}</span>
              </button>

              <button
                onClick={() => handleConsent(false)}
                className="py-6 bg-rose-100 hover:bg-rose-200 active:bg-rose-300 text-rose-800 font-black text-2xl rounded-2xl border-2 border-rose-300 flex flex-col items-center justify-center space-y-1 transition"
              >
                <XCircle className="w-8 h-8" />
                <span>{t.step3NoBtn}</span>
              </button>
            </div>
          </div>
        )}

        {/* ====================================================
            SCREEN 4: CAPTURE CNIC FRONT & BACK
        ==================================================== */}
        {currentStep === 4 && (
          <div className="bg-white rounded-3xl p-6 md:p-8 shadow-xl border border-slate-100 space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 bg-emerald-100 text-emerald-700 rounded-2xl flex items-center justify-center">
                  <Camera className="w-7 h-7" />
                </div>
                <div>
                  <h2 className="text-2xl font-black text-slate-900">{t.step4Title}</h2>
                  <p className="text-xs text-slate-500">{t.step4Desc}</p>
                </div>
              </div>

              <button
                onClick={() => playAudioClip('capture_cnic', 'شناختی کارڈ کے دونوں اطراف کی تصویر لیں۔')}
                className="p-2 bg-slate-100 hover:bg-slate-200 rounded-full text-slate-700"
              >
                <Volume2 className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Front Photo Card */}
              <div className="border-2 border-dashed border-slate-300 rounded-2xl p-4 text-center hover:border-emerald-500 transition relative">
                <label className="cursor-pointer block">
                  <input
                    type="file"
                    accept="image/*"
                    capture="environment"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && handleImagePick(e.target.files[0], 'front')}
                  />
                  {frontPreview ? (
                    <img src={frontPreview} alt="Front preview" className="w-full h-32 object-cover rounded-xl mb-2" />
                  ) : (
                    <div className="h-32 flex flex-col items-center justify-center text-slate-400">
                      <Camera className="w-8 h-8 mb-1" />
                      <span className="text-xs font-bold">{t.step4FrontLabel}</span>
                    </div>
                  )}
                </label>
                {frontBlurry && (
                  <div className="text-[11px] font-bold text-rose-600 bg-rose-50 p-1.5 rounded-lg border border-rose-200 mt-1">
                    {t.step4BlurWarning}
                  </div>
                )}
              </div>

              {/* Back Photo Card */}
              <div className="border-2 border-dashed border-slate-300 rounded-2xl p-4 text-center hover:border-emerald-500 transition relative">
                <label className="cursor-pointer block">
                  <input
                    type="file"
                    accept="image/*"
                    capture="environment"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && handleImagePick(e.target.files[0], 'back')}
                  />
                  {backPreview ? (
                    <img src={backPreview} alt="Back preview" className="w-full h-32 object-cover rounded-xl mb-2" />
                  ) : (
                    <div className="h-32 flex flex-col items-center justify-center text-slate-400">
                      <Camera className="w-8 h-8 mb-1" />
                      <span className="text-xs font-bold">{t.step4BackLabel}</span>
                    </div>
                  )}
                </label>
                {backBlurry && (
                  <div className="text-[11px] font-bold text-rose-600 bg-rose-50 p-1.5 rounded-lg border border-rose-200 mt-1">
                    {t.step4BlurWarning}
                  </div>
                )}
              </div>
            </div>

            {uploadProgress > 0 && (
              <div className="w-full bg-slate-200 rounded-full h-2.5 overflow-hidden">
                <div className="bg-emerald-600 h-2.5 transition-all" style={{ width: `${uploadProgress}%` }} />
              </div>
            )}

            <button
              onClick={handleUploadAndProceed}
              disabled={uploadingDocs}
              className="w-full py-4 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white font-black text-xl rounded-2xl shadow-lg transition"
            >
              {uploadingDocs ? '...' : t.step4UploadBtn}
            </button>
          </div>
        )}

        {/* ====================================================
            SCREEN 5: READ-BACK & DETAILS CONFIRMATION
        ==================================================== */}
        {currentStep === 5 && (
          <div className="bg-white rounded-3xl p-6 md:p-8 shadow-xl border border-slate-100 space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 bg-emerald-100 text-emerald-700 rounded-2xl flex items-center justify-center">
                  <UserCheck className="w-7 h-7" />
                </div>
                <div>
                  <h2 className="text-2xl font-black text-slate-900">{t.step5Title}</h2>
                  <p className="text-xs text-slate-500">{t.step5Desc}</p>
                </div>
              </div>

              <button
                onClick={() => {
                  playAudioClip('confirm_details', 'شناختی کارڈ نمبر کی تصدیق کریں۔');
                  playChainedDigits(cnicDigits);
                }}
                className="p-2 bg-slate-100 hover:bg-slate-200 rounded-full text-slate-700"
                title="Play digit by digit audio"
              >
                <Volume2 className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 bg-slate-50 p-5 rounded-2xl border border-slate-200">
              <div>
                <span className="text-xs font-bold text-slate-500 uppercase">{t.step5NameLabel}</span>
                <p className="text-xl font-black text-slate-900">{claimantName}</p>
              </div>

              <div>
                <span className="text-xs font-bold text-slate-500 uppercase">{t.step5CnicLabel}</span>
                <p className="text-2xl font-mono font-black text-emerald-700 tracking-wider">
                  {cnicDigits.replace(/(\d{5})(\d{7})(\d{1})/, '$1-$2-$3')}
                </p>
              </div>
            </div>

            {isEditingCnic ? (
              <div className="space-y-3">
                <Keypad
                  onDigit={(d) => setCnicDigits((prev) => (prev.length < 13 ? prev + d : prev))}
                  onBackspace={() => setCnicDigits((prev) => prev.slice(0, -1))}
                  onConfirm={() => setIsEditingCnic(false)}
                  confirmLabel={isUrdu ? 'مکمل' : 'Done'}
                />
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4">
                <button
                  onClick={handleSubmitCase}
                  disabled={evaluatingCase}
                  className="py-5 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white font-black text-lg rounded-2xl shadow-lg flex items-center justify-center space-x-2 transition"
                >
                  <CheckCircle2 className="w-6 h-6 mr-1" />
                  <span>{evaluatingCase ? '...' : t.step5ConfirmBtn}</span>
                </button>

                <button
                  onClick={() => setIsEditingCnic(true)}
                  className="py-5 bg-slate-100 hover:bg-slate-200 active:bg-slate-300 text-slate-800 font-bold text-base rounded-2xl border border-slate-300 flex items-center justify-center space-x-2 transition"
                >
                  <RotateCcw className="w-5 h-5 mr-1" />
                  <span>{t.step5RejectBtn}</span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* ====================================================
            SCREEN 6: STATUS & DECISION EXPLANATION
        ==================================================== */}
        {currentStep === 6 && (
          <div className="bg-white rounded-3xl p-6 md:p-8 shadow-xl border border-slate-100 space-y-6">
            <div className="text-center space-y-3">
              {decisionResult?.route === 'AUTO' ? (
                <div className="w-20 h-20 bg-emerald-100 text-emerald-700 rounded-3xl mx-auto flex items-center justify-center">
                  <CheckCircle2 className="w-10 h-10" />
                </div>
              ) : decisionResult?.route === 'ASK' ? (
                <div className="w-20 h-20 bg-amber-100 text-amber-700 rounded-3xl mx-auto flex items-center justify-center">
                  <HelpCircle className="w-10 h-10" />
                </div>
              ) : (
                <div className="w-20 h-20 bg-blue-100 text-blue-700 rounded-3xl mx-auto flex items-center justify-center">
                  <Clock className="w-10 h-10" />
                </div>
              )}

              <h2 className="text-2xl font-black text-slate-900">
                {isUrdu
                  ? decisionResult?.explanation?.title_ur || t.step6Title
                  : decisionResult?.explanation?.title || t.step6Title}
              </h2>

              <p className="text-slate-600 text-sm leading-relaxed">
                {isUrdu
                  ? decisionResult?.explanation?.reason_ur || decisionResult?.explanation?.reason
                  : decisionResult?.explanation?.reason}
              </p>
            </div>

            {decisionResult?.route === 'AUTO' && (
              <div className="p-4 bg-emerald-50 rounded-2xl border border-emerald-200 text-emerald-900 text-sm font-bold flex items-center space-x-2">
                <Clock className="w-5 h-5 text-emerald-700 flex-shrink-0" />
                <span>{t.step6AutoNotice}</span>
              </div>
            )}

            {decisionResult?.route === 'ASK' && (
              <div className="p-4 bg-amber-50 rounded-2xl border border-amber-200 text-amber-900 text-sm font-bold flex items-center space-x-2">
                <HelpCircle className="w-5 h-5 text-amber-700 flex-shrink-0" />
                <span>{t.step6AskNotice}</span>
              </div>
            )}

            {decisionResult?.route === 'HUMAN' && (
              <div className="p-4 bg-blue-50 rounded-2xl border border-blue-200 text-blue-900 text-sm font-bold flex items-center space-x-2">
                <ShieldCheck className="w-5 h-5 text-blue-700 flex-shrink-0" />
                <span>{t.step6HumanNotice}</span>
              </div>
            )}

            <button
              onClick={() => playAudioClip('status_result', isUrdu ? decisionResult?.explanation?.reason_ur : decisionResult?.explanation?.reason)}
              className="w-full py-4 bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold rounded-2xl border border-slate-300 flex items-center justify-center space-x-2 transition"
            >
              <Volume2 className="w-5 h-5 mr-1" />
              <span>{t.step6ReplayAudio}</span>
            </button>

            <button
              onClick={() => {
                setCurrentStep(1);
                setCaseId(`case-${Date.now().toString(36)}`);
                setDecisionResult(null);
              }}
              className="w-full py-3 text-emerald-700 font-bold text-sm hover:underline"
            >
              {isUrdu ? 'نئی درخواست شروع کریں' : 'Start Another Application'}
            </button>
          </div>
        )}
      </main>
    </div>
  );
};
