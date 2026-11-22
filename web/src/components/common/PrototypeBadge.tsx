import React from 'react';

export const PrototypeBadge: React.FC = () => {
  return (
    <div className="bg-amber-500 text-slate-900 text-xs font-bold uppercase tracking-wider py-1 px-4 text-center shadow-sm flex items-center justify-center space-x-2">
      <span className="bg-slate-900 text-amber-400 px-1.5 py-0.5 rounded text-[10px]">PROTOTYPE</span>
      <span>HAGRID'S HACKATHON 2026 — NOT AN OFFICIAL GOVERNMENT SERVICE — MOCKED SERVICES ONLY</span>
    </div>
  );
};
