import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { ThemeProvider } from "./contexts/ThemeContext";
import { AuthProvider } from "./contexts/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import DashboardLayout from "./components/layout/DashboardLayout";

// Pages
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Datasets from "./pages/Datasets";
import Chat from "./pages/Chat";
import Charts from "./pages/Charts";
import Settings from "./pages/Settings";

import "./App.css";

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public Routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            {/* Protected Routes */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="datasets" element={<Datasets />} />
              <Route path="chat" element={<Chat />} />
              <Route path="charts" element={<Charts />} />
              <Route path="settings" element={<Settings />} />
            </Route>

            {/* Catch all - redirect to login */}
            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
          <Toaster 
            position="top-center"
            toastOptions={{
              duration: 4000,
              style: {
                background: 'var(--background)',
                color: 'var(--foreground)',
                border: '1px solid var(--border)',
              },
            }}
          />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
