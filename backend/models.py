from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Boolean,
    DateTime,
    ForeignKey
)

from sqlalchemy.orm import relationship

from datetime import datetime

from .database import Base


class Role(Base):

    __tablename__ = "roles"

    role_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    role_name = Column(
        String(50),
        unique=True,
        nullable=False
    )

    users = relationship(
        "UserProfile",
        back_populates="role"
    )


class UserProfile(Base):

    __tablename__ = "user_profiles"

    user_id = Column(
        String,
        primary_key=True
    )

    user_fname = Column(
        String(100),
        nullable=False
    )

    user_lname = Column(
        String(100),
        nullable=False
    )

    role_id = Column(
        BigInteger,
        ForeignKey("roles.role_id"),
        nullable=False
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    role = relationship(
        "Role",
        back_populates="users"
    )