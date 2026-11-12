export type Role = 'SUPER_ADMIN' | 'ADMIN' | 'TEACHER' | 'STUDENT';

export interface UserProfile {
  id: string;
  email: string;
  registrationNumber?: string | null;
  registration_number?: string | null;
  fullName?: string;
  full_name?: string;
  avatarUrl?: string | null;
  avatar_url?: string | null;
  role: Role;
  institutionId?: string | null;
  institution_id?: string | null;
  institutionName?: string | null;
  institution_name?: string | null;
  isMfaVerified?: boolean;
  is_mfa_verified?: boolean;
}

export interface AuthMeResponse {
  authenticated: boolean;
  user: UserProfile | null;
  primaryRoute?: string;
  primary_route?: string;
}

export interface LoginResponse {
  success: boolean;
  mfaRequired?: boolean;
  mfa_required?: boolean;
  preAuthToken?: string;
  redirectUrl?: string;
  redirect_url?: string;
}

