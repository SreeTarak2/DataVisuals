import React, { useEffect, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { CustomToaster } from "./components/ui/custom-toaster";
import { initAuth } from "./store/authStore";
import useThemeStore from "./store/themeStore";
import ProtectedRoute from "./components/ProtectedRoute";
import DashboardLayout from "./components/layout/DashboardLayout";
import ErrorBoundary from "./components/common/ErrorBoundary";
import { Loader2 } from "lucide-react";
import lazyWithRetry from "./utils/lazyWithRetry";

// Lazy load pages with retry to avoid repeated "Failed to fetch dynamically imported module" loops.
const Landing = lazyWithRetry(() => import("./pages/LandingPage.jsx"), "landing");
const Login = lazyWithRetry(() => import("./pages/Login.jsx"), "login");
const Register = lazyWithRetry(() => import("./pages/Register.jsx"), "register");
const GoogleCallback = lazyWithRetry(() => import("./pages/auth/GoogleCallbackPage.jsx"), "google-callback");
const Dashboard = lazyWithRetry(() => import("./pages/Dashboard/index.js"), "dashboard");
const Datasets = lazyWithRetry(() => import("./pages/Datasets.jsx"), "datasets");
const Chat = lazyWithRetry(() => import("./pages/Chat.jsx"), "chat");
const ChartsStudio = lazyWithRetry(() => import("./pages/ChartsStudio.jsx"), "charts");
const Settings = lazyWithRetry(() => import("./pages/Settings.jsx"), "settings");
const Insights = lazyWithRetry(() => import("./pages/insights/index.js"), "insights");
const DataProfile = lazyWithRetry(() => import("./pages/DataProfile/index.js"), "data-profile");
const UnderstandingReport = lazyWithRetry(() => import("./pages/datasets/UnderstandingReport.jsx"), "understanding-report");
const Connectors = lazyWithRetry(() => import("./pages/ConnectorsPage.jsx"), "connectors");
const ConnectorSetup = lazyWithRetry(() => import("./pages/ConnectorSetupPage.jsx"), "connector-setup");
const DevKpiTest = lazyWithRetry(() => import("./pages/dev/KpiTest.jsx"), "dev-kpi-test");

// Loading fallback component
const PageLoader = () => (
  <div className="min-h-screen bg-slate-950 flex items-center justify-center">
    <div className="flex flex-col items-center gap-4">
      <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      <p className="text-slate-400 text-sm">Loading...</p>
    </div>
  </div>
);

function App() {
  // Initialize auth and theme on app load
  useEffect(() => {
    initAuth();
    useThemeStore.getState().initTheme();
  }, []);

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {/* Public Routes */}
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/auth/google/callback" element={<GoogleCallback />} />
            <Route path="/dev/kpi-test" element={<DevKpiTest />} />

            {/* Protected Routes */}
            <Route
              path="/app"
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/app/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="workspace" element={<Datasets />} />
              <Route path="chat" element={<Chat />} />
              <Route path="charts" element={<ChartsStudio />} />
              <Route path="analysis" element={<Insights />} />
              <Route path="settings" element={<Settings />} />
              <Route path="connectors" element={<Connectors />} />
              <Route path="connectors/:id" element={<ConnectorSetup />} />
              <Route path="datasets/:id/profile" element={<DataProfile />} />
              <Route path="datasets/:id/understanding" element={<UnderstandingReport />} />
            </Route>

            {/* Catch all - redirect to landing */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
        <CustomToaster />
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
