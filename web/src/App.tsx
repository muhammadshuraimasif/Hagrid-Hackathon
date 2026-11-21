import React from 'react';

export default function App() {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      {/* Universal Mandatory Prototype Banner */}
      <header className="bg-amber-500 text-black px-4 py-2 text-center font-bold tracking-wide uppercase shadow-sm">
        ⚠️ PROTOTYPE ONLY — Hagrid&apos;s Hackathon &apos;26 — Synthetic Data Only
      </header>

      <main className="flex-1 max-w-4xl mx-auto w-full p-6 flex flex-col items-center justify-center text-center">
        <h1 className="text-4xl font-extrabold text-slate-800 mb-4 tracking-tight">
          Project Amaanat (امانت)
        </h1>
        <p className="text-lg text-slate-600 max-w-xl mb-6">
          AI on Public Rails: Transparent, fail-closed DPI relief assistance prototype for Pakistan.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full text-left">
          <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-sm">
            <h2 className="font-semibold text-slate-800 mb-1">Citizen Portal</h2>
            <p className="text-sm text-slate-500">Voice-and-icon claims, offline queue, plain-language Urdu status.</p>
          </div>
          <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-sm">
            <h2 className="font-semibold text-slate-800 mb-1">Officer Queue</h2>
            <p className="text-sm text-slate-500">Fail-closed human hand-offs with full context packets.</p>
          </div>
          <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-sm">
            <h2 className="font-semibold text-slate-800 mb-1">Auditor & Twin</h2>
            <p className="text-sm text-slate-500">Hash-chained audit log & live rule sandbox simulations.</p>
          </div>
        </div>
      </main>

      <footer className="text-center py-4 text-xs text-slate-400">
        Amaanat Prototype · Zero Real Personal Data · Three Exits: AUTO / ASK / HUMAN
      </footer>
    </div>
  );
}
