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
const Features = lazyWithRetry(() => import("./pages/FeaturesPage.jsx"), "features");
const Pricing = lazyWithRetry(() => import("./pages/PricingPage.jsx"), "pricing");
const Docs = lazyWithRetry(() => import("./pages/DocsPage.jsx"), "docs");
const Blog = lazyWithRetry(() => import("./pages/BlogPage.jsx"), "blog");
const Demo = lazyWithRetry(() => import("./pages/DemoPage.jsx"), "demo");
const Playground = lazyWithRetry(() => import("./pages/playground/PlaygroundPage.jsx"), "playground");
const Projects = lazyWithRetry(() => import("./pages/projects/ProjectsPage.jsx"), "projects");
const ProjectNotebook = lazyWithRetry(() => import("./pages/projects/ProjectNotebookPage.jsx"), "project-notebook");
const Login = lazyWithRetry(() => import("./pages/Login.jsx"), "login");
const Register = lazyWithRetry(() => import("./pages/Register.jsx"), "register");
const GoogleCallback = lazyWithRetry(() => import("./pages/auth/GoogleCallbackPage.jsx"), "google-callback");
const Dashboard = lazyWithRetry(() => import("./pages/Dashboard/index.js"), "dashboard");
const MainDashboard = lazyWithRetry(() => import("./pages/Dashboard/MainDashboard.jsx"), "main-dashboard");
const Datasets = lazyWithRetry(() => import("./pages/Datasets.jsx"), "datasets");
const Settings = lazyWithRetry(() => import("./pages/Settings.jsx"), "settings");
const Connectors = lazyWithRetry(() => import("./pages/ConnectorsPage.jsx"), "connectors");
const ConnectorSetup = lazyWithRetry(() => import("./pages/ConnectorSetupPage.jsx"), "connector-setup");
const DataBriefing = lazyWithRetry(() => import("./pages/DataBriefing.jsx"), "data-briefing");
const SqlEditorPage = lazyWithRetry(() => import("./pages/sql/SqlEditorPage.jsx"), "sql");

// Loading fallback component
const PageLoader = () => (
  <div className="min-h-screen bg-slate-950 flex items-center justify-center">
    <div className="flex flex-col items-center gap-4">
      <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      <p className="text-slate-400 text-sm">Loading...</p>
    </div>
  </div>
);

// Module-level guard prevents double init in React StrictMode (dev mode).
// React 18 StrictMode unmounts and remounts components with fresh useRefs,
// so a module-level variable is the only reliable guard outside the component.
let _appInitialized = false;

function App() {
  // Initialize auth and theme on app load
  useEffect(() => {
    if (_appInitialized) return;
    _appInitialized = true;
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
            <Route path="/features" element={<Features />} />
            <Route path="/pricing" element={<Pricing />} />
            <Route path="/docs" element={<Docs />} />
            <Route path="/blog" element={<Blog />} />
            <Route path="/demo" element={<Demo />} />
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
              <Route path="dashboard" element={<MainDashboard />} />
              <Route path="workspace" element={<Datasets />} />
              <Route path="datasets" element={<Datasets />} />
              <Route path="settings" element={<Settings />} />
              <Route path="connectors" element={<Connectors />} />
              <Route path="connectors/:id" element={<ConnectorSetup />} />
              <Route path="datasets/:id/briefing" element={<DataBriefing />} />
              <Route path="playground" element={<Playground />} />
              <Route path="projects" element={<Projects />} />
              <Route path="projects/:projectId" element={<ProjectNotebook />} />
              <Route path="sql" element={<SqlEditorPage />} />
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
