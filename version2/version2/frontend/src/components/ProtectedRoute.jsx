import React, { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../store/authStore';
import useAuthStore from '../store/authStore';
import { Loader2 } from 'lucide-react';

const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading, hasHydrated } = useAuth();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // If already hydrated (sync case), mark ready immediately
    if (hasHydrated && !loading) {
      setReady(true);
      return;
    }

    // Subscribe to store changes for async hydration
    const unsub = useAuthStore.subscribe((state) => {
      if (state._hasHydrated && !state.loading) {
        setReady(true);
        unsub();
      }
    });

    // Safety timeout — if still loading after 3s, force ready
    const timeout = setTimeout(() => {
      console.warn('ProtectedRoute: Auth hydration timed out, forcing ready');
      setReady(true);
    }, 3000);

    return () => {
      unsub();
      clearTimeout(timeout);
    };
  }, [hasHydrated, loading]);

  if (!ready) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
          <div className="text-slate-400 text-sm">Authenticating...</div>
        </div>
      </div>
    );
  }

  return isAuthenticated ? children : <Navigate to="/login" replace />;
};

export default ProtectedRoute;
