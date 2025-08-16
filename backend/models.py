from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)


class Audio(Base):
    __tablename__ = "audios"
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(1024), nullable=False)
    mime = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Row(Base):
    __tablename__ = "rows"
    id = Column(Integer, primary_key=True)
    col1 = Column(String(255), nullable=False, default="")
    col2 = Column(String(255), nullable=False, default="")
    audio_id = Column(Integer, ForeignKey("audios.id"), nullable=True)
    audio = relationship("Audio", lazy="joined")