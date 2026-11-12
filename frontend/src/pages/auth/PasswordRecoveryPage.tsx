import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Mail, KeyRound, AlertCircle, CheckCircle, ArrowLeft, ArrowRight } from 'lucide-react';
import { apiClient } from '../../api/client';

export const PasswordRecoveryPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [identifier, setIdentifier] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleRequestReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage(null);

    try {
      await apiClient.post('/api/v1/auth/forgot-password', { identifier });
      setIsSuccess(true);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to dispatch reset link');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCommitReset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setErrorMessage('Passwords do not match');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      await apiClient.post('/api/v1/auth/reset-password', {
        token,
        new_password: newPassword,
      });
      setIsSuccess(true);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to reset password. The link may have expired.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white border border-[#DCE7EE] rounded-[18px] p-8 shadow-sm">
        {/* Brand Header */}
        <div className="text-center mb-6">
          <div className="w-12 h-12 bg-[#0A8FF5] text-white rounded-2xl flex items-center justify-center mx-auto mb-3 shadow-md">
            <KeyRound className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-[#111111]">
            {token ? 'Reset Password' : 'Password Recovery'}
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            {token
              ? 'Enter a new secure password for your account.'
              : 'Enter your institutional email or registration number to receive a reset link.'}
          </p>
        </div>

        {errorMessage && (
          <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3 text-sm text-red-700">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-500 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        {isSuccess ? (
          <div className="text-center py-4">
            <CheckCircle className="w-12 h-12 text-[#22A06B] mx-auto mb-3" />
            <h2 className="text-base font-bold text-slate-900 mb-1">
              {token ? 'Password Reset Successful' : 'Reset Link Dispatched'}
            </h2>
            <p className="text-xs text-slate-500 mb-6">
              {token
                ? 'Your password has been securely updated. You can now log in.'
                : 'If an account matches your identifier, a recovery link has been sent to your verified email address.'}
            </p>
            <Link to="/login" className="btn-primary w-full py-2.5 inline-block text-center text-sm">
              Return to Login
            </Link>
          </div>
        ) : token ? (
          <form onSubmit={handleCommitReset} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
                New Password
              </label>
              <input
                type="password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="At least 8 characters"
                className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#0A8FF5]/30 focus:border-[#0A8FF5]"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
                Confirm Password
              </label>
              <input
                type="password"
                required
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm password"
                className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#0A8FF5]/30 focus:border-[#0A8FF5]"
              />
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="w-full btn-primary py-2.5 flex items-center justify-center gap-2 mt-2"
            >
              {isLoading ? 'Updating...' : 'Set New Password'}
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        ) : (
          <form onSubmit={handleRequestReset} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
                Identifier
              </label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-3 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  required
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="e.g. 210101001 or faculty@outr.ac.in"
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#0A8FF5]/30 focus:border-[#0A8FF5]"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="w-full btn-primary py-2.5 flex items-center justify-center gap-2 mt-2"
            >
              {isLoading ? 'Sending Link...' : 'Send Recovery Link'}
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        )}

        {!isSuccess && (
          <div className="mt-6 text-center">
            <Link
              to="/login"
              className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back to Login
            </Link>
          </div>
        )}
      </div>
    </div>
  );
};

