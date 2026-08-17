/**
 * authStorage — Centralized reader for persisted user state.
 *
 * Exists to break the circular dependency between authStore and datasetStore.
 * Both stores persist to localStorage/sessionStorage. datasetStore needs to
 * know the current user ID but cannot import authStore without creating a
 * cycle (authStore imports datasetStore for clearUserScopedClientState).
 *
 * This module is dependency-free — it reads raw storage only.
 *
 * IMPORTANT: This module reads the persisted USER object, NOT the auth token.
 * Auth tokens are now stored in HttpOnly cookies (Phase 1+) and are not
 * accessible to JavaScript. See core/auth.py on the backend.
 *
 * Usage:
 *   import { getCurrentUserId } from './authStorage';
 *   const userId = getCurrentUserId();
 */

const AUTH_STORAGE_KEY = 'signal-auth';

/**
 * Parse persisted auth state from a specific storage backend.
 * Returns { user } or null.
 */
function parseAuthState(storage) {
  try {
    const raw = storage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.state || null;
  } catch {
    return null;
  }
}

/**
 * Return the active auth state from whichever storage backend has persisted user info.
 */
function getActiveAuthState() {
  if (typeof window === 'undefined') return null;

  const sessionState = parseAuthState(window.sessionStorage);
  const localState = parseAuthState(window.localStorage);

  return sessionState || localState;
}

/**
 * Get the current user ID from whichever storage backend has persisted user data.
 * Checks sessionStorage first (for "don't remember me" sessions), then
 * localStorage (for persistent sessions).
 */
export function getCurrentUserId() {
  const state = getActiveAuthState();
  return state?.user?.id || null;
}
