from fastapi import HTTPException, Depends, status
from passlib.context import CryptContext
from core.auth import get_token_from_request
from core.config import settings
import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
import os
import time
from db.database import get_database
from db.schemas import User, UserCreate, UserLogin, Token, TokenData, LoginResponse
from services.workspace import workspace_service
from services.auth.sessions import (
    hash_refresh_token,
    generate_refresh_token,
    revoked_jti_store,
    session_store,
)
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class DatabaseUnavailableError(Exception):
    """Raised when the database is unreachable or times out."""
    pass


class UserCache:
    """Simple in-memory cache for user objects with TTL.

    When MongoDB is temporarily unreachable, cached user data
    allows the auth layer to continue validating users without
    forcing a logout on every request.
    """

    def __init__(self, ttl_seconds: int = 30):
        self._cache: dict[str, dict] = {}
        self._ttl = ttl_seconds

    def get(self, user_id: str) -> Optional[dict]:
        entry = self._cache.get(user_id)
        if entry and time.time() - entry["ts"] < self._ttl:
            return entry["user"]
        return None

    def get_stale(self, user_id: str) -> Optional[dict]:
        """Return user even if TTL expired — used as fallback when DB is down."""
        entry = self._cache.get(user_id)
        if entry:
            return entry["user"]
        return None

    def set(self, user_id: str, user: dict):
        self._cache[user_id] = {"user": user, "ts": time.time()}

    def invalidate(self, user_id: str):
        self._cache.pop(user_id, None)

# JWT settings - SECURITY CRITICAL
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError(
        "FATAL: SECRET_KEY environment variable is required. "
        'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
    )
if len(SECRET_KEY) < 32:
    raise ValueError(
        f"FATAL: SECRET_KEY must be at least 32 characters (got {len(SECRET_KEY)}). "
        'Generate a secure key with: python -c "import secrets; print(secrets.token_hex(32))"'
    )
ALGORITHM = settings.ALGORITHM or "HS256"
# Short-lived access token (default 50 min). Long-lived sessions are
# maintained by refresh-token rotation — see services/auth/sessions.py.
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

class AuthService:
    def __init__(self):
        self.db = None
        self._user_cache = UserCache(ttl_seconds=30)

    async def get_user_from_token(self, token: str) -> Optional[dict]:
        """Decode JWT token and return user - for WebSocket auth"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                return None
            # Reject tokens whose session was revoked (logout / logout-all)
            jti = payload.get("jti")
            if jti and revoked_jti_store.is_revoked(jti):
                logger.debug(f"Rejecting WebSocket auth — session {jti[:8]} revoked")
                return None
        except JWTError:
            return None

        try:
            user = await self.get_user_by_id(user_id)
            if user is not None:
                # Attach the tenant boundary from the JWT (set at login) so
                # WebSocket callers resolve the same personal workspace id that
                # HTTP writes/reads use — prevents upload→404 mismatches.
                if payload.get("workspace_id"):
                    user["workspace_id"] = payload.get("workspace_id")
                if payload.get("jti"):
                    user["jti"] = payload.get("jti")
            return user
        except DatabaseUnavailableError:
            logger.warning(f"DB unavailable for WebSocket auth (user {user_id}) — rejecting connection")
            return None

    def _get_db(self):
        """Get database connection"""
        if self.db is None:
            self.db = get_database()
        return self.db

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        try:
            # Use direct bcrypt for better compatibility
            return bcrypt.checkpw(
                plain_password.encode("utf-8"), hashed_password.encode("utf-8")
            )
        except Exception as e:
            logger.error(f"Password verification failed: {e}")
            return False

    def get_password_hash(self, password: str) -> str:
        """Hash a password using bcrypt"""
        try:
            # Use direct bcrypt for better compatibility
            salt = bcrypt.gensalt(rounds=12)
            hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
            return hashed.decode("utf-8")
        except Exception as e:
            logger.error(f"Password hashing failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password hashing failed",
            )

    def create_access_token(
        self,
        data: dict,
        expires_delta: Optional[timedelta] = None,
        jti: Optional[str] = None,
    ):
        """Create JWT access token.

        ``jti`` is the session id — lets ``get_current_user`` reject tokens
        whose session was revoked (via the in-memory denylist) without a
        per-request database hit.
        """
        to_encode = data.copy()
        if jti:
            to_encode["jti"] = jti
        if expires_delta:
            expire = datetime.now(timezone.utc).replace(tzinfo=None) + expires_delta
        else:
            expire = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user by email"""
        try:
            db = self._get_db()
            user = await db.users.find_one({"email": email})
            if user:
                user["id"] = str(user.pop("_id"))
            return user
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            return None

    async def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """Get user by ID — uses in-memory cache for resilience.

        Returns cached user data when MongoDB is temporarily unreachable,
        ensuring auth validation doesn't fail on transient DB issues.
        Raises DatabaseUnavailableError when DB is down and cache is empty.
        """
        # 1. Check fresh cache first
        cached = self._user_cache.get(user_id)
        if cached:
            return cached

        # 2. Query the database
        db = self._get_db()
        try:
            object_id = ObjectId(user_id)
        except Exception:
            object_id = user_id

        try:
            user = await db.users.find_one({"_id": object_id})
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            # DB is unreachable — try stale cache as fallback
            stale = self._user_cache.get_stale(user_id)
            if stale:
                logger.warning(f"Returning stale cached user {user_id} — DB unavailable")
                return stale
            # No cache entry at all — propagate as a DB error
            raise DatabaseUnavailableError(f"Database unavailable: {e}")

        if user:
            user["id"] = str(user.pop("_id"))
            self._user_cache.set(user_id, user)
        else:
            # User legitimately not found — invalidate any stale cache entry
            self._user_cache.invalidate(user_id)
        return user

    def decode_token(self, token: str) -> Optional[dict]:
        """Decode a JWT access token without triggering FastAPI dependencies."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: Optional[str] = payload.get("sub")
            email: Optional[str] = payload.get("email")
            if not user_id:
                return None
            return {"id": user_id, "email": email}
        except JWTError as exc:
            logger.warning(f"Failed to decode token: {exc}")
            return None

    async def create_user(self, user_data: UserCreate) -> dict:
        """Create a new user"""
        try:
            # Check if user already exists
            existing_user = await self.get_user_by_email(user_data.email)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )

            # Check if username already exists
            db = self._get_db()
            existing_username = await db.users.find_one(
                {"username": user_data.username}
            )
            if existing_username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken",
                )

            # Hash password
            hashed_password = self.get_password_hash(user_data.password)

            # Create user document
            user_doc = {
                "username": user_data.username,
                "email": user_data.email,
                "hashed_password": hashed_password,
                "is_active": True,
                "is_verified": False,
                "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
                "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
                "last_login": None,
            }

            # Insert user
            result = await db.users.insert_one(user_doc)
            user_doc["_id"] = str(result.inserted_id)

            # Convert _id to id for Pydantic model
            user_doc["id"] = user_doc.pop("_id")

            # Remove password from response
            user_doc.pop("hashed_password", None)

            # ── Auto-create personal workspace ──
            try:
                await workspace_service.create_personal_workspace(
                    user_id=user_doc["id"],
                    username=user_data.username,
                )
                logger.info(f"Personal workspace created for user: {user_data.email}")
            except Exception as ws_err:
                logger.warning(f"Failed to create personal workspace for {user_data.email}: {ws_err}")

            logger.info(f"User created successfully: {user_data.email}")
            return user_doc

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user",
            )

    async def authenticate_user(self, email: str, password: str) -> Optional[dict]:
        """Authenticate user with email and password"""
        try:
            user = await self.get_user_by_email(email)
            if not user:
                return None

            if not self.verify_password(password, user["hashed_password"]):
                return None

            # Update last login
            db = self._get_db()
            await db.users.update_one(
                {"_id": ObjectId(user["id"])},
                {"$set": {"last_login": datetime.now(timezone.utc).replace(tzinfo=None)}},
            )

            # Remove password from response
            user.pop("hashed_password", None)
            return user

        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            return None

    async def _resolve_user_workspace_id(self, user_id: str) -> str:
        """Resolve the default workspace ID for a user."""
        try:
            personal = await workspace_service.get_personal_workspace(user_id)
            if personal:
                return personal["id"]
        except Exception as e:
            logger.warning(f"Failed to resolve workspace for user {user_id}: {e}")
        return user_id  # Fallback to user_id for backward compatibility

    async def _issue_token_pair(
        self,
        user: dict,
        workspace_id: str,
        device_name: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> tuple:
        """Create a session and return (access_token, refresh_token).

        The access token carries the session's ``jti``; the refresh token is
        stored hashed in the ``sessions`` collection and rotated on refresh.
        """
        refresh_token = generate_refresh_token()
        session = await session_store.create_session(
            user_id=str(user["id"]),
            workspace_id=workspace_id,
            refresh_token=refresh_token,
            device_name=device_name,
            ip=ip,
            user_agent=user_agent,
        )
        access_token = self.create_access_token(
            data={
                "sub": str(user["id"]),
                "email": user.get("email"),
                "workspace_id": workspace_id,
            },
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            jti=session["jti"],
        )
        return access_token, refresh_token

    async def login_user(
        self,
        login_data: UserLogin,
        device_name: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> LoginResponse:
        """Login user and return access token with user data"""
        try:
            user = await self.authenticate_user(login_data.email, login_data.password)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect email or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            if not user.get("is_active", True):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Account is disabled",
                )

            # ── Resolve workspace for JWT ──
            workspace_id = await self._resolve_user_workspace_id(user["id"])

            access_token, refresh_token = await self._issue_token_pair(
                user, workspace_id, device_name=device_name, ip=ip, user_agent=user_agent
            )

            return LoginResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user=User(**user),
                refresh_token=refresh_token,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error logging in user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed"
            )

    async def google_oauth_user(
        self,
        email: str,
        name: str,
        google_id: str,
        picture: str = None,
        device_name: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> LoginResponse:
        """Handle Google OAuth user - find existing or create new user"""
        try:
            db = self._get_db()

            existing_user = await db.users.find_one({"email": email})

            if existing_user:
                existing_user["id"] = str(existing_user.pop("_id"))

                if not existing_user.get("is_active", True):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Account is disabled",
                    )

                await db.users.update_one(
                    {"_id": ObjectId(existing_user["id"])},
                    {"$set": {"last_login": datetime.now(timezone.utc).replace(tzinfo=None)}},
                )

                user = existing_user
            else:
                username = name.replace(" ", "_").lower()
                base_username = username
                counter = 1
                while await db.users.find_one({"username": username}):
                    username = f"{base_username}{counter}"
                    counter += 1

                user_doc = {
                    "username": username,
                    "email": email,
                    "hashed_password": None,
                    "is_active": True,
                    "is_verified": True,
                    "google_id": google_id,
                    "avatar": picture,
                    "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
                    "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
                    "last_login": datetime.now(timezone.utc).replace(tzinfo=None),
                }

                result = await db.users.insert_one(user_doc)
                user_doc["_id"] = str(result.inserted_id)
                user_doc["id"] = user_doc.pop("_id")
                user_doc.pop("hashed_password", None)

                user = user_doc

                # ── Auto-create personal workspace for Google OAuth users ──
                try:
                    await workspace_service.create_personal_workspace(
                        user_id=user["id"],
                        username=username,
                    )
                    logger.info(f"Personal workspace created for Google user: {email}")
                except Exception as ws_err:
                    logger.warning(f"Failed to create personal workspace for {email}: {ws_err}")

                logger.info(f"Google OAuth user created: {email}")

            # ── Resolve workspace for JWT ──
            workspace_id = await self._resolve_user_workspace_id(user["id"])

            access_token, refresh_token = await self._issue_token_pair(
                user, workspace_id, device_name=device_name, ip=ip, user_agent=user_agent
            )

            return LoginResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user=User(**user),
                refresh_token=refresh_token,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in Google OAuth: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Google OAuth failed",
            )

    async def get_current_user(self, token: str) -> dict:
        """Get current authenticated user.

        ``token`` is a raw JWT string extracted from HttpOnly cookie or
        Authorization header by the ``get_token_from_request`` dependency.

        If the JWT is valid but the database is unreachable, returns 503 instead of
        401 so the frontend can retry rather than force-logout the user.
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not validate credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            # Session revoked (logout / logout-all / per-device revoke) — the
            # denylist check is O(1) and covers the access token's lifetime.
            jti = payload.get("jti")
            if jti and revoked_jti_store.is_revoked(jti):
                logger.debug(f"Rejecting request — session {jti[:8]} revoked")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session revoked — please log in again",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            user = await self.get_user_by_id(user_id)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            # Attach the tenant boundary from the JWT (resolved at login to the
            # user's personal workspace). Without this, routes that scope via
            # current_user.get("workspace_id", ...) fall back to the raw user_id
            # while reads resolve the personal workspace id — a mismatch that
            # made freshly-uploaded datasets 404 (get/stages/reprocess) while
            # still matching duplicate detection (409).
            if payload.get("workspace_id"):
                user["workspace_id"] = payload.get("workspace_id")
            if jti:
                user["jti"] = jti
            return user
        except DatabaseUnavailableError:
            # JWT is valid but DB is unreachable — don't log the user out
            logger.warning(f"DB unavailable during auth for user {user_id} — returning 503")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service is temporarily unavailable. Please try again.",
                headers={"Retry-After": "5"},
            )

    async def change_password(
        self, user_id: str, old_password: str, new_password: str
    ) -> bool:
        """Change user password"""
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )

            # Verify old password
            if not self.verify_password(old_password, user["hashed_password"]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Incorrect old password",
                )

            # Hash new password
            new_hashed_password = self.get_password_hash(new_password)

            # Update password
            from bson import ObjectId

            db = self._get_db()
            await db.users.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "hashed_password": new_hashed_password,
                        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
                    }
                },
            )

            # Invalidate cache so next auth fetch picks up the change
            self._user_cache.invalidate(user_id)

            logger.info(f"Password changed for user: {user_id}")
            return True

        except HTTPException:
            raise
        except DatabaseUnavailableError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable. Please try again.",
            )
        except Exception as e:
            logger.error(f"Error changing password: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to change password",
            )

    async def update_user_profile(
        self, user_id: str, profile_data: dict
    ) -> Optional[dict]:
        """Update user profile information"""
        try:
            db = self._get_db()
            from bson import ObjectId

            # Remove none values
            update_data = {k: v for k, v in profile_data.items() if v is not None}
            if not update_data:
                return await self.get_user_by_id(user_id)

            # If updating username, check for uniqueness
            if "username" in update_data:
                existing_username = await db.users.find_one(
                    {"username": update_data["username"]}
                )
                if existing_username and str(existing_username["_id"]) != user_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Username already taken",
                    )

            update_data["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None)

            await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})

            # Invalidate cache so next auth fetch picks up the change
            self._user_cache.invalidate(user_id)

            return await self.get_user_by_id(user_id)
        except HTTPException:
            raise
        except DatabaseUnavailableError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Profile service temporarily unavailable. Please try again.",
            )
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update profile",
            )


    # ──────────────────────────────────────────────────────────────────
    # Per-device session management (refresh-token rotation)
    # ──────────────────────────────────────────────────────────────────

    async def refresh_session(
        self, refresh_token: str, ip: Optional[str] = None
    ) -> tuple:
        """Validate + rotate a refresh token; returns (access_token, new_refresh_token).

        Raises 401 when the token is missing, expired, revoked, or reused.
        Presenting a previously-rotated token is treated as possible theft
        and revokes the entire session.
        """
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No refresh token provided",
            )

        refresh_hash = hash_refresh_token(refresh_token)
        session = await session_store.find_by_any_hash(refresh_hash)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session",
            )

        # Reuse of a rotated (old) token → possible theft → kill the session
        if session.get("prev_refresh_token_hash") == refresh_hash:
            logger.warning(
                f"Refresh-token reuse detected for session {session.get('jti', '')[:8]} — revoking"
            )
            await session_store.revoke(session["jti"])
            revoked_jti_store.revoke(session["jti"])
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session revoked",
            )

        if session.get("revoked_at"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session revoked",
            )

        if session.get("expires_at") and session["expires_at"] < datetime.now(
            timezone.utc
        ).replace(tzinfo=None):
            await session_store.revoke(session["jti"])
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired",
            )

        # ── Rotation: mint a new refresh token, keep the old as prev ──
        new_refresh_token = generate_refresh_token()
        await session_store.rotate(
            session["_id"],
            current_hash=session["refresh_token_hash"],
            new_refresh_token=new_refresh_token,
        )

        user_id = session.get("user_id")
        user = await self.get_user_by_id(user_id)
        access_token = self.create_access_token(
            data={
                "sub": user_id,
                "email": (user or {}).get("email") or session.get("email"),
                "workspace_id": session.get("workspace_id"),
            },
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            jti=session["jti"],
        )
        return access_token, new_refresh_token

    async def get_session_by_jti(self, jti: str) -> Optional[dict]:
        """Fetch a session document by jti (no refresh-token material)."""
        session = await session_store.get_by_jti(jti)
        if session:
            session.pop("refresh_token_hash", None)
            session.pop("prev_refresh_token_hash", None)
        return session

    async def revoke_session_by_jti(self, jti: str, user_id: str) -> bool:
        """Revoke one session (ownership-checked). Returns True if revoked."""
        if not jti:
            return False
        session = await session_store.get_by_jti(jti)
        if not session or session.get("user_id") != user_id:
            return False
        await session_store.revoke(jti)
        revoked_jti_store.revoke(jti)
        return True

    async def revoke_all_other_sessions(self, user_id: str, keep_jti: str) -> int:
        """Revoke every active session except the current one; returns count."""
        revoked = await session_store.revoke_all_except(user_id, keep_jti)
        for jti in revoked:
            revoked_jti_store.revoke(jti)
        return len(revoked)

    async def list_sessions(self, user_id: str) -> list:
        """Active sessions for the user (no refresh-token material)."""
        return await session_store.list_active(user_id)


# Create auth service instance
auth_service = AuthService()


# Dependency to get current user
async def get_current_user(
    token: str = Depends(get_token_from_request),
) -> dict:
    return await auth_service.get_current_user(token)
