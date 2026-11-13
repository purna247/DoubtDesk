import React, { useState } from 'react';
import { Search, Bell, LogOut, ShieldCheck, GraduationCap, School, X, ChevronDown, User as UserIcon } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

export interface AppHeaderProps {
  searchQuery?: string;
  onSearchChange?: (query: string) => void;
  onOpenAskModal?: () => void;
  onOpenProfile?: () => void;
  onNavigateHome?: () => void;
}

export const AppHeader: React.FC<AppHeaderProps> = ({
  searchQuery = '',
  onSearchChange,
  onOpenAskModal,
  onOpenProfile,
  onNavigateHome,
}) => {
  const { user, role, logout } = useAuth();
  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);

  const [notifications, setNotifications] = useState([
    { id: 1, title: 'Priya Nair verified your answer', desc: 'Operating Systems: Demand Paging & Page Fault Handling', time: '5m ago', unread: true },
    { id: 2, title: 'Faculty Solution Available', desc: 'Prof. Arvind Sharma verified an answer on Computer Networks', time: '1h ago', unread: true },
    { id: 3, title: 'Weekly Streaks Reward', desc: 'Active contributor badge unlocked for 3-day answer streak', time: '1d ago', unread: false },
  ]);

  const hasUnread = notifications.some((n) => n.unread);
  const markAllRead = () => setNotifications((prev) => prev.map((n) => ({ ...n, unread: false })));

  const displayName = user?.fullName || user?.full_name || user?.email?.split('@')[0] || 'User';
  const initials = displayName.slice(0, 2).toUpperCase();
  const isStudent = role === 'STUDENT';

  const getRoleBadge = () => {
    switch (role) {
      case 'SUPER_ADMIN':
        return <span className="hidden sm:inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-100 text-purple-800 border border-purple-200"><ShieldCheck className="w-3 h-3" /> Platform Owner</span>;
      case 'ADMIN':
        return <span className="hidden sm:inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200"><School className="w-3 h-3" /> Institution Admin</span>;
      case 'TEACHER':
        return <span className="hidden sm:inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200"><GraduationCap className="w-3 h-3" /> Faculty</span>;
      default:
        return null;
    }
  };

  return (
    <header className="sticky top-0 z-40 bg-white border-b border-[#E8EFF3] h-[68px] px-3 sm:px-6 lg:px-8">
      <div className="max-w-[1540px] mx-auto h-full flex items-center justify-between gap-3 sm:gap-6">

        {/* Brand — always a clickable home button */}
        <button
          onClick={onNavigateHome}
          className="flex items-center gap-2.5 shrink-0 hover:opacity-90 transition cursor-pointer text-left"
        >
          <span className="text-lg sm:text-xl font-bold tracking-tight text-[#111111] select-none leading-none">
            Doubt<span className="text-[#0A8FF5]">Desk</span>
          </span>
        </button>

        {/* Search bar — shared across all roles */}
        {onSearchChange && (
          <div className="flex-1 min-w-0 max-w-[720px]">
            <div className="relative flex items-center w-full">
              <Search className="absolute left-3.5 sm:left-4 w-4 h-4 sm:w-5 sm:h-5 text-[#61717D] pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
                placeholder={
                  isStudent
                    ? 'Search for an answer to any question...'
                    : 'Search academic doubts, concepts, or PYQs...'
                }
                className="w-full h-[42px] sm:h-[46px] pl-10 sm:pl-12 pr-9 sm:pr-10 rounded-full bg-[#EDF4F8] border border-transparent text-[#111111] placeholder-[#637381] text-xs sm:text-[15px] focus:bg-white focus:border-[#0A8FF5]/40 focus:outline-none focus:ring-4 focus:ring-[#0A8FF5]/10 transition-all truncate"
              />
              {searchQuery && (
                <button
                  onClick={() => onSearchChange('')}
                  className="absolute right-3 text-[#71808C] hover:text-[#111111] p-1 rounded-full hover:bg-slate-200/60 transition cursor-pointer"
                  aria-label="Clear search"
                >
                  <X className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Right actions */}
        <div className="flex items-center gap-2 sm:gap-3.5 shrink-0">

          {/* Role badge (teacher / admin only) */}
          {getRoleBadge()}

          {/* Ask Question button — student only */}
          {isStudent && onOpenAskModal && (
            <button
              onClick={onOpenAskModal}
              className="h-[40px] sm:h-[42px] px-4 sm:px-6 rounded-full bg-[#050505] hover:bg-[#1A1A1A] text-white font-extrabold text-xs sm:text-sm uppercase tracking-wide inline-flex items-center gap-1.5 transition transform hover:-translate-y-0.5 cursor-pointer shadow-sm whitespace-nowrap"
            >
              Ask Question
            </button>
          )}

          {/* Notifications */}
          <div className="relative">
            <button
              onClick={() => setShowNotifications((v) => !v)}
              className="w-9 h-9 sm:w-10 sm:h-10 rounded-full flex items-center justify-center text-[#4D5963] hover:text-[#111111] hover:bg-[#EDF4F8] transition relative cursor-pointer"
              aria-label="Notifications"
            >
              <Bell className="w-4 h-4 sm:w-5 sm:h-5" />
              {hasUnread && (
                <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-[#E52521] ring-2 ring-white" />
              )}
            </button>

            {/* Notification dropdown — student only; staff gets simple icon */}
            {showNotifications && isStudent && (
              <div className="absolute right-0 mt-2 w-80 sm:w-88 bg-white rounded-2xl border border-[#DCE7EE] shadow-xl z-50 p-4 animate-in fade-in duration-150">
                <div className="flex items-center justify-between pb-3 border-b border-[#E8EFF3]">
                  <h4 className="text-sm font-bold text-[#111111]">Notifications</h4>
                  <button onClick={markAllRead} className="text-[11px] font-semibold text-[#0A8FF5] hover:underline cursor-pointer">
                    Mark all read
                  </button>
                </div>
                <div className="py-2 space-y-2.5 max-h-80 overflow-y-auto">
                  {notifications.map((n) => (
                    <div key={n.id} className={`p-2.5 rounded-xl transition ${n.unread ? 'bg-[#F4F8FB]' : 'hover:bg-[#F7FAFC]'}`}>
                      <div className="flex items-start justify-between gap-1">
                        <p className="text-xs font-bold text-[#111111] leading-tight">{n.title}</p>
                        <span className="text-[10px] text-[#71808C] shrink-0">{n.time}</span>
                      </div>
                      <p className="text-xs text-[#4D5963] mt-0.5 leading-snug">{n.desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Profile / user menu — shared structure, student gets "View Profile" link */}
          <div className="relative">
            <button
              onClick={() => setShowUserMenu((v) => !v)}
              className="flex items-center gap-2 p-1 pl-1.5 rounded-full hover:bg-slate-100 transition cursor-pointer"
              aria-label="User profile menu"
              title={displayName}
            >
              <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-slate-200 border border-[#DCE7EE] overflow-hidden flex items-center justify-center font-bold text-xs text-slate-700">
                {user?.avatar_url && (
                  <img
                    src={user.avatar_url}
                    alt={displayName}
                    className="w-full h-full object-cover"
                    referrerPolicy="no-referrer"
                    onError={(e) => { (e.target as HTMLElement).style.display = 'none'; }}
                  />
                )}
                <span>{initials}</span>
              </div>
              <div className="hidden md:flex flex-col text-left">
                <span className="text-xs font-bold text-[#111111] truncate max-w-[110px]">{displayName}</span>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 hidden sm:block" />
            </button>

            {showUserMenu && (
              <div className="absolute right-0 mt-2 w-56 bg-white rounded-2xl border border-[#DCE7EE] shadow-xl z-50 p-2 animate-in fade-in duration-150">
                <div className="px-3 py-2 border-b border-[#E8EFF3]">
                  <p className="text-xs font-bold text-[#111111]">{displayName}</p>
                  <p className="text-[11px] text-slate-500 truncate">{user?.email}</p>
                </div>
                <div className="py-1">
                  {isStudent && onOpenProfile && (
                    <button
                      onClick={() => { setShowUserMenu(false); onOpenProfile(); }}
                      className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 rounded-lg cursor-pointer"
                    >
                      <UserIcon className="w-4 h-4 text-slate-400" /> View Full Profile
                    </button>
                  )}
                  <button
                    onClick={() => { setShowUserMenu(false); logout(); }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-red-600 hover:bg-red-50 rounded-lg cursor-pointer"
                  >
                    <LogOut className="w-4 h-4 text-red-500" /> Sign Out
                  </button>
                </div>
              </div>
            )}
          </div>

        </div>
      </div>
    </header>
  );
};
