import React, { useState } from 'react';
import { api } from '../../api/client';
import { Shield, Key } from 'lucide-react';

export type UserRole = 'citizen' | 'helper' | 'officer' | 'admin' | 'auditor';

interface RoleSelectorProps {
  currentRole: UserRole;
  onRoleChanged: (newRole: UserRole) => void;
}

export const RoleSelector: React.FC<RoleSelectorProps> = ({ currentRole, onRoleChanged }) => {
  const [loading, setLoading] = useState<boolean>(false);

  const roles: { role: UserRole; email: string; label: string }[] = [
    { role: 'officer', email: 'officer@prd.test', label: 'Officer' },
    { role: 'admin', email: 'admin@prd.test', label: 'Admin' },
    { role: 'auditor', email: 'auditor@prd.test', label: 'Auditor' },
    { role: 'helper', email: 'helper@prd.test', label: 'Helper' },
    { role: 'citizen', email: 'citizen@prd.test', label: 'Citizen' },
  ];

  const handleSwitchRole = async (role: UserRole, email: string) => {
    setLoading(true);
    try {
      const res = await api.post('/auth/login', {
        email,
        password: 'Demo@12345',
        tenant_id: 'prd',
      });
      if (res.access_token && res.refresh_token) {
        api.setTokens(res.access_token, res.refresh_token);
        localStorage.setItem('user_role', role);
        localStorage.setItem('user_email', email);
        onRoleChanged(role);
      }
    } catch (err: any) {
      // In case offline or mock
      localStorage.setItem('user_role', role);
      localStorage.setItem('user_email', email);
      onRoleChanged(role);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-800 text-white px-4 py-2 flex flex-wrap items-center justify-between border-b border-slate-700 text-xs">
      <div className="flex items-center space-x-2">
        <Shield className="w-4 h-4 text-emerald-400" />
        <span className="font-bold">Active Role:</span>
        <span className="uppercase px-2 py-0.5 rounded font-mono font-black bg-emerald-600 text-white">
          {currentRole}
        </span>
        <span className="text-slate-400">({localStorage.getItem('user_email') || `${currentRole}@prd.test`})</span>
      </div>

      <div className="flex items-center space-x-1 mt-1 sm:mt-0">
        <span className="text-slate-400 mr-1 flex items-center">
          <Key className="w-3 h-3 mr-1" /> Swap Real Token:
        </span>
        {roles.map((r) => (
          <button
            key={r.role}
            disabled={loading || currentRole === r.role}
            onClick={() => handleSwitchRole(r.role, r.email)}
            className={`px-2.5 py-1 rounded font-bold transition ${
              currentRole === r.role
                ? 'bg-emerald-500 text-slate-900 shadow'
                : 'bg-slate-700 hover:bg-slate-600 text-slate-200'
            }`}
          >
            {r.label}
          </button>
        ))}
      </div>
    </div>
  );
};
