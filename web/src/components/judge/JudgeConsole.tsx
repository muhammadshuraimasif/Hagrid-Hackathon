import React, { useState } from 'react';
import { CitizenPortal } from '../citizen/CitizenPortal';
import { BackOfficeSuite } from '../backoffice/BackOfficeSuite';
import {
  LayoutDashboard,
  PlayCircle,
  Clock
} from 'lucide-react';

export const JudgeConsole: React.FC = () => {
  const [activeScenario, setActiveScenario] = useState<string | null>(null);
  const [holdCountdown, setHoldCountdown] = useState<number | null>(null);
  const [scenarioNotice, setScenarioNotice] = useState<string | null>(null);

  const scenarios = [
    {
      id: 'clean_auto',
      label: '1. Clean Case (AUTO 60s Hold)',
      desc: 'All checks pass -> Approved onto reversible 60-second hold.',
      color: 'bg-emerald-600 hover:bg-emerald-700',
    },
    {
      id: 'scam_account',
      label: '2. Scammer Account (HUMAN)',
      desc: 'Raast account title mismatch -> Hard guard fails closed to HUMAN.',
      color: 'bg-rose-600 hover:bg-rose-700',
    },
    {
      id: 'edited_cnic',
      label: '3. Forged CNIC (HUMAN)',
      desc: 'ELA forensics detects spliced text -> routes to Officer with suspect boxes.',
      color: 'bg-amber-600 hover:bg-amber-700',
    },
    {
      id: 'name_variant',
      label: '4. Name Variant (AUTO)',
      desc: 'Muhammad vs Mohammad resolved by fuzzy phonetics -> passes.',
      color: 'bg-teal-600 hover:bg-teal-700',
    },
    {
      id: 'service_down',
      label: '5. Service Down (WAITING)',
      desc: 'NADRA 503 outage -> WAITING_FOR_SERVICE queue. No decision made.',
      color: 'bg-slate-700 hover:bg-slate-800',
    },
  ];

  const handleTriggerScenario = (sc: any) => {
    setActiveScenario(sc.id);
    if (sc.id === 'clean_auto' || sc.id === 'name_variant') {
      setHoldCountdown(60);
      setScenarioNotice(`Seeded "${sc.label}". Case placed on 60-second reversible hold.`);
    } else if (sc.id === 'service_down') {
      setHoldCountdown(null);
      setScenarioNotice(`Seeded "${sc.label}". Service failure detected. Case placed in WAITING_FOR_SERVICE.`);
    } else {
      setHoldCountdown(null);
      setScenarioNotice(`Seeded "${sc.label}". Hard guard triggered. Context packet dispatched to Officer Queue.`);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col font-sans">
      {/* Judge Control Ribbon */}
      <div className="bg-slate-800 border-b border-slate-700 px-6 py-3 flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="font-black text-amber-400 text-sm tracking-wider flex items-center space-x-2">
            <LayoutDashboard className="w-4 h-4 mr-1 text-amber-400" />
            <span>JUDGE DEMONSTRATION CONSOLE (DUAL VIEW)</span>
          </span>
          <span className="text-slate-400 text-[11px] block">
            Left: Accessible Mobile Citizen PWA | Right: Operational Back-Office & Audits
          </span>
        </div>

        {/* 60-Second Hold Indicator */}
        {holdCountdown !== null && (
          <div className="flex items-center space-x-2 bg-emerald-950 border border-emerald-500/50 px-3 py-1.5 rounded-xl text-xs">
            <Clock className="w-4 h-4 text-emerald-400 animate-pulse" />
            <span className="font-bold text-emerald-200">Reversible Release Hold:</span>
            <span className="font-mono font-black text-amber-300 text-sm">{holdCountdown}s</span>
            <button
              onClick={() => setHoldCountdown(0)}
              className="ml-2 px-2 py-0.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-[10px] font-bold"
            >
              Release Now
            </button>
            <button
              onClick={() => {
                setHoldCountdown(null);
                setScenarioNotice('Officer reversed the hold before the 60s window expired.');
              }}
              className="px-2 py-0.5 bg-rose-700 hover:bg-rose-600 text-white rounded text-[10px] font-bold"
            >
              Reverse Hold
            </button>
          </div>
        )}
      </div>

      {/* One-Click Scenario Buttons from Blueprint 12.4 */}
      <div className="bg-slate-950 px-6 py-2.5 border-b border-slate-800 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-slate-400 font-bold flex items-center mr-1">
          <PlayCircle className="w-3.5 h-3.5 mr-1 text-amber-400" /> Seed Scenario:
        </span>
        {scenarios.map((sc) => (
          <button
            key={sc.id}
            onClick={() => handleTriggerScenario(sc)}
            className={`px-3 py-1.5 rounded-lg text-white font-bold transition shadow-sm ${sc.color} ${
              activeScenario === sc.id ? 'ring-2 ring-amber-400' : ''
            }`}
          >
            {sc.label}
          </button>
        ))}
      </div>

      {scenarioNotice && (
        <div className="bg-amber-950/80 border-b border-amber-600/50 px-6 py-2 text-xs text-amber-200 font-bold flex items-center justify-between">
          <span>{scenarioNotice}</span>
          <button onClick={() => setScenarioNotice(null)} className="text-amber-400 hover:underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Dual Split Screen */}
      <div className="flex-1 grid grid-cols-1 xl:grid-cols-12 gap-0 overflow-hidden">
        {/* Left Side: Mobile Phone Frame */}
        <div className="xl:col-span-5 bg-slate-900 p-6 flex flex-col items-center justify-start border-r border-slate-800 overflow-y-auto">
          <div className="w-full max-w-[400px]">
            {/* Phone Bezel */}
            <div className="border-[10px] border-slate-800 rounded-[44px] shadow-2xl overflow-hidden bg-slate-50 relative">
              {/* Phone Speaker Notch */}
              <div className="h-6 bg-slate-800 flex items-center justify-center">
                <div className="w-16 h-3 bg-slate-900 rounded-full" />
              </div>

              {/* Citizen PWA Inside Phone Frame */}
              <div className="h-[740px] overflow-y-auto">
                <CitizenPortal />
              </div>

              {/* Phone Home Indicator Bar */}
              <div className="h-4 bg-slate-800 flex items-center justify-center">
                <div className="w-28 h-1 bg-slate-600 rounded-full" />
              </div>
            </div>
          </div>
        </div>

        {/* Right Side: Back-Office Suite */}
        <div className="xl:col-span-7 bg-slate-100 overflow-y-auto">
          <BackOfficeSuite />
        </div>
      </div>
    </div>
  );
};
