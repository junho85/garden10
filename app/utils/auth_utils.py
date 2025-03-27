from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends, Request, Cookie
from sqlalchemy.orm import Session

from app.config import config
from app.database import get_db
from app.models.user import User

# JWT 토큰 설정
SECRET_KEY = config.auth.get("secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = config.auth.get("token_expire_minutes", 1440)
TOKEN_COOKIE_NAME = "access_token"

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """JWT 액세스 토큰 생성"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    """JWT 토큰 검증"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증에 실패했습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise credentials_exception
        
        return {"user_id": user_id}
    except JWTError:
        raise credentials_exception

async def get_current_user(
    access_token: str = Cookie(None, alias=TOKEN_COOKIE_NAME),
    db: Session = Depends(get_db)
):
    """쿠키에서 토큰을 읽어 현재 인증된 사용자 가져오기"""
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = verify_token(access_token)
    user = db.query(User).filter(User.id == token_data["user_id"]).first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    
    return user