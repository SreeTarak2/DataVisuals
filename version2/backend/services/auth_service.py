from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import os
from db.database import get_database
from db.schemas import User, UserCreate, UserLogin, Token, TokenData, LoginResponse
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Security scheme
security = HTTPBearer()

class AuthService:
    def __init__(self):
        self.db = None
    
    def _get_db(self):
        """Get database connection"""
        if self.db is None:
            self.db = get_database()
        return self.db
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        try:
            # Use direct bcrypt for better compatibility
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification failed: {e}")
            return False
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password using bcrypt"""
        try:
            # Use direct bcrypt for better compatibility
            salt = bcrypt.gensalt(rounds=12)
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            return hashed.decode('utf-8')
        except Exception as e:
            logger.error(f"Password hashing failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password hashing failed"
            )
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
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
        """Get user by ID"""
        try:
            db = self._get_db()
            try:
                object_id = ObjectId(user_id)
            except Exception:
                object_id = user_id
            user = await db.users.find_one({"_id": object_id})
            if user:
                user["id"] = str(user.pop("_id"))
            return user
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None
    
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
                    detail="Email already registered"
                )
            
            # Check if username already exists
            db = self._get_db()
            existing_username = await db.users.find_one({"username": user_data.username})
            if existing_username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
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
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None
            }
            
            # Insert user
            result = await db.users.insert_one(user_doc)
            user_doc["_id"] = str(result.inserted_id)
            
            # Convert _id to id for Pydantic model
            user_doc["id"] = user_doc.pop("_id")
            
            # Remove password from response
            user_doc.pop("hashed_password", None)
            
            logger.info(f"User created successfully: {user_data.email}")
            return user_doc
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
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
                {"$set": {"last_login": datetime.utcnow()}}
            )
            
            # Remove password from response
            user.pop("hashed_password", None)
            return user
            
        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            return None
    
    async def login_user(self, login_data: UserLogin) -> LoginResponse:
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
                    detail="Account is disabled"
                )
            
            # Create access token
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = self.create_access_token(
                data={"sub": str(user["id"]), "email": user["email"]},
                expires_delta=access_token_expires
            )
            
            return LoginResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user=User(**user)
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error logging in user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Login failed"
            )
    
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
        """Get current authenticated user"""
        try:
            token = credentials.credentials
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not validate credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = await self.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
    
    async def update_user_profile(self, user_id: str, update_data: dict) -> dict:
        """Update user profile"""
        try:
            update_data["updated_at"] = datetime.utcnow()
            
            db = self._get_db()
            result = await db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Return updated user
            updated_user = await self.get_user_by_id(user_id)
            updated_user.pop("hashed_password", None)
            return updated_user
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update profile"
            )
    
    async def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """Change user password"""
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Verify old password
            if not self.verify_password(old_password, user["hashed_password"]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Incorrect old password"
                )
            
            # Hash new password
            new_hashed_password = self.get_password_hash(new_password)
            
            # Update password
            from bson import ObjectId
            db = self._get_db()
            await db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"hashed_password": new_hashed_password, "updated_at": datetime.utcnow()}}
            )
            
            logger.info(f"Password changed for user: {user_id}")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error changing password: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to change password"
            )

# Create auth service instance
auth_service = AuthService()

# Dependency to get current user
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    return await auth_service.get_current_user(credentials)


