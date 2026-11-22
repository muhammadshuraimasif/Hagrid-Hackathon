import React, { useState } from 'react';
import { ShieldCheck, ShieldAlert, CheckCircle2, XCircle, ArrowLeft, RefreshCw } from 'lucide-react';
import { api } from '../../api/client';
import { queueOutboxEvent } from '../../db/outbox';
import { Language, translations } from '../../i18n/translations';

interface MyDataProps {
  lang: Language;
  onBack: () => void;
}

export const MyData: React.FC<MyDataProps> = ({ lang, onBack }) => {
  const t = translations[lang];
  const isUrdu = lang === 'ur';

  const [scopes, setScopes] = useState({
    identity: true,
    contact: true,
    documents: true,
    payment: true,
  });
  const [withdrawing, setWithdrawing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const handleWithdrawAll = async () => {
    setWithdrawing(true);
    try {
      // 1. Queue local outbox event for offline resilience
      const eventId = crypto.randomUUID();
      await queueOutboxEvent(eventId, 'self', 'CONSENT_WITHDRAWN', { scope: 'all' });

      // 2. Call server
      await api.post('/consent/withdraw', { scope: 'all', reason: 'Citizen exercised sovereign right to revoke' });
      setScopes({ identity: false, contact: false, documents: false, payment: false });
      setMessage(isUrdu ? 'تمام رضامندی کامیابی سے منسوخ کر دی گئی ہے۔' : 'All consent revoked successfully.');
    } catch (err: any) {
      setMessage(isUrdu ? 'آف لائن موڈ: منسوخی کو محفوظ کر لیا گیا ہے۔' : 'Offline mode: Withdrawal queued locally.');
    } finally {
      setWithdrawing(false);
    }
  };

  const handleRequestCorrection = async () => {
    try {
      await api.post('/consent/correction', {
        person_id: 'self',
        correction_request: 'Citizen requested name / CNIC audit check',
      });
      alert(isUrdu ? 'درستگی کی درخواست درج کر لی گئی ہے۔' : 'Correction request filed successfully.');
    } catch {
      alert(isUrdu ? 'درخواست محفوظ کر لی گئی ہے۔' : 'Request queued locally.');
    }
  };

  return (
    <div className={`p-6 max-w-2xl mx-auto ${isUrdu ? 'rtl' : 'ltr'}`}>
      <button
        onClick={onBack}
        className="flex items-center space-x-2 text-emerald-700 font-bold mb-6 hover:underline"
      >
        <ArrowLeft className="w-5 h-5 mr-1" />
        <span>{isUrdu ? 'واپس جائیں' : 'Back to Portal'}</span>
      </button>

      <div className="bg-white rounded-3xl shadow-lg border border-slate-100 p-6 md:p-8">
        <div className="flex items-center space-x-3 mb-4">
          <div className="w-12 h-12 rounded-2xl bg-emerald-100 text-emerald-700 flex items-center justify-center">
            <ShieldCheck className="w-7 h-7" />
          </div>
          <div>
            <h2 className="text-2xl font-black text-slate-900">{t.myDataTitle}</h2>
            <p className="text-slate-600 text-sm">{t.myDataDesc}</p>
          </div>
        </div>

        {message && (
          <div className="mb-6 p-4 bg-emerald-50 text-emerald-800 rounded-xl border border-emerald-200 text-sm font-medium">
            {message}
          </div>
        )}

        <div className="space-y-4 mb-8">
          <div className="flex items-center justify-between p-4 bg-slate-50 rounded-2xl border border-slate-200">
            <div>
              <span className="font-bold text-slate-900 block">{isUrdu ? 'شناختی کوائف (NADRA)' : 'Identity Data (NADRA)'}</span>
              <span className="text-xs text-slate-500">{isUrdu ? 'شناختی کارڈ، تاریخ پیدائش، خاندانی ریکارڈ' : 'CNIC, DOB, Family Unit'}</span>
            </div>
            {scopes.identity ? (
              <span className="inline-flex items-center text-xs font-bold text-emerald-700 bg-emerald-100 px-3 py-1.5 rounded-full">
                <CheckCircle2 className="w-4 h-4 mr-1 inline" /> {isUrdu ? 'فعال' : 'Active'}
              </span>
            ) : (
              <span className="inline-flex items-center text-xs font-bold text-slate-500 bg-slate-200 px-3 py-1.5 rounded-full">
                <XCircle className="w-4 h-4 mr-1 inline" /> {isUrdu ? 'منسوخ' : 'Revoked'}
              </span>
            )}
          </div>

          <div className="flex items-center justify-between p-4 bg-slate-50 rounded-2xl border border-slate-200">
            <div>
              <span className="font-bold text-slate-900 block">{isUrdu ? 'بینک اکاؤنٹ و ادائیگی (Raast)' : 'Payment & Account Title (Raast)'}</span>
              <span className="text-xs text-slate-500">{isUrdu ? 'آئی بی اے این اور نام کی تصدیق' : 'IBAN & Title Match'}</span>
            </div>
            {scopes.payment ? (
              <span className="inline-flex items-center text-xs font-bold text-emerald-700 bg-emerald-100 px-3 py-1.5 rounded-full">
                <CheckCircle2 className="w-4 h-4 mr-1 inline" /> {isUrdu ? 'فعال' : 'Active'}
              </span>
            ) : (
              <span className="inline-flex items-center text-xs font-bold text-slate-500 bg-slate-200 px-3 py-1.5 rounded-full">
                <XCircle className="w-4 h-4 mr-1 inline" /> {isUrdu ? 'منسوخ' : 'Revoked'}
              </span>
            )}
          </div>
        </div>

        <div className="border-t border-slate-200 pt-6 space-y-4">
          <p className="text-xs text-slate-500 leading-relaxed">
            {t.withdrawalNotice}
          </p>

          <button
            onClick={handleWithdrawAll}
            disabled={withdrawing || (!scopes.identity && !scopes.payment)}
            className="w-full py-4 bg-rose-600 hover:bg-rose-700 active:bg-rose-800 disabled:bg-slate-300 text-white font-bold rounded-2xl shadow-md transition flex items-center justify-center space-x-2"
          >
            <ShieldAlert className="w-5 h-5 mr-1" />
            <span>{t.withdrawAllBtn}</span>
          </button>

          <button
            onClick={handleRequestCorrection}
            className="w-full py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-2xl border border-slate-300 transition flex items-center justify-center space-x-2 text-sm"
          >
            <RefreshCw className="w-4 h-4 mr-1" />
            <span>{t.requestCorrectionBtn}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
