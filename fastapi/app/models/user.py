import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, BigInteger, Column, DateTime, Enum, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class SexEnum(str, enum.Enum):
    M = "M"
    F = "F"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ProviderEnum(str, enum.Enum):
    KAKAO = "KAKAO"


class User(Base):
    __tablename__ = "User"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    birthdate = Column(DateTime(fsp=6), nullable=False)
    email = Column(String(255), nullable=False)
    sex = Column(Enum(SexEnum), nullable=False, default=SexEnum.M, server_default=SexEnum.M.value)
    createdAt = Column(DateTime(fsp=6), nullable=False, server_default=func.now())
    nickname = Column(String(20), nullable=False)
    updatedAt = Column(DateTime(fsp=6), nullable=False, server_default=func.now(), onupdate=func.now())
    deletedAt = Column(DateTime(fsp=6), nullable=True)
    idealVoiceUrl = Column(String(512), nullable=True)
    introVoiceUrl = Column(String(512), nullable=False)
    introText = Column(String(255), nullable=False)
    profileImageUrl = Column(String(512), nullable=False)
    status = Column(Enum(UserStatus), nullable=False, default=UserStatus.ACTIVE, server_default=UserStatus.ACTIVE.value)
    code = Column(String(10), nullable=False)
    vibeVector = Column(JSON, nullable=False)
    provider = Column(Enum(ProviderEnum), nullable=True)
    providerUserId = Column(String(64), nullable=True)
    age = Column(Integer, nullable=False, default=50, server_default="50")

    def __repr__(self) -> str:  # pragma: no cover - 디버깅 헬퍼
        return f"User(id={self.id}, nickname={self.nickname!r})"
