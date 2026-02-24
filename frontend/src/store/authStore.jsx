import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import axios from 'axios';
import useDatasetStore from './datasetStore';
import useChatStore from './chatStore';
import useChatHistoryStore from './chatHistoryStore';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const USER_SCOPED_STORAGE_KEYS = ['dataset-storage', 'datasage-chat-store', 'chat-history-storage'];

/**
 * Determine the storage backend based on the user's "Remember me" preference.
 * Defaults to localStorage (persistent). When "Remember me" is unchecked,
 * sessionStorage is used so the session dies when the browser closes.
 */
const getStorageBackend = () => {
    // Check if we previously chose sessionStorage
    if (sessionStorage.getItem('datasage-auth')) {
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
        useChatHistoryStore.getState().resetState();
    } catch (error) {
        console.warn('Failed to reset chat history store:', error);
    }

    USER_SCOPED_STORAGE_KEYS.forEach((key) => {
        localStorage.removeItem(key);
        sessionStorage.removeItem(key);
    });
};

const useAuthStore = create(
    persist(
        (set, get) => ({
            user: null,
            token: null,
            loading: true,
            _hasHydrated: false,

            // Verify token and get user info
            verifyToken: async () => {
                const token = get().token;
                if (!token) {
                    set({ loading: false });
                    return false;
                }

                axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;

                try {
                    const response = await axios.get(`${API_URL}/auth/me`);
                    set({ user: response.data, loading: false });
                    return true;
                } catch (error) {
                    console.error('Token verification failed:', error);
                    // Only logout on definitive auth failures (401/403), not network errors
                    const status = error.response?.status;
                    if (status === 401 || status === 403) {
                        get().logout();
                    } else {
                        // Network error or server down — keep the persisted user/token
                        // so the app remains usable with cached data
                        set({ loading: false });
                    }
                    return false;
                }
            },

            login: async (email, password, rememberMe = true) => {
                try {
                    const response = await axios.post(`${API_URL}/auth/login`, { email, password });
                    const { access_token, user: userData } = response.data;

                    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

                    // Security: never carry user-scoped caches across logins
                    clearUserScopedClientState();

                    // If "Remember me" is unchecked, migrate to sessionStorage
                    if (!rememberMe) {
                        // Clear any existing localStorage entry
                        localStorage.removeItem('datasage-auth');
                        // The persist middleware will be reconfigured below
                        useAuthStore.persist.setOptions({
                            storage: createJSONStorage(() => sessionStorage),
                        });
                    } else {
                        // Ensure we're using localStorage
                        sessionStorage.removeItem('datasage-auth');
                        useAuthStore.persist.setOptions({
                            storage: createJSONStorage(() => localStorage),
                        });
                    }

                    set({ token: access_token, user: userData, loading: false });

                    // Force a rehydration write to the correct storage
                    useAuthStore.persist.rehydrate();

                    return { success: true };
                } catch (error) {
                    return { success: false, error: error.response?.data?.detail || 'Login failed' };
                }
            },

            register: async (email, password, username) => {
                try {
                    await axios.post(`${API_URL}/auth/register`, {
                        email,
                        password,
                        username
                    });
                    return { success: true, message: 'Registration successful! Please login.' };
                } catch (error) {
                    return { success: false, error: error.response?.data?.detail || 'Registration failed' };
                }
            },

            updateProfile: async (profileData) => {
                try {
                    const response = await axios.put(`${API_URL}/auth/profile`, profileData);
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
                    await axios.post(`${API_URL}/auth/change-password`, {
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

            logout: () => {
                delete axios.defaults.headers.common['Authorization'];
                set({ token: null, user: null, loading: false });
                clearUserScopedClientState();
                // Clear from both storage backends
                localStorage.removeItem('datasage-auth');
                sessionStorage.removeItem('datasage-auth');
            },
        }),
        {
            name: 'datasage-auth',
            // Use whichever storage backend has the auth data
            storage: createJSONStorage(() => getStorageBackend()),
            // Persist both token AND user for instant rehydration
            partialize: (state) => ({ token: state.token, user: state.user }),
            // Called when store is rehydrated from storage
            onRehydrateStorage: () => {
                return (state, error) => {
                    if (error) {
                        console.error('Auth rehydration error:', error);
                        useAuthStore.setState({ _hasHydrated: true, loading: false });
                        return;
                    }
                    // Mark hydration as complete
                    useAuthStore.setState({ _hasHydrated: true });
                    // Set axios header immediately if token exists
                    if (state?.token) {
                        console.log('Auth rehydrated, token found, user:', state.user ? 'present' : 'missing');
                        axios.defaults.headers.common['Authorization'] = `Bearer ${state.token}`;
                    }
                };
            },
        }
    )
);

// Initialize auth on app load - call this once in App.jsx
export const initAuth = async () => {
    const store = useAuthStore.getState();

    // Wait for rehydration to complete
    if (store.token) {
        console.log('initAuth: Token found, verifying...');
        await store.verifyToken();
    } else {
        console.log('initAuth: No token found');
        useAuthStore.setState({ loading: false });
    }
};

// Convenience hook that matches the old Context API
export const useAuth = () => {
    const user = useAuthStore((state) => state.user);
    const token = useAuthStore((state) => state.token);
    const loading = useAuthStore((state) => state.loading);
    const login = useAuthStore((state) => state.login);
    const register = useAuthStore((state) => state.register);
    const updateProfile = useAuthStore((state) => state.updateProfile);
    const changePassword = useAuthStore((state) => state.changePassword);
    const logout = useAuthStore((state) => state.logout);
    const hasHydrated = useAuthStore((state) => state._hasHydrated);

    return {
        user,
        token,
        login,
        register,
        updateProfile,
        changePassword,
        logout,
        loading,
        hasHydrated,
        isAuthenticated: !!user && !!token,
    };
};

export default useAuthStore;
