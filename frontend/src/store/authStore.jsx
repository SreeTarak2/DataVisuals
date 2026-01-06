import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const useAuthStore = create(
    persist(
        (set, get) => ({
            user: null,
            token: null,
            loading: true,

            // Verify token and get user info
            verifyToken: async () => {
                const token = get().token;
                if (!token) {
                    set({ loading: false });
                    return;
                }

                axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;

                try {
                    const response = await axios.get(`${API_URL}/auth/me`);
                    set({ user: response.data, loading: false });
                } catch (error) {
                    console.error('Token verification failed:', error);
                    get().logout();
                }
            },

            login: async (email, password) => {
                try {
                    const response = await axios.post(`${API_URL}/auth/login`, { email, password });
                    const { access_token, user: userData } = response.data;

                    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
                    set({ token: access_token, user: userData, loading: false });

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

            logout: () => {
                delete axios.defaults.headers.common['Authorization'];
                set({ token: null, user: null, loading: false });
            },
        }),
        {
            name: 'datasage-auth',
            partialize: (state) => ({ token: state.token }), // Only persist token
            onRehydrate: () => (state) => {
                // Set axios header and verify token when store rehydrates
                if (state?.token) {
                    axios.defaults.headers.common['Authorization'] = `Bearer ${state.token}`;
                }
            },
        }
    )
);

// Initialize auth on app load - call this once in App.jsx
export const initAuth = () => {
    const store = useAuthStore.getState();
    if (store.token) {
        store.verifyToken();
    } else {
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
    const logout = useAuthStore((state) => state.logout);

    return {
        user,
        login,
        register,
        logout,
        loading,
        isAuthenticated: !!user,
    };
};

export default useAuthStore;
