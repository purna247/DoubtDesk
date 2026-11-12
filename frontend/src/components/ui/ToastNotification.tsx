import React, { useEffect } from 'react';
import { CheckCircle2, X } from 'lucide-react';

interface ToastNotificationProps {
  message: string | null;
  onClose: () => void;
}

export const ToastNotification: React.FC<ToastNotificationProps> = ({ message, onClose }) => {
  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => {
      onClose();
    }, 3000);
    return () => clearTimeout(timer);
  }, [message, onClose]);

  if (!message) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-2xl bg-[#050505] text-white shadow-xl animate-in slide-in-from-bottom-4 duration-200">
      <CheckCircle2 className="w-4 h-4 text-[#22A06B] shrink-0" />
      <span className="text-xs font-semibold">{message}</span>
      <button
        onClick={onClose}
        className="ml-2 text-slate-400 hover:text-white transition p-0.5"
        aria-label="Close notification"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};
