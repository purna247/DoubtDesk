import React, { createContext, useContext, useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { AuthMeResponse, Role, UserProfile } from '../types/auth';

interface AuthContextType {
  user: UserProfile | null;
  role: Role | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  primaryRoute: string;
  refreshSession: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [role, setRole] = useState<Role | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [primaryRoute, setPrimaryRoute] = useState<string>('/login');

  const refreshSession = async () => {
    setIsLoading(true);
    try {
      const data = await apiClient.get<AuthMeResponse>('/api/v1/auth/me');
      if (data.authenticated && data.user) {
        const u = data.user;
        const name = u.fullName || u.full_name || u.email?.split('@')[0] || 'User';
        const inst = u.institutionName || u.institution_name || null;
        const normalizedUser: UserProfile = {
          ...u,
          fullName: name,
          full_name: name,
          institutionName: inst,
          institution_name: inst,
        };
        setUser(normalizedUser);
        setRole(data.user.role);
        setIsAuthenticated(true);
        setPrimaryRoute(data.primaryRoute || data.primary_route || '/doubts');
      } else {
        setUser(null);
        setRole(null);
        setIsAuthenticated(false);
        setPrimaryRoute('/login');
      }
    } catch {
      setUser(null);
      setRole(null);
      setIsAuthenticated(false);
      setPrimaryRoute('/login');
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      await apiClient.post('/api/v1/auth/logout');
    } catch {
      // Ignore network errors on logout
    } finally {
      setUser(null);
      setRole(null);
      setIsAuthenticated(false);
      window.location.href = '/login';
    }
  };

  useEffect(() => {
    refreshSession();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        role,
        isAuthenticated,
        isLoading,
        primaryRoute,
        refreshSession,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

