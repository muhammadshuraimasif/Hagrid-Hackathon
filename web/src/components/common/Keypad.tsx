import React from 'react';
import { Delete, Check } from 'lucide-react';

interface KeypadProps {
  onDigit: (digit: string) => void;
  onBackspace: () => void;
  onConfirm?: () => void;
  confirmLabel?: string;
}

export const Keypad: React.FC<KeypadProps> = ({
  onDigit,
  onBackspace,
  onConfirm,
  confirmLabel = 'Done',
}) => {
  const digits = ['1', '2', '3', '4', '5', '6', '7', '8', '9'];

  return (
    <div className="bg-slate-100 p-4 rounded-2xl shadow-inner max-w-sm mx-auto">
      <div className="grid grid-cols-3 gap-3">
        {digits.map((d) => (
          <button
            key={d}
            type="button"
            onClick={() => onDigit(d)}
            className="h-16 bg-white hover:bg-emerald-50 active:bg-emerald-100 rounded-xl font-bold text-2xl text-slate-800 shadow-sm border border-slate-200 flex items-center justify-center transition"
          >
            {d}
          </button>
        ))}
        <button
          type="button"
          onClick={onBackspace}
          className="h-16 bg-rose-50 hover:bg-rose-100 active:bg-rose-200 rounded-xl font-bold text-rose-700 shadow-sm border border-rose-200 flex items-center justify-center transition"
          aria-label="Backspace"
        >
          <Delete className="w-7 h-7" />
        </button>
        <button
          type="button"
          onClick={() => onDigit('0')}
          className="h-16 bg-white hover:bg-emerald-50 active:bg-emerald-100 rounded-xl font-bold text-2xl text-slate-800 shadow-sm border border-slate-200 flex items-center justify-center transition"
        >
          0
        </button>
        {onConfirm && (
          <button
            type="button"
            onClick={onConfirm}
            className="h-16 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white rounded-xl font-bold text-lg shadow-sm flex items-center justify-center space-x-1 transition"
          >
            <Check className="w-6 h-6 mr-1" />
            <span>{confirmLabel}</span>
          </button>
        )}
      </div>
    </div>
  );
};
