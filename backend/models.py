from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String, unique=True, index=True, nullable=False)
    email           = Column(String, unique=True, index=True, nullable=False) 
    role           = Column(String, unique=True, index=True, nullable=False) 
    hashed_password = Column(String, nullable=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())


class APIClient(Base):
    """API clients for external access with client_id/secret authentication."""
    __tablename__ = "api_clients"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String, nullable=False)
    client_id     = Column(String, unique=True, index=True, nullable=False)
    hashed_secret = Column(String, nullable=False)
    created_by    = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active     = Column(Boolean, default=True, nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
