import logging
from datetime import datetime, timedelta
from typing import Optional
import uuid
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings
from models import UserCreate, UserInDB, UserResponse, TokenData, UserLogin
from database import get_collection

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = settings.secret_key or "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Security scheme
security = HTTPBearer()


class AuthService:
    def __init__(self):
        self._users_collection = None
    
    @property
    def users_collection(self):
        if self._users_collection is None:
            self._users_collection = get_collection("users")
        return self._users_collection
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[TokenData]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                return None
            return TokenData(user_id=user_id)
        except JWTError:
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """Get a user by email."""
        try:
            user_data = await self.users_collection.find_one({"email": email})
            if user_data:
                # Convert MongoDB _id to id for Pydantic model
                user_data["id"] = user_data.pop("_id")
                return UserInDB(**user_data)
            return None
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            return None
    
    async def get_user_by_id(self, user_id: str) -> Optional[UserInDB]:
        """Get a user by ID."""
        try:
            user_data = await self.users_collection.find_one({"_id": user_id})
            if user_data:
                # Convert MongoDB _id to id for Pydantic model
                user_data["id"] = user_data.pop("_id")
                return UserInDB(**user_data)
            return None
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None
    
    async def create_user(self, user_create: UserCreate) -> UserResponse:
        """Create a new user."""
        # Check if user already exists
        existing_user = await self.get_user_by_email(user_create.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create user
        user_id = str(uuid.uuid4())
        hashed_password = self.get_password_hash(user_create.password)
        
        user_data = {
            "_id": user_id,
            "email": user_create.email,
            "full_name": user_create.full_name,
            "hashed_password": hashed_password,
            "is_active": user_create.is_active,
            "created_at": datetime.utcnow(),
            "last_login": None
        }
        
        try:
            await self.users_collection.insert_one(user_data)
            
            # Return user without password
            return UserResponse(
                id=user_id,
                email=user_create.email,
                full_name=user_create.full_name,
                is_active=user_create.is_active,
                created_at=user_data["created_at"],
                last_login=None
            )
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error creating user"
            )
    
    async def authenticate_user(self, email: str, password: str) -> Optional[UserInDB]:
        """Authenticate a user with email and password."""
        user = await self.get_user_by_email(email)
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user
    
    async def login_user(self, user_login: UserLogin) -> dict:
        """Login a user and return access token."""
        user = await self.authenticate_user(user_login.email, user_login.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        
        # Update last login
        await self.users_collection.update_one(
            {"_id": user.id},
            {"$set": {"last_login": datetime.utcnow()}}
        )
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = self.create_access_token(
            data={"sub": user.id}, expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": UserResponse(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                created_at=user.created_at,
                last_login=datetime.utcnow()
            )
        }
    
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserInDB:
        """Get the current authenticated user."""
        token = credentials.credentials
        token_data = self.verify_token(token)
        if token_data is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = await self.get_user_by_id(token_data.user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user


# Create auth service instance
auth_service = AuthService()

# Dependency to get current user
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserInDB:
    return await auth_service.get_current_user(credentials)
