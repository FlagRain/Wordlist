import os
from datetime import datetime, timedelta
from jose import jwt
from passlib.hash import bcrypt
from sqlalchemy.orm import Session
from models import User

SECRET = os.getenv("SECRET", "dev-secret")
ALGO = "HS256"
EXPIRE_MIN = int(os.getenv("TOKEN_EXPIRE_MIN", "1440"))


def create_default_admin(db: Session):
    username = os.getenv("ADMIN_USERNAME", "admin")
    pwd = os.getenv("ADMIN_PASSWORD", "admin")
    u = db.query(User).filter_by(username=username).first()
    if not u:
        db.add(User(username=username, password_hash=bcrypt.hash(pwd)))
        db.commit()


def authenticate(db: Session, username: str, password: str):
    u = db.query(User).filter_by(username=username).first()
    if not u or not bcrypt.verify(password, u.password_hash):
        return None
    payload = {"sub": u.username, "exp": datetime.utcnow() + timedelta(minutes=EXPIRE_MIN)}
    return jwt.encode(payload, SECRET, algorithm=ALGO)


def verify_token(token: str):
    return jwt.decode(token, SECRET, algorithms=[ALGO])