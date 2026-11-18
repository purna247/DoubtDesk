import React from 'react';
import type { LucideIcon } from 'lucide-react';

export interface EmptyStateCardProps {
  icon: LucideIcon;
  title: string;
  badgeIcon?: LucideIcon;
  badgeText: string;
  action?: React.ReactNode;
  className?: string;
}

export const EmptyStateCard: React.FC<EmptyStateCardProps> = ({
  icon: Icon,
  title,
  badgeIcon: BadgeIcon,
  badgeText,
  action,
  className = '',
}) => {
  return (
    <div className={`border border-[#DCE7EE] rounded-[16px] bg-white p-10 sm:p-14 text-center ${className}`}>
      <div className="w-14 h-14 rounded-full bg-[#F4F7F9] flex items-center justify-center text-[#71808C] mx-auto mb-4 shadow-xs">
        <Icon className="w-7 h-7" />
      </div>
      <h2 className="text-lg font-bold text-[#111111] mb-5">{title}</h2>
      <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#F4F7F9] text-xs font-semibold text-[#4D5963]">
        {BadgeIcon && <BadgeIcon className="w-4 h-4 text-[#0A8FF5]" />}
        <span>{badgeText}</span>
      </div>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
};
