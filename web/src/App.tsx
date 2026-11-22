import { useState } from 'react';
import { PrototypeBadge } from './components/common/PrototypeBadge';
import { CitizenPortal } from './components/citizen/CitizenPortal';
import { BackOfficeSuite } from './components/backoffice/BackOfficeSuite';
import { JudgeConsole } from './components/judge/JudgeConsole';
import { HelperMode } from './components/helper/HelperMode';
import { Users, FileText, Gavel, HandHelping } from 'lucide-react';

export type AppView = 'citizen' | 'backoffice' | 'judge' | 'helper';

export default function App() {
  const [view, setView] = useState<AppView>('citizen');

  return (
    <div className="min-h-screen flex flex-col bg-slate-100 font-sans">
      {/* 1. Mandatory Uncompromising Prototype Banner */}
      <PrototypeBadge />

      {/* 2. Top Portal View Switcher Bar */}
      <div className="bg-slate-900 text-white text-xs px-4 py-2 flex items-center justify-between border-b border-slate-800">
        <div className="flex items-center space-x-2">
          <span className="font-black text-amber-400 text-sm">AMAANAT</span>
          <span className="text-slate-400">|</span>
          <span className="text-slate-300">DPI Relief Grant System (Prototype)</span>
        </div>

        <nav className="flex items-center space-x-1 sm:space-x-2">
          <button
            onClick={() => setView('citizen')}
            className={`px-3 py-1.5 rounded-lg font-bold flex items-center space-x-1 transition ${
              view === 'citizen' ? 'bg-emerald-600 text-white' : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Users className="w-3.5 h-3.5 mr-1" />
            <span>Citizen Claim</span>
          </button>

          <button
            onClick={() => setView('backoffice')}
            className={`px-3 py-1.5 rounded-lg font-bold flex items-center space-x-1 transition ${
              view === 'backoffice' ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <FileText className="w-3.5 h-3.5 mr-1" />
            <span>Back-Office</span>
          </button>

          <button
            onClick={() => setView('judge')}
            className={`px-3 py-1.5 rounded-lg font-bold flex items-center space-x-1 transition ${
              view === 'judge' ? 'bg-amber-600 text-white' : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Gavel className="w-3.5 h-3.5 mr-1" />
            <span>Judge Console</span>
          </button>

          <button
            onClick={() => setView('helper')}
            className={`px-3 py-1.5 rounded-lg font-bold flex items-center space-x-1 transition ${
              view === 'helper' ? 'bg-teal-600 text-white' : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <HandHelping className="w-3.5 h-3.5 mr-1" />
            <span>Helper Mode</span>
          </button>
        </nav>
      </div>

      {/* 3. Main Dynamic Content */}
      <div className="flex-1">
        {view === 'citizen' && <CitizenPortal />}
        {view === 'backoffice' && <BackOfficeSuite />}
        {view === 'judge' && <JudgeConsole />}
        {view === 'helper' && <HelperMode />}
      </div>

      {/* Footer */}
      <footer className="bg-slate-900 text-slate-400 text-center py-2 text-[11px] border-t border-slate-800">
        Project Amaanat (امانت) — Hagrid&apos;s Hackathon 2026 — Fail Closed to HUMAN — Zero Real Personal Data
      </footer>
    </div>
  );
}
