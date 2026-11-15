import React from 'react';

interface SecondaryNavProps {
  activeTab: string;
  onSelectTab: (tabId: string) => void;
  role?: string | null;
}

export const SecondaryNav: React.FC<SecondaryNavProps> = ({ activeTab, onSelectTab, role }) => {
  const navItems = [
    { id: 'doubts', label: 'Doubts' },
    { id: 'learn', label: 'Learn' },
    { id: 'quiz', label: 'Quiz' },
    { id: 'pyq', label: 'PYQ' },
    { id: 'studymaterial', label: 'Study Material' },
    ...(role === 'TEACHER' ? [
      { id: 'teacher_analytics', label: 'Analytics' },
    ] : []),
  ];

  return (
    <nav className="h-[46px] bg-white border-b border-[#E8EFF3] px-4 md:px-8 overflow-x-auto no-scrollbar">
      <div className="max-w-[1540px] mx-auto h-full flex items-center gap-7 sm:gap-9 whitespace-nowrap text-[14px]">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`transition-colors cursor-pointer relative py-3 font-semibold ${
                isActive
                  ? 'text-[#111111] font-bold'
                  : 'text-[#4D5963] hover:text-[#111111]'
              }`}
            >
              <span>{item.label}</span>
              {isActive && (
                <span className="absolute bottom-0 left-0 right-0 h-[2.5px] bg-[#111111] rounded-full" />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
};


