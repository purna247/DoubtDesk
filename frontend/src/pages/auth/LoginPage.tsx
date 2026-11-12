import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Lock, Mail, AlertCircle, ArrowRight } from 'lucide-react';
import { apiClient } from '../../api/client';
import { LoginResponse } from '../../types/auth';
import { useAuth } from '../../contexts/AuthContext';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { refreshSession } = useAuth();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const response = await apiClient.post<LoginResponse>('/api/v1/auth/login', {
        identifier,
        password,
      });

      if (response.mfaRequired) {
        // Super Admin MFA challenge required
        navigate('/login/mfa');
        return;
      }

      await refreshSession();
      navigate(response.redirectUrl || '/doubts');
    } catch (err: any) {
      setErrorMessage(err.message || 'Invalid institutional credentials. Please check your identifier and password.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white border border-[#DCE7EE] rounded-[18px] p-8 shadow-sm">
        {/* Brand Header */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-[#0A8FF5] text-white rounded-2xl flex items-center justify-center font-extrabold text-2xl mx-auto mb-3 shadow-md">
            D
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight text-[#111111]">
            Doubt<span className="text-[#0A8FF5]">Desk</span>
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            University Learning & Peer Doubt Community
          </p>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3 text-sm text-red-700">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-500 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
              Email or Registration Number
            </label>
            <div className="relative">
              <Mail className="absolute left-3.5 top-3 w-4 h-4 text-slate-400" />
              <input
                type="text"
                required
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="e.g. 210101001 or faculty@outr.ac.in"
                className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#0A8FF5]/30 focus:border-[#0A8FF5] transition-all"
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600">
                Password
              </label>
              <Link to="/forgot-password" className="text-xs text-[#0A8FF5] hover:underline font-medium">
                Forgot Password?
              </Link>
            </div>
            <div className="relative">
              <Lock className="absolute left-3.5 top-3 w-4 h-4 text-slate-400" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your account password"
                className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#0A8FF5]/30 focus:border-[#0A8FF5] transition-all"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full btn-primary py-2.5 flex items-center justify-center gap-2 mt-2"
          >
            {isLoading ? 'Signing in...' : 'Sign In'}
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-slate-100 text-center text-xs text-slate-400">
          ODISHA UNIVERSITY OF TECHNOLOGY AND RESEARCH (OUTR) PILOT
        </div>
      </div>
    </div>
  );
};

