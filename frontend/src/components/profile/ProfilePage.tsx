import React, { useState } from 'react';
import {
  Shield,
  Pencil,
  Trophy,
  ArrowLeft,
  Crown,
  Grid,
  Cpu,
  BookOpen,
  Sparkles
} from 'lucide-react';
import { DoubtItem } from '../../data/doubtsData';
import type { MyDoubtStats } from '../sidebar/RightSidebar';

interface ProfilePageProps {
  onBackToFeed: () => void;
  userPoints?: number;
  allDoubts?: DoubtItem[];
  studentName?: string;
  semester?: string;
  avatarUrl?: string | null;
  stats?: MyDoubtStats | null;
}

const getInitials = (name: string) => {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return 'S';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
};

export const ProfilePage: React.FC<ProfilePageProps> = ({
  onBackToFeed,
  userPoints = 655,
  studentName = 'Student Scholar',
  semester = 'Enrolled Student',
  avatarUrl,
  stats,
}) => {
  const [activeTab, setActiveTab] = useState<'achievements' | 'answers' | 'questions' | 'friends'>('achievements');
  const [isEditing, setIsEditing] = useState(false);
  const [bio, setBio] = useState('Learning and collaborating with peers across core engineering subjects on DoubtDesk.');

  const userStats = {
    name: studentName,
    title: semester,
    answersCount: stats?.answered_count ?? 0,
    brainliestCount: stats?.verified_answers_count ?? 0,
    thanksCount: stats?.thanks_count ?? 0,
    questionsCount: stats?.asked_count ?? 0,
    friendsCount: 0,
    achievementsUnlocked: (stats?.answered_count || stats?.asked_count) ? 1 : 0,
    achievementsTotal: 267
  };



  const inProgressAchievements = [
    {
      id: 'star-student',
      title: 'Star Student',
      level: 'Level 3/9',
      description: 'Answer 10 questions in any subject.',
      current: 6,
      total: 10,
      icon: (
        <div className="w-10 h-10 rounded-xl bg-[#EDF4F8] border border-[#DCE7EE] flex flex-col items-center justify-center text-[#111111] font-bold shrink-0">
          <Grid className="w-4 h-4 text-[#0A8FF5]" />
          <span className="text-[10px] leading-none mt-0.5">10</span>
        </div>
      )
    },
    {
      id: 'smart-microchip',
      title: 'Smart Microchip',
      level: 'Level 3/9',
      description: 'Answer 10 Computer Science questions.',
      current: 6,
      total: 10,
      icon: (
        <div className="w-10 h-10 rounded-xl bg-[#EDF4F8] border border-[#DCE7EE] flex flex-col items-center justify-center text-[#111111] font-bold shrink-0">
          <Cpu className="w-4 h-4 text-[#0A8FF5]" />
          <span className="text-[8px] leading-none mt-0.5 font-semibold text-[#61717D]">CS</span>
        </div>
      )
    }
  ];

  const unlockedBadges = [
    { id: 'helper', name: 'Helper' },
    { id: 'first-answer', name: 'First Answer' },
    { id: 'rising-star', name: 'Rising Star' },
    { id: 'cs-expert', name: 'CS Expert' },
    { id: 'engaged', name: 'Engaged' },
    { id: 'thanks-getter', name: 'Thanks Getter' },
  ];

  return (
    <div className="min-h-screen bg-white text-[#111111] pb-16">
      {/* Decorative Top Banner matching user screenshot */}
      <div className="w-full h-32 sm:h-36 md:h-40 bg-gradient-to-r from-[#D7EEFA] via-[#E2F2FC] to-[#D0EAF8] relative overflow-hidden border-b border-[#D2E7F3]">
        <div className="absolute inset-0 opacity-40 bg-[radial-gradient(#0A8FF5_1px,transparent_1px)] [background-size:16px_16px]" />
        
        {/* Subtle geometric shapes mimicking Brainly's banner */}
        <div className="absolute -right-8 -top-8 w-56 h-56 rounded-full bg-white/20 pointer-events-none" />
        <div className="absolute left-1/3 -bottom-10 w-72 h-36 bg-white/15 -rotate-12 rounded-3xl pointer-events-none" />

        <div className="max-w-[960px] mx-auto px-4 sm:px-6 h-full flex items-start pt-3 sm:pt-4">
          <button
            onClick={onBackToFeed}
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/85 hover:bg-white text-xs font-bold text-[#111111] backdrop-blur-xs transition shadow-xs cursor-pointer"
          >
            <ArrowLeft className="w-3.5 h-3.5 text-[#0A8FF5]" />
            <span>Back to feed</span>
          </button>
        </div>
      </div>

      {/* Main Centered Content Container (max-w-[960px] centered with mx-auto) */}
      <div className="max-w-[960px] mx-auto px-4 sm:px-6">
        <div className="grid grid-cols-1 md:grid-cols-[240px_minmax(0,1fr)] gap-7 lg:gap-9 -mt-12 sm:-mt-14 relative z-10">
          
          {/* LEFT COLUMN: Profile info, stats, badges, edit profile */}
          <div className="flex flex-col items-center md:items-start text-center md:text-left">
            {/* Avatar with Circular Ring */}
            <div className="relative w-22 h-22 sm:w-24 sm:h-24 shrink-0 mb-2 flex items-center justify-center">
              {/* Segmented Green Ring SVG */}
              <svg className="w-full h-full -rotate-90 shrink-0" viewBox="0 0 80 80">
                <circle
                  cx="40"
                  cy="40"
                  r="35"
                  fill="none"
                  stroke="#E8EFF3"
                  strokeWidth="3.5"
                />
                <circle
                  cx="40"
                  cy="40"
                  r="35"
                  fill="none"
                  stroke="#22A06B"
                  strokeWidth="3.5"
                  strokeDasharray="6 2.5"
                  strokeDashoffset="24"
                  strokeLinecap="round"
                />
              </svg>

              {/* Inner Avatar Graphic */}
              <div className="absolute inset-2 rounded-full overflow-hidden bg-[#0F172A] text-white border-2 border-white flex items-center justify-center shadow-sm font-bold text-lg">
                {avatarUrl ? (
                  <img
                    src={avatarUrl}
                    alt={userStats.name}
                    className="w-full h-full object-cover"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <span>{getInitials(userStats.name)}</span>
                )}
              </div>
            </div>

            {/* Username & Points pill row matching screenshot */}
            <div className="flex items-center gap-2 mb-1.5 flex-wrap justify-center md:justify-start">
              <h1 className="text-xl font-bold text-[#111111] tracking-tight">
                {userStats.name}
              </h1>

              {/* Points Pill */}
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#050505] text-white text-xs font-bold shadow-xs">
                <span>{userPoints} pts</span>
              </div>
            </div>

            {/* Ambitious Yellow Badge Pill matching screenshot */}
            <div className="mb-3.5">
              <span className="inline-block px-3 py-0.5 rounded-full bg-[#FFF2C6] text-[#111111] font-semibold text-xs tracking-wide">
                {userStats.title}
              </span>
            </div>

            {/* Stats Row (Answers 6 · Brainliest 0 · Thanks 24) matching screenshot */}
            <div className="w-full py-3 border-y border-[#E8EFF3] grid grid-cols-3 text-center mb-4">
              <div>
                <span className="text-[11px] font-medium text-[#71808C] block">
                  Answers
                </span>
                <span className="text-lg font-bold text-[#111111] tabular-nums mt-0.5 block">
                  {userStats.answersCount}
                </span>
              </div>
              <div className="border-x border-[#E8EFF3]">
                <span className="text-[11px] font-medium text-[#71808C] block">
                  Best Answer
                </span>
                <span className="text-lg font-bold text-[#111111] tabular-nums mt-0.5 block">
                  {userStats.brainliestCount}
                </span>
              </div>
              <div>
                <span className="text-[11px] font-medium text-[#71808C] block">
                  Thanks
                </span>
                <span className="text-lg font-bold text-[#111111] tabular-nums mt-0.5 block">
                  {userStats.thanksCount}
                </span>
              </div>
            </div>

            {/* Badges List matching screenshot */}
            <div className="w-full mb-4">
              <div className="grid grid-cols-2 gap-1.5">
                {unlockedBadges.map((badge) => (
                  <div
                    key={badge.id}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#EDF4F8] hover:bg-[#E3EDF3] text-[#111111] text-[11px] font-semibold transition truncate"
                  >
                    <Shield className="w-3 h-3 text-[#111111] shrink-0" />
                    <span className="truncate">{badge.name}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* EDIT PROFILE Button matching screenshot */}
            <button
              onClick={() => setIsEditing(!isEditing)}
              className="w-full h-10 px-4 rounded-full bg-[#EDF4F8] hover:bg-[#E3EDF3] text-[#111111] font-bold text-xs tracking-wider uppercase inline-flex items-center justify-center gap-2 transition cursor-pointer"
            >
              <Pencil className="w-3 h-3" />
              <span>{isEditing ? 'Save Profile' : 'EDIT PROFILE'}</span>
            </button>

            {/* Inline Bio Editor */}
            {isEditing ? (
              <div className="w-full mt-3 p-3 rounded-xl bg-[#F7FAFC] border border-[#DCE7EE]">
                <textarea
                  rows={3}
                  value={bio}
                  onChange={(e) => setBio(e.target.value)}
                  className="w-full text-xs text-[#111111] bg-white p-2 rounded-lg border border-[#DCE7EE] focus:outline-none focus:ring-1 focus:ring-[#0A8FF5]"
                />
              </div>
            ) : (
              <p className="w-full mt-2.5 text-xs text-[#71808C] leading-relaxed">
                {bio}
              </p>
            )}
          </div>

          {/* RIGHT COLUMN: Horizontal Tabs + Achievements Cards */}
          <div className="min-w-0 pt-1 md:pt-3">
            {/* Top Navigation Tabs matching screenshot */}
            <div className="flex items-center gap-6 sm:gap-7 border-b border-[#E8EFF3] mb-5 overflow-x-auto no-scrollbar justify-start">
              <button
                onClick={() => setActiveTab('answers')}
                className={`pb-2.5 text-xs sm:text-sm font-bold transition-colors relative whitespace-nowrap cursor-pointer ${
                  activeTab === 'answers'
                    ? 'text-[#111111]'
                    : 'text-[#71808C] hover:text-[#111111]'
                }`}
              >
                <span>Answers {userStats.answersCount}</span>
                {activeTab === 'answers' && (
                  <span className="absolute bottom-0 left-0 right-0 h-[2.5px] bg-[#0A8FF5] rounded-t-full" />
                )}
              </button>

              <button
                onClick={() => setActiveTab('questions')}
                className={`pb-2.5 text-xs sm:text-sm font-bold transition-colors relative whitespace-nowrap cursor-pointer ${
                  activeTab === 'questions'
                    ? 'text-[#111111]'
                    : 'text-[#71808C] hover:text-[#111111]'
                }`}
              >
                <span>Questions {userStats.questionsCount}</span>
                {activeTab === 'questions' && (
                  <span className="absolute bottom-0 left-0 right-0 h-[2.5px] bg-[#0A8FF5] rounded-t-full" />
                )}
              </button>

              <button
                onClick={() => setActiveTab('achievements')}
                className={`pb-2.5 text-xs sm:text-sm font-bold transition-colors relative whitespace-nowrap cursor-pointer ${
                  activeTab === 'achievements'
                    ? 'text-[#111111]'
                    : 'text-[#71808C] hover:text-[#111111]'
                }`}
              >
                <span>Achievements {userStats.achievementsUnlocked}</span>
                {activeTab === 'achievements' && (
                  <span className="absolute bottom-0 left-0 right-0 h-[2.5px] bg-[#0A8FF5] rounded-t-full" />
                )}
              </button>

              <button
                onClick={() => setActiveTab('friends')}
                className={`pb-2.5 text-xs sm:text-sm font-bold transition-colors relative whitespace-nowrap cursor-pointer ${
                  activeTab === 'friends'
                    ? 'text-[#111111]'
                    : 'text-[#71808C] hover:text-[#111111]'
                }`}
              >
                <span>Friends {userStats.friendsCount}</span>
                {activeTab === 'friends' && (
                  <span className="absolute bottom-0 left-0 right-0 h-[2.5px] bg-[#0A8FF5] rounded-t-full" />
                )}
              </button>
            </div>

            {/* TAB CONTENT: ACHIEVEMENTS (Matching screenshot) */}
            {activeTab === 'achievements' && (
              <div className="space-y-5 animate-in fade-in duration-150">
                {/* Achievements Banner Hero Card matching screenshot */}
                <div className="rounded-[16px] bg-[#F4F7F9] border border-[#DCE7EE] p-5 sm:p-6 relative overflow-hidden">
                  <div className="max-w-md z-10 relative">
                    <h2 className="text-lg sm:text-xl font-bold text-[#111111] mb-1.5 tracking-tight">
                      Achievements
                    </h2>
                    <p className="text-xs text-[#4D5963] leading-relaxed">
                      Answer questions, complete achievements, earn extra points and claim new badges that will adorn your profile for all to see. The higher level you achieve, the higher rewards you will get!
                    </p>
                  </div>

                  {/* Decorative Badges Stack Graphic on Right matching screenshot */}
                  <div className="hidden sm:flex absolute right-4 top-1/2 -translate-y-1/2 items-center gap-1.5 pointer-events-none opacity-90">
                    <div className="w-12 h-12 rounded-xl bg-[#0A8FF5] text-white flex flex-col items-center justify-center font-bold text-[11px] shadow-sm -rotate-6">
                      <Sparkles className="w-3.5 h-3.5 text-white" />
                      <span>2500</span>
                    </div>
                    <div className="w-13 h-13 rounded-xl bg-[#F5D36C] text-[#111111] flex flex-col items-center justify-center font-bold text-[11px] shadow-sm rotate-6">
                      <Crown className="w-4 h-4 text-[#8A6800]" />
                      <span>5000</span>
                    </div>
                    <div className="w-11 h-11 rounded-lg bg-[#22A06B] text-white flex flex-col items-center justify-center font-bold text-[10px] shadow-sm -rotate-3">
                      <span>500</span>
                    </div>
                  </div>
                </div>

                {/* Trophy Counter Banner matching screenshot */}
                <div className="flex items-center gap-2 text-sm sm:text-base font-bold text-[#111111]">
                  <Trophy className="w-5 h-5 text-[#D49E00]" />
                  <span>{userStats.achievementsUnlocked}/{userStats.achievementsTotal} achievements unlocked</span>
                </div>

                {/* In Progress Section matching screenshot */}
                <div>
                  <h3 className="text-xs sm:text-sm font-bold text-[#111111] mb-2.5">
                    In progress
                  </h3>

                  <div className="space-y-2.5">
                    {inProgressAchievements.map((item) => (
                      <div
                        key={item.id}
                        className="rounded-[14px] bg-white border border-[#DCE7EE] p-3.5 sm:p-4 flex items-center gap-3.5 hover:border-[#0A8FF5]/40 transition shadow-2xs"
                      >
                        {item.icon}

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2 mb-0.5">
                            <span className="font-bold text-xs sm:text-sm text-[#111111] truncate">
                              {item.title}
                            </span>
                            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#71808C] shrink-0">
                              <Trophy className="w-3 h-3 text-[#D49E00]" />
                              <span>{item.level}</span>
                            </span>
                          </div>

                          <p className="text-[11px] text-[#4D5963] mb-1.5 truncate">
                            {item.description}
                          </p>

                          {/* Progress Bar matching screenshot */}
                          <div className="flex items-center gap-2.5">
                            <div className="flex-1 h-1.5 rounded-full bg-[#E9F0F4] overflow-hidden">
                              <div
                                className="h-full bg-[#0A8FF5] rounded-full transition-all duration-300"
                                style={{ width: `${(item.current / item.total) * 100}%` }}
                              />
                            </div>
                            <span className="text-[10px] font-bold text-[#71808C] tabular-nums shrink-0">
                              {item.current}/{item.total}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* TAB CONTENT: ANSWERS */}
            {activeTab === 'answers' && (
              <div className="space-y-3 animate-in fade-in duration-150">
                <div className="border border-[#DCE7EE] rounded-xl p-4 bg-white shadow-2xs">
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="text-xs font-bold text-[#0A8FF5]">Operating Systems</span>
                    <span className="text-[11px] text-[#71808C]">Answered today</span>
                  </div>
                  <h4 className="font-bold text-xs sm:text-sm text-[#111111] mb-1.5">
                    Explain the role of the C programming language in the development of operating system kernels.
                  </h4>
                  <p className="text-xs text-[#4D5963] line-clamp-2">
                    C provides direct hardware access via pointers, register control, and minimal runtime dependency required for booting and kernel execution.
                  </p>
                  <div className="mt-2.5 pt-2 border-t border-[#E8EFF3] flex items-center justify-between text-[11px] text-[#71808C]">
                    <span className="font-semibold text-[#22A06B]">✓ Verified by Teacher</span>
                    <span className="font-bold text-[#111111]">+25 points earned</span>
                  </div>
                </div>
              </div>
            )}

            {/* TAB CONTENT: QUESTIONS */}
            {activeTab === 'questions' && (
              <div className="space-y-3 animate-in fade-in duration-150">
                <div className="border border-[#DCE7EE] rounded-xl p-4 bg-white shadow-2xs">
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="text-xs font-bold text-[#0A8FF5]">Operating Systems</span>
                    <span className="text-[11px] text-[#71808C]">Asked today</span>
                  </div>
                  <h4 className="font-bold text-xs sm:text-sm text-[#111111] mb-1.5">
                    Explain the role of the C programming language in the development of operating system kernels. What characteristics of C make it suitable for low-level system programming?
                  </h4>
                  <div className="mt-2.5 pt-2 border-t border-[#E8EFF3] flex items-center justify-between text-[11px] text-[#71808C]">
                    <span className="text-[#22A06B] font-bold">2 answers received</span>
                    <span>342 views</span>
                  </div>
                </div>
              </div>
            )}

            {/* TAB CONTENT: FRIENDS */}
            {activeTab === 'friends' && (
              <div className="border border-[#DCE7EE] rounded-xl p-6 bg-white text-center shadow-2xs animate-in fade-in duration-150">
                <div className="w-10 h-10 rounded-full bg-[#EDF4F8] flex items-center justify-center text-[#0A8FF5] mx-auto mb-2.5">
                  <BookOpen className="w-5 h-5" />
                </div>
                <h4 className="font-bold text-sm text-[#111111] mb-1">
                  Connect with Study Buddies
                </h4>
                <p className="text-xs text-[#71808C] max-w-sm mx-auto mb-3">
                  Add classmates and peers to compare achievements, see their answers, and solve doubts together.
                </p>
                <button
                  onClick={onBackToFeed}
                  className="btn-primary text-xs py-1.5 px-4"
                >
                  Explore Community
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
