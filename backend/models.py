from sqlalchemy import (
    Column,
    BigInteger,
    Date,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text
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

    employee_id = Column(
        String(50),
        unique=True,
        nullable=False
    )

    user_fname = Column(
        String(100),
        nullable=False
    )

    user_mname = Column(
        String(100),
    )

    user_lname = Column(
        String(100),
        nullable=False
    )

    user_birthdate = Column(
        Date
    )

    user_sex = Column(
        String(20)
    )

    user_contact_number = Column(
        String(30)
    )

    user_address = Column(
        Text
    )

    user_department = Column(
        String(100)
    )

    user_job_title = Column(
        String(100)
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

    last_login = Column(
        DateTime(timezone=True),
        nullable=True
    )

    role = relationship(
        "Role",
        back_populates="users"
    )