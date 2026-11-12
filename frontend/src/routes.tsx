import React, { useEffect, useState } from 'react';
import { Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AppHeader } from './components/layout/AppHeader';
import { StaffSidebar } from './components/layout/StaffSidebar';
import { LoginPage } from './pages/auth/LoginPage';
import { MFAPage } from './pages/auth/MFAPage';
import { PasswordRecoveryPage } from './pages/auth/PasswordRecoveryPage';
import { StudentFeedPage } from './pages/student/StudentFeedPage';
import { TeacherDashboardPage } from './pages/teacher/TeacherDashboardPage';
import { AdminDashboardPage } from './pages/admin/AdminDashboardPage';
import { SuperAdminDashboardPage } from './pages/superadmin/SuperAdminDashboardPage';
import { QuizView } from './components/academic/QuizView';
import { ToastNotification } from './components/ui/ToastNotification';
import { apiClient } from './api/client';
import type { CourseOffering } from './types/academics';
import { useAuth } from './contexts/AuthContext';

const MaterialsRoute: React.FC = () => {
  return <StudentFeedPage />;
};

const TeacherQuizzesRoute: React.FC = () => {
  const [offerings, setOfferings] = useState<CourseOffering[]>([]);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<CourseOffering[]>('/api/v1/academics/teacher/offerings')
      .then((rows) => {
        if (!cancelled) setOfferings(Array.isArray(rows) ? rows : []);
      })
      .catch(() => {
        if (!cancelled) setOfferings([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-5">
      <header>
        <p className="text-xs font-bold uppercase tracking-wide text-[#0A8FF5]">Faculty studio</p>
        <h1 className="mt-1 text-2xl font-bold text-slate-900">Quizzes &amp; Assessments</h1>
      </header>
      <QuizView offerings={offerings} onShowToast={setToast} />
      <ToastNotification message={toast} onClose={() => setToast(null)} />
    </div>
  );
};

// Dedicated Layout for Faculty, Institution Admin, and Platform Governance
const StaffLayout: React.FC = () => {
  return (
    <div className="min-h-screen bg-[#F8FAFC] flex flex-col">
      <AppHeader />
      <div className="flex-1 flex max-w-7xl w-full mx-auto">
        <StaffSidebar />
        <main className="flex-1 p-4 lg:p-8 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
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

      {/* Student Community Experience (Self-Contained 3-Column Layout from Prototype) */}
      <Route path="/doubts" element={<StudentFeedPage />} />
      <Route path="/courses" element={<StudentFeedPage />} />
      <Route path="/quiz" element={<StudentFeedPage />} />
      <Route path="/pyq" element={<StudentFeedPage />} />
      <Route path="/materials" element={<MaterialsRoute />} />
      <Route path="/course-doubts" element={<StudentFeedPage />} />
      <Route path="/analytics" element={<StudentFeedPage />} />
      <Route path="/profile" element={<StudentFeedPage />} />

      {/* Staff & Administration Studio Layout */}
      <Route element={<StaffLayout />}>
        {/* Teacher Routes */}
        <Route path="/teacher/dashboard" element={<TeacherDashboardPage />} />
        <Route path="/teacher/courses" element={<TeacherDashboardPage />} />
        <Route path="/teacher/quizzes" element={<TeacherQuizzesRoute />} />
        <Route path="/teacher/analytics" element={<TeacherDashboardPage />} />

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
