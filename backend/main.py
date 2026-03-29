from contextlib import asynccontextmanager
from datetime import timedelta, datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import bcrypt
import uvicorn

from dotenv import load_dotenv
load_dotenv()

from config import DATABASE_TYPE
from database import engine, get_db, Base
from models import User, APIClient
from schemas import (
    EncryptedRequest, UserResponse, LoginResponse,
    APIClientCreate, APIClientResponse, APIClientCreateResponse,
    APIClientListResponse, UserDetailsResponse, ToggleRoleResponse
)
from crypto_utils import decrypt_payload
from auth import (
    create_access_token, get_current_user, get_current_user_or_api_client,
    generate_client_credentials, hash_client_secret,
    TokenData, APIClientData, JWT_ACCESS_TOKEN_EXPIRE_MINUTES
)
from rate_limiter import limiter, rate_limit_exceeded_handler

if DATABASE_TYPE == "mongo":
    from database_mongo import connect_to_mongo, close_mongo_connection, get_database
    from models_mongo import UserCollection, APIClientCollection


@asynccontextmanager
async def lifespan(app: FastAPI):
    if DATABASE_TYPE == "sqlite":
        Base.metadata.create_all(bind=engine)
    elif DATABASE_TYPE == "mongo":
        await connect_to_mongo()
        db = get_database()
        await UserCollection.create_indexes(db)
        await APIClientCollection.create_indexes(db)
    yield
    if DATABASE_TYPE == "mongo":
        await close_mongo_connection()

app = FastAPI(lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# ============================================================================
# Public Endpoints (No Authentication Required)
# ============================================================================

@app.post("/auth/register", response_model=UserResponse)
async def register(request: EncryptedRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    try:
        data        = decrypt_payload(request.encrypted)
        username    = data["username"]
        email       = data["email"]
        password    = data["password"]
        role        = data.get("role", "guest")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid encrypted data",
        )

    if len(password.encode('utf-8')) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password too long (max 72 bytes)",
        )

    if DATABASE_TYPE == "mongo":
        mongo_db = get_database()

        if await UserCollection.find_by_username(mongo_db, username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered",
            )

        if await UserCollection.find_by_email(mongo_db, email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        hashed_password = get_password_hash(password)
        user_data = {
            "username"          : username,
            "email"             : email,
            "role"              : role,
            "hashed_password"   : hashed_password,
        }
        created_user = await UserCollection.create(mongo_db, user_data)
        return UserResponse(
            id=str(created_user["_id"]),
            username    =created_user["username"],
            email       =created_user["email"],
            role        =created_user["role"],
        )

    db_user = db.query(User).filter(User.username == username).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    db_user = db.query(User).filter(User.email == email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    hashed_password = get_password_hash(password)
    print(role)
    db_user = User(
        username        =username,
        email           =email,
        role            =role,
        hashed_password =hashed_password,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return UserResponse(
        id=str(db_user.id),
        username=db_user.username,
        email=db_user.email,
        role=db_user.role,
    )


@app.post("/auth/login", response_model=LoginResponse)
async def login(request: EncryptedRequest, db: Session = Depends(get_db)):
    """
    Login and receive a JWT token.

    The token should be included in subsequent requests as:
    Authorization: Bearer <token>
    """
    try:
        data = decrypt_payload(request.encrypted)
        username = data["username"]
        password = data["password"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid encrypted data",
        )

    if DATABASE_TYPE == "mongo":
        mongo_db = get_database()
        db_user = await UserCollection.find_by_username(mongo_db, username)

        if not db_user or not verify_password(password, db_user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        # Create JWT token
        access_token = create_access_token(
            data={
                "user_id"       : str(db_user["_id"]),
                "username"      : db_user["username"],
                "role"          : db_user["role"],
                "token_type"    : "user",
            },
            expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse(
                id=str(db_user["_id"]),
                username=db_user["username"],
                email=db_user["email"],
                role=db_user["role"]
            ),
        )


    db_user = db.query(User).filter(User.username == username).first()

    if not db_user or not verify_password(password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )


    access_token = create_access_token(
        data={
            "user_id": str(db_user.id),
            "username": db_user.username,
            "role": db_user.role,
            "token_type": "user",
        },
        expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return LoginResponse(
         
        access_token=access_token,
        token_type="bearer",
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            id=str(db_user.id),
            username=db_user.username,
            email=db_user.email,
            role=db_user.role
        ),
    )


# ============================================================================
# Protected Endpoints (JWT or API Key Authentication Required)
# ============================================================================

@app.get("/health")
@limiter.limit("60/minute")
async def health_check(
    request: Request,
    auth: TokenData | APIClientData = Depends(get_current_user_or_api_client)
):
    """
    Health check endpoint - requires authentication.

    Accepts either:
    - JWT Bearer token (for logged-in users)
    - API credentials (X-API-Key and X-API-Secret headers for external clients)
    """
    return {
        "status": "ok",
        "authenticated_as": auth.username if isinstance(auth, TokenData) else auth.client_name,
        "auth_type": auth.token_type,
    }


@app.get("/get_user_details", response_model=UserDetailsResponse)
@limiter.limit("60/minute")
async def get_user_details(
    request: Request,
    auth: TokenData | APIClientData = Depends(get_current_user_or_api_client),
    db: Session = Depends(get_db),
):
    """
    Get details of the authenticated user or API client.

    Accepts either:
    - JWT Bearer token (for logged-in users)
    - API credentials (X-API-Key and X-API-Secret headers for external clients)
    """
    if isinstance(auth, TokenData):
 
        if DATABASE_TYPE == "mongo":
            mongo_db = get_database()
            user = await UserCollection.find_by_id(mongo_db, auth.user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )
            return UserDetailsResponse(
                id=str(user["_id"]),
                username=user["username"],
                email=user["email"],
                role=user["role"],
                auth_type="user",
            )
        else:
            user = db.query(User).filter(User.id == int(auth.user_id)).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )
            return UserDetailsResponse(
                id=str(user.id),
                username=user.username,
                email=user.email,
                role=user.role,
                auth_type="user",
            )
    else:
        return UserDetailsResponse(
            id=auth.client_id,
            username=auth.client_name,
            email="",
            auth_type="api_client",
            client_name=auth.client_name,
        )


@app.put("/user/toggle-role", response_model=ToggleRoleResponse)
@limiter.limit("10/minute")
async def toggle_role(
    request: Request,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Toggle the current user's role between 'admin' and 'guest'.
    Returns a new JWT token with the updated role.

    Requires JWT authentication.
    """
    new_role = "guest" if current_user.role == "admin" else "admin"

    if DATABASE_TYPE == "mongo":
        mongo_db = get_database()
        updated_user = await UserCollection.update_role(mongo_db, current_user.user_id, new_role)

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        access_token = create_access_token(
            data={
                "user_id": str(updated_user["_id"]),
                "username": updated_user["username"],
                "role": new_role,
                "token_type": "user",
            },
            expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        return ToggleRoleResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse(
                id=str(updated_user["_id"]),
                username=updated_user["username"],
                email=updated_user["email"],
                role=new_role,
            ),
            message=f"Role changed from '{current_user.role}' to '{new_role}'",
        )

    # SQLite path
    db_user = db.query(User).filter(User.id == int(current_user.user_id)).first()

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    db_user.role = new_role
    db.commit()
    db.refresh(db_user)

    access_token = create_access_token(
        data={
            "user_id": str(db_user.id),
            "username": db_user.username,
            "role": new_role,
            "token_type": "user",
        },
        expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return ToggleRoleResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            id=str(db_user.id),
            username=db_user.username,
            email=db_user.email,
            role=new_role,
        ),
        message=f"Role changed from '{current_user.role}' to '{new_role}'",
    )


# ============================================================================
# API Client Management (JWT Authentication Required)
# ============================================================================

@app.post("/api-clients", response_model=APIClientCreateResponse)
async def create_api_client(
    client_data: APIClientCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new API client for external access.

    Returns the client_id and client_secret. The secret is only shown once
    and must be stored securely by the user.

    Requires JWT authentication.
    """
    client_id, client_secret = generate_client_credentials()
    hashed_secret = hash_client_secret(client_secret)

    if DATABASE_TYPE == "mongo":
        mongo_db = get_database()
        client_doc = {
            "name"              : client_data.name,
            "client_id"         : client_id,
            "hashed_secret"     : hashed_secret,
            "created_by"        : current_user.user_id,
            "is_active"         : True,
            "created_at"        : datetime.now(timezone.utc),
        }
        created_client = await APIClientCollection.create(mongo_db, client_doc)
        return APIClientCreateResponse(
            id=str(created_client["_id"]),
            name=created_client["name"],
            client_id=created_client["client_id"],
            client_secret=client_secret,
            is_active=True,
            created_at=created_client["created_at"],
        )

    # SQLite path
    db_client = APIClient(
        name=client_data.name,
        client_id=client_id,
        hashed_secret=hashed_secret,
        created_by=int(current_user.user_id),
        is_active=True,
    )
    db.add(db_client)
    db.commit()
    db.refresh(db_client)

    return APIClientCreateResponse(
        id=str(db_client.id),
        name=db_client.name,
        client_id=db_client.client_id,
        client_secret=client_secret,
        is_active=db_client.is_active,
        created_at=db_client.created_at,
    )

@app.get("/api-clients", response_model=APIClientListResponse)
async def list_api_clients(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all API clients created by the current user.

    Requires JWT authentication.
    """
    if DATABASE_TYPE == "mongo":
        mongo_db = get_database()
        clients = await APIClientCollection.find_by_user(mongo_db, current_user.user_id)
        return APIClientListResponse(
            clients=[
                APIClientResponse(
                    id=str(c["_id"]),
                    name=c["name"],
                    client_id=c["client_id"],
                    is_active=c.get("is_active", True),
                    created_at=c["created_at"],
                )
                for c in clients
            ]
        )

    clients = db.query(APIClient).filter(
        APIClient.created_by == int(current_user.user_id)
    ).all()

    return APIClientListResponse(
        clients=[
            APIClientResponse(
                id=str(c.id),
                name=c.name,
                client_id=c.client_id,
                is_active=c.is_active,
                created_at=c.created_at,
            )
            for c in clients
        ]
    )

@app.delete("/api-clients/{client_id}")
async def revoke_api_client(
    client_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Revoke (deactivate) an API client.

    Requires JWT authentication. Users can only revoke their own clients.
    """
    if DATABASE_TYPE == "mongo":
        mongo_db = get_database()
        success = await APIClientCollection.deactivate(
            mongo_db, client_id, current_user.user_id
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API client not found or already revoked",
            )
        return {"message": "API client revoked successfully"}

    # SQLite path
    db_client = db.query(APIClient).filter(
        APIClient.client_id == client_id,
        APIClient.created_by == int(current_user.user_id),
    ).first()

    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API client not found",
        )

    db_client.is_active = False
    db.commit()

    return {"message": "API client revoked successfully"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
