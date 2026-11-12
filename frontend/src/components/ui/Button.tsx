import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'outline';
}

export const Button: React.FC<ButtonProps> = ({ variant = 'primary', className = '', disabled, ...props }) => (
  <button
    {...props}
    disabled={disabled}
    className={`${variant === 'primary' ? 'btn-primary' : 'btn-outline'} disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:transform-none ${className}`.trim()}
  />
);
