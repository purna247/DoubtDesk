import React from 'react';
import { AppHeader } from './AppHeader';
import { SecondaryNav } from './SecondaryNav';
import { useAuth } from '../../contexts/AuthContext';

export interface AppLayoutProps {
  // Top nav / header
  searchQuery?: string;
  onSearchChange?: (q: string) => void;
  onOpenAskModal?: () => void;
  onOpenProfile?: () => void;
  onNavigateHome?: () => void;

  // Secondary nav
  activeTab?: string;
  onSelectTab?: (tabId: string) => void;

  // 3-Column slots
  leftSidebar?: React.ReactNode;
  rightSidebar?: React.ReactNode;
  children: React.ReactNode;

  // Configuration
  fullWidthMain?: boolean;
  className?: string;
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  searchQuery,
  onSearchChange,
  onOpenAskModal,
  onOpenProfile,
  onNavigateHome,
  activeTab,
  onSelectTab,
  leftSidebar,
  rightSidebar,
  children,
  fullWidthMain = false,
  className = '',
}) => {
  const { role } = useAuth();

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex flex-col">
      {/* 1. Universal Top Nav Bar */}
      <AppHeader
        searchQuery={searchQuery}
        onSearchChange={onSearchChange}
        onOpenAskModal={onOpenAskModal}
        onOpenProfile={onOpenProfile}
        onNavigateHome={onNavigateHome}
      />

      {/* 2. Universal Secondary Nav Bar */}
      <SecondaryNav
        activeTab={activeTab}
        onSelectTab={onSelectTab}
        role={role}
      />

      {/* 3. Universal 3-Column Workspace Grid */}
      <main className={`flex-1 w-full max-w-[1540px] mx-auto px-3 sm:px-6 py-5 sm:py-6 ${className}`}>
        <div
          className={`grid grid-cols-1 ${
            fullWidthMain || !rightSidebar
              ? 'md:grid-cols-[210px_minmax(0,1fr)] lg:grid-cols-[220px_minmax(0,1fr)] xl:grid-cols-[240px_minmax(0,1fr)]'
              : 'md:grid-cols-[210px_minmax(0,1fr)] lg:grid-cols-[200px_minmax(0,1fr)_290px] xl:grid-cols-[230px_minmax(0,1fr)_320px] 2xl:grid-cols-[240px_minmax(0,820px)_340px]'
          } gap-4 lg:gap-5 xl:gap-7 justify-center`}
        >
          {/* Column 1: Left Sidebar */}
          {leftSidebar && (
            <div className="shrink-0 hidden md:block">
              {leftSidebar}
            </div>
          )}

          {/* Column 2: Main Middle Section */}
          <section className={`min-w-0 ${fullWidthMain ? 'w-full' : 'max-w-[820px] w-full mx-auto md:mx-0'}`}>
            {children}
          </section>

          {/* Column 3: Right Sidebar */}
          {rightSidebar && (
            <div className="shrink-0 hidden lg:block">
              {rightSidebar}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};
