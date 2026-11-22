import React, { useState } from 'react';
import { RoleSelector, UserRole } from './RoleSelector';
import { OfficerQueue } from './OfficerQueue';
import { AdminTwin } from './AdminTwin';
import { AuditorLedger } from './AuditorLedger';
import { EvalDashboard } from './EvalDashboard';
import {
  FileText,
  Sliders,
  Lock,
  BarChart3,
  ShieldAlert
} from 'lucide-react';

export const BackOfficeSuite: React.FC = () => {
  const [currentRole, setCurrentRole] = useState<UserRole>(
    () => (localStorage.getItem('user_role') as UserRole) || 'officer'
  );
  const [activeTab, setActiveTab] = useState<'queue' | 'admin' | 'auditor' | 'eval'>('queue');

  // RBAC Permission Checks
  const canAccessQueue = ['officer', 'admin'].includes(currentRole);
  const canAccessAdmin = ['admin'].includes(currentRole);
  const canAccessAuditor = ['auditor', 'admin'].includes(currentRole);
  const canAccessEval = ['admin', 'auditor', 'officer'].includes(currentRole);

  const isDenied = !canAccessQueue && !canAccessAdmin && !canAccessAuditor && !canAccessEval;

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans">
      {/* Real Token Role Swapper */}
      <RoleSelector
        currentRole={currentRole}
        onRoleChanged={(newRole) => {
          setCurrentRole(newRole);
          // Set appropriate default tab for newly selected role
          if (newRole === 'officer') setActiveTab('queue');
          else if (newRole === 'admin') setActiveTab('admin');
          else if (newRole === 'auditor') setActiveTab('auditor');
        }}
      />

      {/* Sub Header & Navigation */}
      <div className="bg-white border-b border-slate-200 px-6 py-2 flex items-center justify-between text-xs font-bold">
        <div className="flex items-center space-x-1 sm:space-x-4">
          <button
            onClick={() => setActiveTab('queue')}
            className={`py-2 px-3 rounded-lg flex items-center space-x-1.5 transition ${
              activeTab === 'queue' ? 'bg-indigo-600 text-white shadow' : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Officer Queue</span>
          </button>

          <button
            onClick={() => setActiveTab('admin')}
            className={`py-2 px-3 rounded-lg flex items-center space-x-1.5 transition ${
              activeTab === 'admin' ? 'bg-indigo-600 text-white shadow' : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            <Sliders className="w-4 h-4" />
            <span>Admin & Digital Twin</span>
          </button>

          <button
            onClick={() => setActiveTab('auditor')}
            className={`py-2 px-3 rounded-lg flex items-center space-x-1.5 transition ${
              activeTab === 'auditor' ? 'bg-indigo-600 text-white shadow' : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            <Lock className="w-4 h-4" />
            <span>Auditor Ledger</span>
          </button>

          <button
            onClick={() => setActiveTab('eval')}
            className={`py-2 px-3 rounded-lg flex items-center space-x-1.5 transition ${
              activeTab === 'eval' ? 'bg-indigo-600 text-white shadow' : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            <span>Evaluation Dashboard</span>
          </button>
        </div>
      </div>

      {/* Main Body with Strict RBAC Feedback */}
      <div className="flex-1">
        {isDenied ? (
          <div className="max-w-md mx-auto my-16 p-8 bg-white rounded-3xl shadow-lg border border-rose-200 text-center space-y-4">
            <div className="w-16 h-16 bg-rose-100 text-rose-700 rounded-3xl mx-auto flex items-center justify-center">
              <ShieldAlert className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-black text-slate-900">HTTP 403: Forbidden</h2>
            <p className="text-xs text-slate-500 leading-relaxed">
              Your active token represents role <span className="font-mono font-bold uppercase text-rose-700">{currentRole}</span>, which is not authorized to access internal administrative back-office suites.
            </p>
            <p className="text-xs text-slate-400">
              Please use the &quot;Swap Real Token&quot; bar at the top to assume an Officer, Admin, or Auditor role.
            </p>
          </div>
        ) : (
          <>
            {activeTab === 'queue' && (
              canAccessQueue ? (
                <OfficerQueue />
              ) : (
                <div className="p-12 text-center text-slate-400 text-sm font-bold">
                  403: Role &apos;{currentRole}&apos; does not have permission to view the Officer Review Queue.
                </div>
              )
            )}

            {activeTab === 'admin' && (
              canAccessAdmin ? (
                <AdminTwin />
              ) : (
                <div className="p-12 text-center text-slate-400 text-sm font-bold">
                  403: Role &apos;{currentRole}&apos; does not have permission to edit Rules or run the Digital Twin. Swap to Admin.
                </div>
              )
            )}

            {activeTab === 'auditor' && (
              canAccessAuditor ? (
                <AuditorLedger />
              ) : (
                <div className="p-12 text-center text-slate-400 text-sm font-bold">
                  403: Role &apos;{currentRole}&apos; does not have permission to view Auditor Hash Chains. Swap to Auditor.
                </div>
              )
            )}

            {activeTab === 'eval' && (
              canAccessEval ? (
                <EvalDashboard />
              ) : (
                <div className="p-12 text-center text-slate-400 text-sm font-bold">
                  403: Evaluation dashboard access denied.
                </div>
              )
            )}
          </>
        )}
      </div>
    </div>
  );
};
