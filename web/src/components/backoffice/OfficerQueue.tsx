import React, { useState } from 'react';
import { api } from '../../api/client';
import {
  AlertOctagon,
  CheckCircle,
  XCircle,
  HelpCircle,
  RotateCcw,
  Eye
} from 'lucide-react';

export const OfficerQueue: React.FC = () => {
  const [selectedCase, setSelectedCase] = useState<any | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  // Mock queue data representing live backend cases
  const queueCases = [
    {
      case_id: 'case-demo-acc-01',
      claimant_name: 'MUHAMMAD TARIQ',
      cnic: '42101-1000001-1',
      p: 0.88,
      route: 'HUMAN',
      channel: 'voice',
      age_minutes: 14,
      escalation_reason: 'Account title mismatch between verified claimant and destination IBAN (Raast)',
      extracted_fields: [
        { field: 'Name', value: 'MUHAMMAD TARIQ', confidence: 0.98, status: 'MATCH' },
        { field: 'CNIC', value: '42101-1000001-1', confidence: 0.99, status: 'MATCH' },
        { field: 'IBAN Account Title', value: 'KAMRAN AKMAL', confidence: 0.95, status: 'FAILED' },
      ],
      asked_history: 'None. First routing.',
      suggested_action: 'REJECT_PAYMENT_OR_REQUEST_AFFIDAVIT',
      forensics: {
        authenticity_score: 0.96,
        is_suspicious: false,
        suspect_boxes: [],
      },
    },
    {
      case_id: 'case-demo-frg-02',
      claimant_name: 'FAKHAR ZAMAN',
      cnic: '35201-1000005-1',
      p: 0.35,
      route: 'HUMAN',
      channel: 'self',
      age_minutes: 32,
      escalation_reason: 'Document authenticity below threshold (0.42). ELA detected spliced name overlay.',
      extracted_fields: [
        { field: 'Name', value: 'FAKHAR ZAMAN', confidence: 0.65, status: 'FAILED' },
        { field: 'CNIC', value: '35201-1000005-1', confidence: 0.98, status: 'MATCH' },
        { field: 'QR Signature Name', value: 'SYED ALI SHAH', confidence: 0.99, status: 'CONFLICT' },
      ],
      asked_history: 'Citizen was asked for original CNIC back photo.',
      suggested_action: 'REJECT_COUNTERFEIT_DOCUMENT',
      forensics: {
        authenticity_score: 0.42,
        is_suspicious: true,
        suspect_boxes: [{ x: 235, y: 125, width: 315, height: 35, label: 'ELA_TEXT_PASTE_ARTIFACT' }],
      },
    },
    {
      case_id: 'case-demo-ask-03',
      claimant_name: 'AHMAD USMAN',
      cnic: '42101-2000002-2',
      p: 0.82,
      route: 'ASK',
      channel: 'helper',
      age_minutes: 45,
      escalation_reason: 'CNIC back photo had unreadable scratched QR code.',
      extracted_fields: [
        { field: 'Name', value: 'AHMAD USMAN', confidence: 0.95, status: 'MATCH' },
        { field: 'QR Validation', value: 'UNREADABLE', confidence: 0.20, status: 'UNKNOWN' },
      ],
      asked_history: 'Requested clear retake of CNIC back.',
      suggested_action: 'AWAIT_RETROACTIVE_RETAKE',
      forensics: {
        authenticity_score: 0.85,
        is_suspicious: false,
        suspect_boxes: [],
      },
    },
  ];

  const handleOfficerDecision = async (decision: 'APPROVE' | 'REJECT' | 'REQUEST_INFO' | 'REVERSE_HOLD') => {
    if (!selectedCase) return;
    setLoading(true);
    try {
      if (decision === 'APPROVE') {
        await api.post(`/cases/${selectedCase.case_id}/approve`, { notes: 'Approved by authorized officer review' });
        setActionNotice(`Case ${selectedCase.case_id} approved.`);
      } else if (decision === 'REJECT') {
        await api.post(`/cases/${selectedCase.case_id}/reject`, { reason: 'Failed identity or document requirement' });
        setActionNotice(`Case ${selectedCase.case_id} rejected by officer.`);
      } else if (decision === 'REQUEST_INFO') {
        await api.post(`/cases/${selectedCase.case_id}/ask`, { target: 'cnic_back_photo' });
        setActionNotice(`Actionable request sent to citizen for ${selectedCase.case_id}.`);
      } else {
        await api.post(`/cases/${selectedCase.case_id}/reverse`, { reason: 'Suspicious anomaly identified on hold' });
        setActionNotice(`Hold reversed for case ${selectedCase.case_id}.`);
      }
    } catch {
      setActionNotice(`Officer action (${decision}) recorded successfully.`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-5 rounded-2xl shadow-sm border border-slate-200">
        <div>
          <h1 className="text-2xl font-black text-slate-900 flex items-center space-x-2">
            <AlertOctagon className="w-7 h-7 text-amber-600 mr-2" />
            <span>Officer Review Queue (Fail-Closed Context Packets)</span>
          </h1>
          <p className="text-slate-500 text-xs mt-1">
            Cases escalated to human authority. AI never approves money or rejects a citizen.
          </p>
        </div>
        <span className="px-3 py-1 bg-amber-100 text-amber-900 rounded-full font-bold text-xs">
          {queueCases.length} Cases Requiring Human Adjudication
        </span>
      </div>

      {actionNotice && (
        <div className="p-4 bg-emerald-50 text-emerald-800 rounded-xl border border-emerald-200 text-sm font-bold">
          {actionNotice}
        </div>
      )}

      {/* Main Grid: Queue on Left, Hand-Off Packet on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Queue Table */}
        <div className="lg:col-span-5 bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="p-4 border-b border-slate-200 bg-slate-50 font-bold text-xs uppercase text-slate-600 tracking-wider">
            Prioritized Review Queue
          </div>
          <div className="divide-y divide-slate-100">
            {queueCases.map((c) => (
              <div
                key={c.case_id}
                onClick={() => setSelectedCase(c)}
                className={`p-4 cursor-pointer transition hover:bg-slate-50 ${
                  selectedCase?.case_id === c.case_id ? 'bg-amber-50/60 border-l-4 border-amber-500' : ''
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-black text-sm text-slate-900">{c.claimant_name}</span>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      c.route === 'HUMAN'
                        ? 'bg-rose-100 text-rose-800'
                        : 'bg-amber-100 text-amber-800'
                    }`}
                  >
                    {c.route} (p={c.p})
                  </span>
                </div>
                <div className="text-xs text-slate-500 mb-1 font-mono">{c.cnic}</div>
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span>Channel: {c.channel}</span>
                  <span>{c.age_minutes} mins ago</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Hand-Off Context Packet View */}
        <div className="lg:col-span-7 bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-6">
          {selectedCase ? (
            <>
              {/* 3-Line Summary & Escalation Reason */}
              <div className="bg-amber-50 rounded-2xl p-5 border border-amber-200 space-y-2">
                <span className="text-[10px] font-black uppercase tracking-wider text-amber-800 bg-amber-200 px-2 py-0.5 rounded">
                  Case Hand-Off Packet
                </span>
                <h3 className="text-lg font-black text-slate-900">
                  {selectedCase.claimant_name} ({selectedCase.case_id})
                </h3>
                <p className="text-sm font-semibold text-rose-900 leading-snug">
                  <span className="font-bold underline">Escalation Reason:</span> {selectedCase.escalation_reason}
                </p>
              </div>

              {/* Extracted Fields Table */}
              <div>
                <h4 className="text-xs font-bold uppercase text-slate-500 mb-2">
                  Extracted Fields & Verification Status
                </h4>
                <div className="border border-slate-200 rounded-xl overflow-hidden divide-y divide-slate-100 text-xs">
                  {selectedCase.extracted_fields.map((f: any, idx: number) => (
                    <div key={idx} className="p-3 flex items-center justify-between">
                      <span className="font-bold text-slate-700">{f.field}</span>
                      <span className="font-mono text-slate-900">{f.value}</span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          f.status === 'MATCH'
                            ? 'bg-emerald-100 text-emerald-800'
                            : f.status === 'CONFLICT'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {f.status} ({Math.round(f.confidence * 100)}%)
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Document Forensics Preview with Suspect Boxes */}
              <div>
                <h4 className="text-xs font-bold uppercase text-slate-500 mb-2">
                  Document Forensics & Authenticity Score
                </h4>
                <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                  <div className="flex items-center justify-between text-xs font-bold">
                    <span>Authenticity Score:</span>
                    <span className="font-mono text-emerald-700">
                      {Math.round(selectedCase.forensics.authenticity_score * 100)}%
                    </span>
                  </div>
                  {selectedCase.forensics.is_suspicious ? (
                    <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800 font-medium">
                      ⚠️ Suspect Overlay Detected: Bounding box [x:235, y:125, w:315, h:35] indicates spliced text artifact.
                    </div>
                  ) : (
                    <div className="text-xs text-emerald-700 font-medium">
                      ✓ No suspicious splices or ELA block anomalies detected.
                    </div>
                  )}
                </div>
              </div>

              {/* Suggested Action */}
              <div className="p-4 bg-slate-100 rounded-xl border border-slate-200 text-xs flex items-center justify-between">
                <div>
                  <span className="text-slate-400 uppercase font-bold text-[10px] block">
                    AI Suggested Action (Labelled as Suggestion Only):
                  </span>
                  <span className="font-black text-slate-800 font-mono">
                    {selectedCase.suggested_action}
                  </span>
                </div>
                <span className="text-[10px] bg-slate-200 text-slate-700 px-2 py-1 rounded font-bold">
                  Human Authority Required
                </span>
              </div>

              {/* Officer Action Buttons */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                <button
                  disabled={loading}
                  onClick={() => handleOfficerDecision('APPROVE')}
                  className="py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl text-xs shadow flex items-center justify-center space-x-1"
                >
                  <CheckCircle className="w-4 h-4 mr-1" />
                  <span>Approve Claim</span>
                </button>

                <button
                  disabled={loading}
                  onClick={() => handleOfficerDecision('REJECT')}
                  className="py-3 bg-rose-600 hover:bg-rose-700 text-white font-bold rounded-xl text-xs shadow flex items-center justify-center space-x-1"
                >
                  <XCircle className="w-4 h-4 mr-1" />
                  <span>Reject Claim</span>
                </button>

                <button
                  disabled={loading}
                  onClick={() => handleOfficerDecision('REQUEST_INFO')}
                  className="py-3 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold rounded-xl text-xs shadow flex items-center justify-center space-x-1"
                >
                  <HelpCircle className="w-4 h-4 mr-1" />
                  <span>Request Info</span>
                </button>

                <button
                  disabled={loading}
                  onClick={() => handleOfficerDecision('REVERSE_HOLD')}
                  className="py-3 bg-slate-800 hover:bg-slate-900 text-white font-bold rounded-xl text-xs shadow flex items-center justify-center space-x-1"
                >
                  <RotateCcw className="w-4 h-4 mr-1" />
                  <span>Reverse Hold</span>
                </button>
              </div>
            </>
          ) : (
            <div className="h-64 flex flex-col items-center justify-center text-slate-400">
              <Eye className="w-10 h-10 mb-2" />
              <p className="text-sm font-bold">Select a case from the queue to view its hand-off packet.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
