import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import api, { authAPI } from '../services/api';
import useDatasetStore from './datasetStore';
import useChatStore from './chatStore';
import useWorkspaceStore from './workspaceStore';
import { clearInsightsDataCache } from '../pages/insights/hooks/useInsightsData';

const USER_SCOPED_STORAGE_KEYS = ['dataset-storage', 'signal-chat-store', 'chat-history-storage'];

/**
 * Determine the storage backend based on the user's "Remember me" preference.
 * Defaults to localStorage (persistent). When "Remember me" is unchecked,
 * sessionStorage is used so the session dies when the browser closes.
 */
const getStorageBackend = () => {
    // Check if we previously chose sessionStorage
    if (sessionStorage.getItem('signal-auth')) {
        return sessionStorage;
    }
    return localStorage;
};

const clearUserScopedClientState = () => {
    try {
        useDatasetStore.getState().resetState();
    } catch (error) {
        console.warn('Failed to reset dataset store:', error);
    }

    try {
        useChatStore.getState().resetState();
    } catch (error) {
        console.warn('Failed to reset chat store:', error);
    }

    try {
        clearInsightsDataCache();
    } catch (error) {
        console.warn('Failed to clear insights data cache:', error);
    }

    USER_SCOPED_STORAGE_KEYS.forEach((key) => {
        localStorage.removeItem(key);
        sessionStorage.removeItem(key);
    });

    // Also clear the persisted auth (user only — token is in HttpOnly cookie)
    localStorage.removeItem('signal-auth');
    sessionStorage.removeItem('signal-auth');
};

const useAuthStore = create(
    persist(
        (set) => ({
            user: null,
            loading: true,
            sessions: [],
            sessionsLoading: false,
            _hasHydrated: false,

            // Verify the session is still valid by calling /auth/me.
            // Auth is handled by the HttpOnly cookie (auto-sent by browser).
            // No token is stored in JavaScript — the cookie is managed by the backend.
            verifyToken: async () => {
                // Short-circuit: if already verified, skip the API call entirely.
                // This prevents duplicate /auth/me calls caused by React StrictMode
                // double-firing effects in development (the most common source of
                // duplicate auth requests on page load).
                const current = useAuthStore.getState();
                if (current.user && !current.loading) {
                    return true;
                }

                try {
                    const response = await api.get('/auth/me');
                    set({ user: response.data, loading: false });
                    return true;
                } catch (error) {
                    console.error('Session verification failed:', error);
                    const status = error.response?.status;
                    if (status === 401 || status === 403) {
                        // Session expired or invalid — clear local state
                        set({ user: null, loading: false });
                    } else {
                        // Network error or server down — keep user state for offline UX
                        set({ loading: false });
                    }
                    return false;
                }
            },

            login: async (email, password) => {
                try {
                    const response = await api.post('/auth/login', { email, password });
                    const { user: userData } = response.data;

                    // Security: never carry user-scoped caches across logins
                    clearUserScopedClientState();

                    // Persist user info for instant rehydration on page reload.
                    // Auth token is stored in an HttpOnly cookie by the backend.
                    set({ user: userData, loading: false });

                    // Initialize workspace context immediately so role is available
                    useWorkspaceStore.getState().fetchAndSetContext();

                    return { success: true };
                } catch (error) {
                    return { success: false, error: error.response?.data?.detail || 'Login failed' };
                }
            },

            register: async (email, password, username) => {
                try {
                    await api.post('/auth/register', {
                        email,
                        password,
                        username
                    });
                    return { success: true, message: 'Registration successful! Please login.' };
                } catch (error) {
                    return { success: false, error: error.response?.data?.detail || 'Registration failed' };
                }
            },

            googleLogin: () => {
                const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
                window.location.href = `${baseURL}/auth/google`;
            },

            // Phase 2: Cookie-based auth — the backend sets the HttpOnly cookie during
            // the Google OAuth redirect. The frontend just needs to verify the session.
            verifyGoogleSession: async () => {
                clearUserScopedClientState();
                set({ loading: true });
                try {
                    const response = await api.get('/auth/me');
                    set({ user: response.data, loading: false });
                    return true;
                } catch (error) {
                    console.error('Failed to verify session after Google login:', error);
                    set({ loading: false });
                    return false;
                }
            },

            updateProfile: async (profileData) => {
                try {
                    const response = await api.put('/auth/profile', profileData);
                    const updatedUser = response.data;
                    set((state) => ({
                        user: {
                            ...state.user,
                            ...updatedUser,
                        },
                    }));
                    return { success: true, user: updatedUser };
                } catch (error) {
                    return {
                        success: false,
                        error: error.response?.data?.detail || 'Failed to update profile',
                    };
                }
            },

            changePassword: async (oldPassword, newPassword) => {
                try {
                    await api.post('/auth/change-password', {
                        old_password: oldPassword,
                        new_password: newPassword,
                    });
                    return { success: true };
                } catch (error) {
                    return {
                        success: false,
                        error: error.response?.data?.detail || 'Failed to change password',
                    };
                }
            },

            logout: async () => {
                try {
                    // Ask the backend to revoke this session + clear the HttpOnly cookies
                    await api.post('/auth/logout');
                } catch (error) {
                    console.warn('Logout API call failed, clearing local state anyway:', error);
                }
                // Clear local state regardless of API success
                set({ user: null, loading: false });
                clearUserScopedClientState();
                useWorkspaceStore.getState().reset();
            },

            // ── Per-device session management ──────────────────────────────

            fetchSessions: async () => {
                try {
                    set({ sessionsLoading: true });
                    const response = await authAPI.listSessions();
                    set({ sessions: response.data.sessions || [], sessionsLoading: false });
                    return response.data.sessions || [];
                } catch (error) {
                    set({ sessionsLoading: false });
                    return [];
                }
            },

            revokeSession: async (sessionId) => {
                try {
                    await authAPI.revokeSession(sessionId);
                    set((state) => ({
                        sessions: state.sessions.filter((s) => s.jti !== sessionId),
                    }));
                    return { success: true };
                } catch (error) {
                    return {
                        success: false,
                        error: error.response?.data?.detail || 'Failed to revoke session',
                    };
                }
            },

            logoutAll: async () => {
                try {
                    await authAPI.logoutAll();
                } catch (error) {
                    console.warn('Logout-all API call failed:', error);
                }
                // This device keeps its session (the server kept it) — just
                // drop the other devices from the list.
                set((state) => ({
                    sessions: (state.sessions || []).filter((s) => s.is_current),
                }));
                return { success: true };
            },

            // Called when the server revokes THIS session while the app is
            // open (e.g. the user logged out on another device and the WS
            // push arrived). No API call — the server already did the work.
            handleSessionRevoked: () => {
                set({ user: null, loading: false, sessions: [] });
                clearUserScopedClientState();
                useWorkspaceStore.getState().reset();
            },
        }),
        {
            name: 'signal-auth',
            // Use whichever storage backend has the auth data
            storage: createJSONStorage(() => getStorageBackend()),
            // Only persist user info for instant rehydration.
            // Auth token is in an HttpOnly cookie (Phase 1+) — not stored in JS.
            partialize: (state) => ({ user: state.user }),
            // Called when store is rehydrated from storage
            onRehydrateStorage: () => {
                return (state, error) => {
                    if (error) {
                        console.error('Auth rehydration error:', error);
                        return;
                    }
                    if (state?.user) {
                        console.log('Auth rehydrated, user:', state.user.email);
                        // Also init workspace context on rehydration so role is available immediately
                        useWorkspaceStore.getState().fetchAndSetContext();
                    }
                };
            },
        }
    )
);

// Initialize auth on app load - call this once in App.jsx
// On page load, the HttpOnly cookie is auto-sent with requests.
// Call /auth/me to verify the session and get the current user.
export const initAuth = async () => {
    const store = useAuthStore.getState();
    console.log('initAuth: Verifying session via /auth/me...');
    const verified = await store.verifyToken();
    if (verified) {
        await useWorkspaceStore.getState().fetchAndSetContext();
    }
};

// Convenience hook that matches the old Context API
export const useAuth = () => {
    const user = useAuthStore((state) => state.user);
    const loading = useAuthStore((state) => state.loading);
    const login = useAuthStore((state) => state.login);
    const register = useAuthStore((state) => state.register);
    const googleLogin = useAuthStore((state) => state.googleLogin);
    const verifyGoogleSession = useAuthStore((state) => state.verifyGoogleSession);
    const updateProfile = useAuthStore((state) => state.updateProfile);
    const changePassword = useAuthStore((state) => state.changePassword);
    const logout = useAuthStore((state) => state.logout);
    const logoutAll = useAuthStore((state) => state.logoutAll);
    const fetchSessions = useAuthStore((state) => state.fetchSessions);
    const revokeSession = useAuthStore((state) => state.revokeSession);
    const sessions = useAuthStore((state) => state.sessions);
    const sessionsLoading = useAuthStore((state) => state.sessionsLoading);
    const hasHydrated = useAuthStore((state) => state._hasHydrated);

    return {
        user,
        login,
        register,
        googleLogin,
        verifyGoogleSession,
        updateProfile,
        changePassword,
        logout,
        logoutAll,
        fetchSessions,
        revokeSession,
        sessions,
        sessionsLoading,
        loading,
        hasHydrated,
        isAuthenticated: !!user,
    };
};

export default useAuthStore;
