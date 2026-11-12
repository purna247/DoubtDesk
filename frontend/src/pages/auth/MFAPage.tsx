import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ShieldCheck, AlertCircle, ArrowRight, ArrowLeft } from 'lucide-react';
import { apiClient } from '../../api/client';
import { useAuth } from '../../contexts/AuthContext';

export const MFAPage: React.FC = () => {
  const navigate = useNavigate();
  const { refreshSession } = useAuth();
  const [mfaCode, setMfaCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage(null);

    try {
      await apiClient.post('/api/v1/auth/mfa/verify', {
        code: mfaCode.trim(),
      });

      await refreshSession();
      navigate('/super-admin/dashboard');
    } catch (err: any) {
      setErrorMessage(
        err.message || 'Invalid verification code. Please check your authenticator application.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white border border-[#DCE7EE] rounded-[18px] p-8 shadow-sm">
        {/* Brand Header */}
        <div className="text-center mb-6">
          <div className="w-12 h-12 bg-purple-600 text-white rounded-2xl flex items-center justify-center mx-auto mb-3 shadow-md">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-[#111111]">
            Two-Factor Verification
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Super Admin elevation requires time-based one-time verification.
          </p>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3 text-sm text-red-700">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-500 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5 text-center">
              6-Digit Authenticator Code
            </label>
            <input
              type="text"
              required
              maxLength={6}
              autoFocus
              value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ''))}
              placeholder="000000"
              className="w-full py-3 text-center tracking-[0.5em] font-mono text-2xl bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500/30 focus:border-purple-500 transition-all"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading || mfaCode.length !== 6}
            className="w-full btn-primary bg-purple-700 hover:bg-purple-800 py-2.5 flex items-center justify-center gap-2 mt-2"
          >
            {isLoading ? 'Verifying...' : 'Verify & Elevate Session'}
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        <div className="mt-6 text-center">
          <Link
            to="/login"
            className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Return to Login
          </Link>
        </div>
      </div>
    </div>
  );
};

