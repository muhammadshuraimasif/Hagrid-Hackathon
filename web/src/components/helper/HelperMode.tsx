import React, { useState, useEffect } from 'react';
import { Keypad } from '../common/Keypad';
import { playAudioClip } from '../../utils/audio';
import {
  Users,
  ShieldCheck,
  ShieldAlert,
  Lock,
  ArrowRight,
  LogOut
} from 'lucide-react';

interface FamilyCard {
  id: string;
  name: string;
  head_cnic: string;
  members: number;
  status: 'ELIGIBLE' | 'APPROVED' | 'NEEDS_INFO' | 'CONSENT_REVOKED';
  has_active_grant: boolean;
}

export const HelperMode: React.FC = () => {
  const [families] = useState<FamilyCard[]>([
    {
      id: 'fam-01',
      name: 'Tariq Family (طارق خاندان)',
      head_cnic: '42101-1000001-1',
      members: 5,
      status: 'APPROVED',
      has_active_grant: true,
    },
    {
      id: 'fam-02',
      name: 'Akram Family (اکرم خاندان)',
      head_cnic: '42101-2000002-2',
      members: 6,
      status: 'NEEDS_INFO',
      has_active_grant: false,
    },
    {
      id: 'fam-03',
      name: 'Bibi Family (بی بی خاندان)',
      head_cnic: '42101-3000003-3',
      members: 4,
      status: 'CONSENT_REVOKED',
      has_active_grant: false,
    },
  ]);

  const [activeFamily, setActiveFamily] = useState<FamilyCard | null>(null);
  const [pinEntryFamily, setPinEntryFamily] = useState<FamilyCard | null>(null);
  const [enteredPin, setEnteredPin] = useState<string>('');
  const [actingToken, setActingToken] = useState<string | null>(null);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  // Auto idle timeout (return to helper home after 2 minutes)
  useEffect(() => {
    if (!activeFamily) return;
    const timer = setTimeout(() => {
      handleSwitchFamily();
    }, 120000);
    return () => clearTimeout(timer);
  }, [activeFamily]);

  const handleSelectFamily = (family: FamilyCard) => {
    setErrorNotice(null);
    if (family.status === 'CONSENT_REVOKED') {
      setErrorNotice('HTTP 403 Forbidden: Citizen has withdrawn consent. Helper access is strictly blocked.');
      return;
    }

    if (!family.has_active_grant) {
      // Require 4-digit PIN or spoken phrase consent
      setPinEntryFamily(family);
      setEnteredPin('');
      return;
    }

    // Switch family: clear previous state and issue acting token
    switchActingContext(family);
  };

  const switchActingContext = (family: FamilyCard) => {
    // 1. Wipe previous local family data
    setEnteredPin('');
    setPinEntryFamily(null);

    // 2. Set new acting token
    const mockActingToken = `act-${family.id}-${Date.now()}`;
    setActingToken(mockActingToken);
    setActiveFamily(family);

    // 3. Play spoken receipt
    playAudioClip('consent', 'رضامندی کی تصدیق ہو گئی ہے۔');
  };

  const handleConfirmPin = () => {
    if (enteredPin.length < 4 || !pinEntryFamily) return;
    // Mark grant as active
    pinEntryFamily.has_active_grant = true;
    switchActingContext(pinEntryFamily);
  };

  const handleSwitchFamily = () => {
    // Clear acting context & on-screen data
    setActiveFamily(null);
    setActingToken(null);
    setErrorNotice(null);
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans">
      {/* Coloured "ACTING FOR" Banner (Mandatory when active) */}
      {activeFamily && (
        <div className="bg-teal-600 text-white px-6 py-2.5 shadow-md flex items-center justify-between text-xs font-bold animate-pulse">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-amber-300" />
            <span className="uppercase tracking-wider">
              ACTING FOR: <span className="underline font-black">{activeFamily.name}</span> (CNIC: {activeFamily.head_cnic})
            </span>
            <span className="text-teal-200">| Token: {actingToken?.slice(0, 16)}...</span>
          </div>

          <button
            onClick={handleSwitchFamily}
            className="px-3 py-1 bg-teal-800 hover:bg-teal-900 text-white rounded-lg flex items-center space-x-1"
          >
            <LogOut className="w-3.5 h-3.5 mr-1" />
            <span>End Session & Wipe Local Cache</span>
          </button>
        </div>
      )}

      {/* Main Container */}
      <div className="max-w-4xl mx-auto w-full p-6 space-y-6">
        {/* Header */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black text-slate-900 flex items-center space-x-2">
              <Users className="w-7 h-7 text-teal-600 mr-2" />
              <span>Community Helper Mode (Shared Device Assistance)</span>
            </h1>
            <p className="text-slate-500 text-xs mt-1">
              Assist low-literacy neighbours with explicit PIN or voice delegation. Auto-wipes cache between families.
            </p>
          </div>
          <span className="px-3 py-1 bg-teal-100 text-teal-900 rounded-full font-bold text-xs">
            Role: Authorized Helper
          </span>
        </div>

        {errorNotice && (
          <div className="p-4 bg-rose-50 border border-rose-300 text-rose-900 rounded-xl text-xs font-bold flex items-center space-x-2">
            <ShieldAlert className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <span>{errorNotice}</span>
          </div>
        )}

        {/* 1. PIN or Voice Consent Entry Modal */}
        {pinEntryFamily && (
          <div className="bg-white p-6 rounded-3xl shadow-xl border border-slate-200 max-w-md mx-auto space-y-6 text-center">
            <div className="w-16 h-16 bg-teal-100 text-teal-700 rounded-2xl mx-auto flex items-center justify-center">
              <Lock className="w-8 h-8" />
            </div>

            <div>
              <h3 className="text-xl font-black text-slate-900">Citizen Consent Delegation</h3>
              <p className="text-xs text-slate-500 mt-1">
                Enter head of household 4-digit PIN or speak consent phrase to authorize helper assistance for{' '}
                <span className="font-bold text-slate-800">{pinEntryFamily.name}</span>.
              </p>
            </div>

            {/* PIN Display */}
            <div className="flex justify-center space-x-3">
              {[0, 1, 2, 3].map((idx) => (
                <div
                  key={idx}
                  className="w-12 h-14 bg-slate-50 border-2 border-slate-300 rounded-xl flex items-center justify-center font-mono text-2xl font-black"
                >
                  {enteredPin[idx] ? '•' : ''}
                </div>
              ))}
            </div>

            {/* Large On-Screen Keypad */}
            <Keypad
              onDigit={(d) => setEnteredPin((prev) => (prev.length < 4 ? prev + d : prev))}
              onBackspace={() => setEnteredPin((prev) => prev.slice(0, -1))}
              onConfirm={handleConfirmPin}
              confirmLabel="Authorize"
            />

            <button
              onClick={() => setPinEntryFamily(null)}
              className="text-xs font-bold text-slate-400 hover:text-slate-600"
            >
              Cancel
            </button>
          </div>
        )}

        {/* 2. Active Family Claim Workspace */}
        {activeFamily && !pinEntryFamily && (
          <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-200 space-y-6">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <span className="text-xs font-bold text-teal-600 uppercase">Current Assisted Claimant</span>
                <h2 className="text-2xl font-black text-slate-900">{activeFamily.name}</h2>
                <span className="font-mono text-xs text-slate-500">CNIC: {activeFamily.head_cnic}</span>
              </div>
              <span className="px-3 py-1 bg-emerald-100 text-emerald-800 rounded-full font-bold text-xs">
                {activeFamily.status}
              </span>
            </div>

            <div className="p-4 bg-teal-50 rounded-2xl border border-teal-200 text-teal-900 text-xs font-semibold space-y-1">
              <span className="font-bold block">✓ Spoken Audio Receipt Dispatched:</span>
              <p>
                The citizen has granted a temporary 15-minute delegation token for flood relief assistance.
                Local cache will be automatically sanitized upon switching claimants.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <button
                onClick={() => alert('Launching Camera capture in helper mode...')}
                className="py-4 bg-teal-600 hover:bg-teal-700 text-white font-bold rounded-2xl shadow text-sm"
              >
                Scan CNIC on Helper Camera
              </button>

              <button
                onClick={handleSwitchFamily}
                className="py-4 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-2xl border border-slate-300 text-sm"
              >
                Finish & Switch Family
              </button>
            </div>
          </div>
        )}

        {/* 3. Family Picture Cards Selection */}
        {!activeFamily && !pinEntryFamily && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold uppercase text-slate-500">Select Assisted Family:</h3>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {families.map((fam) => (
                <div
                  key={fam.id}
                  onClick={() => handleSelectFamily(fam)}
                  className={`p-5 bg-white rounded-3xl shadow-sm border border-slate-200 hover:border-teal-500 cursor-pointer transition space-y-4 ${
                    fam.status === 'CONSENT_REVOKED' ? 'opacity-60 bg-slate-50' : ''
                  }`}
                >
                  {/* Family Avatar Box */}
                  <div className="w-14 h-14 bg-teal-100 text-teal-800 rounded-2xl flex items-center justify-center font-black text-xl">
                    {fam.name[0]}
                  </div>

                  <div>
                    <h4 className="font-black text-slate-900 text-base">{fam.name}</h4>
                    <p className="font-mono text-xs text-slate-500">{fam.head_cnic}</p>
                    <p className="text-xs text-slate-400 mt-1">{fam.members} family members</p>
                  </div>

                  <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                    <span
                      className={`font-bold px-2 py-0.5 rounded-full text-[10px] ${
                        fam.status === 'APPROVED'
                          ? 'bg-emerald-100 text-emerald-800'
                          : fam.status === 'CONSENT_REVOKED'
                          ? 'bg-rose-100 text-rose-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {fam.status}
                    </span>
                    <ArrowRight className="w-4 h-4 text-slate-400" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
