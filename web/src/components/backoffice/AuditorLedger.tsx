import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import {
  CheckCircle2,
  History,
  Lock,
  RotateCcw,
  ShieldCheck
} from 'lucide-react';

export const AuditorLedger: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [chainStatus, setChainStatus] = useState<string | null>(null);
  const [verifying, setVerifying] = useState<boolean>(false);
  const [selectedTrace, setSelectedTrace] = useState<any | null>(null);

  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [chainOk, setChainOk] = useState<boolean>(true);
  const [replaying, setReplaying] = useState<number | null>(null);

  const loadLogs = async () => {
    try {
      const rows = await api.get<any[]>('/audit?limit=50');
      setAuditLogs(rows || []);
      setLoadError(null);
    } catch (e: any) {
      setLoadError(e?.message || 'Could not load audit log (auditor role required).');
    }
  };

  useEffect(() => {
    loadLogs();
  }, []);

  const handleVerifyChain = async () => {
    setVerifying(true);
    try {
      const res = await api.get<any>('/audit/verify-chain');
      setChainOk(!!res.ok);
      setChainStatus(
        res.ok
          ? `OK: SHA-256 chain verified intact across ${res.checked} entries (0 breaks).`
          : `TAMPER DETECTED: chain broken at entry #${res.broken_at_id} (checked ${res.checked}).`
      );
      loadLogs();
    } catch (e: any) {
      // Fail closed: never report a chain as intact when verification could not run
      setChainOk(false);
      setChainStatus(`Verification could not run: ${e?.message || 'unknown error'}`);
    } finally {
      setVerifying(false);
    }
  };

  const handleReplayDecision = async (entry: any) => {
    setReplaying(entry.id);
    try {
      const res = await api.get<any>(`/decisions/${entry.entity_id}/replay`);
      setSelectedTrace({
        entry_id: entry.id,
        replayed_under_version: `v${res.rule_version}`,
        rule_hash: res.rule_hash,
        matches: !!res.matches,
        original_route: res.original_outcome?.route,
        replayed_route: res.replayed_outcome?.route,
        reason: res.original_outcome?.citizen_reason,
      });
    } catch (e: any) {
      setSelectedTrace({ entry_id: entry.id, error: e?.message || 'Replay failed' });
    } finally {
      setReplaying(null);
    }
  };


  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header with Verify Chain Button */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-5 rounded-2xl shadow-sm border border-slate-200">
        <div>
          <h1 className="text-2xl font-black text-slate-900 flex items-center space-x-2">
            <Lock className="w-7 h-7 text-emerald-600 mr-2" />
            <span>Auditor Cryptographic Ledger & Decision Replay</span>
          </h1>
          <p className="text-slate-500 text-xs mt-1">
            Post-commit tamper-evident audit logs with cryptographic hash-chaining (SHA-256).
          </p>
        </div>

        <button
          disabled={verifying}
          onClick={handleVerifyChain}
          className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-bold text-xs flex items-center space-x-2 shadow"
        >
          <ShieldCheck className="w-4 h-4" />
          <span>{verifying ? 'Verifying Hashes...' : 'Verify Cryptographic Chain'}</span>
        </button>
      </div>

      {chainStatus && (
        <div className={`p-4 rounded-xl border text-xs font-bold flex items-center space-x-2 ${chainOk ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'}`}>
          <CheckCircle2 className={`w-5 h-5 ${chainOk ? 'text-emerald-600' : 'text-rose-600'}`} />
          <span>{chainStatus}</span>
        </div>
      )}

      {/* Main Grid: Audit Log Table and Trace Replay */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7 bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="p-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
            <span className="font-bold text-xs uppercase text-slate-600 tracking-wider">
              Append-Only Audit Entries
            </span>
            <input
              type="text"
              placeholder="Search by Case ID or Actor..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="px-3 py-1 text-xs border border-slate-300 rounded-lg focus:outline-none"
            />
          </div>

          <div className="divide-y divide-slate-100 text-xs">
            {loadError && <div className="p-4 text-rose-700">{loadError}</div>}
            {!loadError && auditLogs.length === 0 && <div className="p-4 text-slate-400">No audit entries yet for this tenant.</div>}
            {auditLogs
              .filter((log) => !searchTerm || `${log.entity_id} ${log.actor_type} ${log.action}`.toLowerCase().includes(searchTerm.toLowerCase()))
              .map((log) => (
              <div key={log.id} className="p-4 hover:bg-slate-50 transition space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-black text-slate-900">
                    Entry #{log.id} · <span className="font-mono text-emerald-700">{log.action}</span>
                  </span>
                  {log.entity_type === 'decision' && (
                  <button
                    onClick={() => handleReplayDecision(log)}
                    className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 rounded text-[11px] font-bold text-slate-700 flex items-center space-x-1"
                  >
                    <RotateCcw className="w-3 h-3 mr-0.5" />
                    <span>{replaying === log.id ? '...' : 'Replay'}</span>
                  </button>
                  )}
                </div>

                <div className="text-[11px] text-slate-500 flex space-x-4">
                  <span>Entity: {log.entity_id}</span>
                  <span>Actor: {log.actor_type}{log.acting_as ? ` (as ${log.acting_as})` : ''}</span>
                  <span>{new Date(log.created_at).toLocaleString()}</span>
                </div>

                <div className="font-mono text-[10px] text-slate-400 bg-slate-50 p-2 rounded truncate">
                  SHA-256: {log.hash}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Trace View & Replay */}
        <div className="lg:col-span-5 bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
          <h3 className="text-base font-black text-slate-900 flex items-center space-x-1">
            <History className="w-5 h-5 text-indigo-600 mr-1" />
            <span>Decision Trace Replay</span>
          </h3>

          {selectedTrace ? (
            selectedTrace.error ? (
              <div className="p-4 bg-rose-50 rounded-xl border border-rose-200 text-xs text-rose-800">
                Replay for entry #{selectedTrace.entry_id} failed: {selectedTrace.error}
              </div>
            ) : (
            <div className="space-y-4 text-xs">
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                <div className="flex justify-between">
                  <span className="font-bold text-slate-600">Replay Target:</span>
                  <span className="font-mono font-bold">Entry #{selectedTrace.entry_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-bold text-slate-600">Original Rule Version:</span>
                  <span className="font-mono font-bold text-indigo-700">{selectedTrace.replayed_under_version}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-bold text-slate-600">Route (original → replayed):</span>
                  <span className="font-mono font-bold">{selectedTrace.original_route} → {selectedTrace.replayed_route}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-bold text-slate-600">Outcome Match:</span>
                  <span className={`font-bold ${selectedTrace.matches ? 'text-emerald-700' : 'text-rose-700'}`}>
                    {selectedTrace.matches ? 'EXACT MATCH' : 'DIVERGENCE DETECTED'}
                  </span>
                </div>
              </div>

              <div className={`p-4 rounded-xl border space-y-1 ${selectedTrace.matches ? 'bg-emerald-50 border-emerald-200 text-emerald-900' : 'bg-rose-50 border-rose-200 text-rose-900'}`}>
                <span className="font-bold block">{selectedTrace.matches ? 'Deterministic Execution Verified:' : 'Replay Mismatch:'}</span>
                <p className="text-[11px] leading-relaxed">
                  Stored input snapshot re-evaluated against immutable rule set {selectedTrace.replayed_under_version}
                  {selectedTrace.rule_hash ? ` (hash ${String(selectedTrace.rule_hash).slice(0, 12)}…)` : ''}.
                  {selectedTrace.reason ? ` Citizen reason: “${selectedTrace.reason}”` : ''}
                </p>
              </div>
            </div>
            )
          ) : (
            <div className="h-48 flex flex-col items-center justify-center text-slate-400 text-xs text-center">
              Click &quot;Replay&quot; on any audit entry to simulate deterministic evaluation under its historical rule set.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
