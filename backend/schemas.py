from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class EncryptedRequest(BaseModel):
    encrypted: str

class UserCreate(BaseModel):
    username    : str
    email       : EmailStr
    password    : str
    role        : str

class UserLogin(BaseModel):
    username    : str
    password    : str

class UserResponse(BaseModel):
    id          : str
    username    : str
    email       : str
    role        : str

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

class APIClientCreate(BaseModel):
    name: str

class APIClientResponse(BaseModel):
    id: str
    name: str
    client_id: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class APIClientCreateResponse(BaseModel):
    """Response when creating a new API client - includes the secret (shown only once)."""
    id: str
    name: str
    client_id: str
    client_secret: str  # Only shown once at creation
    is_active: bool
    created_at: datetime
    message: str = "Store the client_secret securely. It will not be shown again."

class APIClientListResponse(BaseModel):
    clients: list[APIClientResponse]

class UserDetailsResponse(BaseModel):
    id: str
    username: str
    email: str
    role: Optional[str] = None
    auth_type: str
    client_name: Optional[str] = None


class ToggleRoleResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
    message: str
