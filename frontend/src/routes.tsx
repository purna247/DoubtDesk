import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { StaffSidebar } from './components/layout/StaffSidebar';
import { AdminRightSidebar } from './components/sidebar/AdminRightSidebar';
import { SuperAdminRightSidebar } from './components/sidebar/SuperAdminRightSidebar';
import { LoginPage } from './pages/auth/LoginPage';
import { MFAPage } from './pages/auth/MFAPage';
import { PasswordRecoveryPage } from './pages/auth/PasswordRecoveryPage';
import { StudentFeedPage } from './pages/student/StudentFeedPage';
import { useAuth } from './contexts/AuthContext';

// Dynamic code-splitting for heavy role-specific workspaces (Vercel React Best Practice: bundle-dynamic-imports)
const TeacherWorkspacePage = lazy(() =>
  import('./pages/teacher/TeacherWorkspacePage').then((m) => ({ default: m.TeacherWorkspacePage }))
);
const AdminDashboardPage = lazy(() =>
  import('./pages/admin/AdminDashboardPage').then((m) => ({ default: m.AdminDashboardPage }))
);
const SuperAdminDashboardPage = lazy(() =>
  import('./pages/superadmin/SuperAdminDashboardPage').then((m) => ({ default: m.SuperAdminDashboardPage }))
);

const LoadingSpinner: React.FC = () => (
  <div className="min-h-screen flex items-center justify-center bg-slate-50">
    <div className="w-8 h-8 border-3 border-[#0A8FF5] border-t-transparent rounded-full animate-spin"></div>
  </div>
);

// Unified Academic Route: Dispatches to TeacherWorkspacePage for faculty and StudentFeedPage for students
const AcademicRoute: React.FC = () => {
  const { role, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (role === 'TEACHER') {
    return (
      <Suspense fallback={<LoadingSpinner />}>
        <TeacherWorkspacePage />
      </Suspense>
    );
  }

  return <StudentFeedPage />;
};

// Common Layout for Institution Admin and Platform Governance
const StaffLayout: React.FC = () => {
  const { role } = useAuth();
  const location = useLocation();

  const activeTab = location.pathname.includes('/admin/academic/units')
    ? 'units'
    : location.pathname.includes('/admin/academic/subjects')
    ? 'subjects'
    : location.pathname.includes('/admin/curriculum')
    ? 'curriculum'
    : location.pathname.includes('/admin/offerings')
    ? 'offerings'
    : location.pathname.includes('/admin/moderation')
    ? 'moderation'
    : location.pathname.includes('/super-admin/institutions')
    ? 'institutions'
    : location.pathname.includes('/super-admin/pipeline')
    ? 'pipeline'
    : location.pathname.includes('/super-admin/audit')
    ? 'audit'
    : 'dashboard';

  return (
    <AppLayout
      activeTab={activeTab}
      leftSidebar={<StaffSidebar />}
      rightSidebar={
        role === 'SUPER_ADMIN' ? (
          <SuperAdminRightSidebar />
        ) : (
          <AdminRightSidebar />
        )
      }
    >
      <Suspense fallback={<LoadingSpinner />}>
        <Outlet />
      </Suspense>
    </AppLayout>
  );
};

const RootRedirect: React.FC = () => {
  const { isAuthenticated, isLoading, primaryRoute } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="w-8 h-8 border-3 border-[#0A8FF5] border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to={primaryRoute || '/doubts'} replace />;
  }

  return <Navigate to="/login" replace />;
};

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Public Authentication Routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/login/mfa" element={<MFAPage />} />
      <Route path="/forgot-password" element={<PasswordRecoveryPage />} />
      <Route path="/reset-password" element={<PasswordRecoveryPage />} />

      {/* Unified Academic Experience (Student & Teacher with Common 3-Column Layout) */}
      <Route path="/doubts" element={<AcademicRoute />} />
      <Route path="/courses" element={<AcademicRoute />} />
      <Route path="/quiz" element={<AcademicRoute />} />
      <Route path="/pyq" element={<AcademicRoute />} />
      <Route path="/materials" element={<AcademicRoute />} />
      <Route path="/course-doubts" element={<Navigate to="/doubts" replace />} />
      <Route path="/analytics" element={<AcademicRoute />} />
      <Route path="/profile" element={<AcademicRoute />} />

      {/* Legacy Teacher Routes Redirect to Unified Doubts Workspace */}
      <Route path="/teacher/*" element={<Navigate to="/doubts" replace />} />

      {/* Staff & Administration Studio Layout with Common 3-Column Layout */}
      <Route element={<StaffLayout />}>
        {/* Admin Routes */}
        <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
        <Route path="/admin/academic/units" element={<AdminDashboardPage />} />
        <Route path="/admin/academic/subjects" element={<AdminDashboardPage />} />
        <Route path="/admin/curriculum/subjects" element={<AdminDashboardPage />} />
        <Route path="/admin/offerings" element={<AdminDashboardPage />} />
        <Route path="/admin/users" element={<AdminDashboardPage />} />
        <Route path="/admin/moderation" element={<AdminDashboardPage />} />

        {/* Super Admin Routes */}
        <Route path="/super-admin/dashboard" element={<SuperAdminDashboardPage />} />
        <Route path="/super-admin/institutions" element={<SuperAdminDashboardPage />} />
        <Route path="/super-admin/pipeline" element={<SuperAdminDashboardPage />} />
        <Route path="/super-admin/audit" element={<SuperAdminDashboardPage />} />
      </Route>

      {/* Default Route */}
      <Route path="/" element={<RootRedirect />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};
