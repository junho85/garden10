from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Cookie
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Optional
import httpx
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.utils.auth_utils import create_access_token, get_current_user, TOKEN_COOKIE_NAME
from app.config import config

router = APIRouter()

# GitHub OAuth 설정
GITHUB_CLIENT_ID = config.github.get("oauth", {}).get("client_id")
GITHUB_CLIENT_SECRET = config.github.get("oauth", {}).get("client_secret")
GITHUB_REDIRECT_URI = config.github.get("oauth", {}).get("redirect_uri")

# GitHub Auth URL
GITHUB_AUTH_URL = f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&redirect_uri={GITHUB_REDIRECT_URI}&scope=user:email"

# 응답 모델
class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    github_id: str

class UserInfo(BaseModel):
    id: int
    github_id: str
    github_profile_url: Optional[str] = None

# GitHub 로그인 페이지로 리다이렉트
@router.get("/auth/login", tags=["auth"])
async def login():
    """GitHub OAuth 로그인 페이지로 리다이렉트"""
    return RedirectResponse(url=GITHUB_AUTH_URL)

# GitHub OAuth 콜백 처리
@router.get("/auth/callback", tags=["auth"])
async def auth_callback(code: str, db: Session = Depends(get_db)):
    """GitHub OAuth 콜백 처리 및 JWT 토큰 발급"""
    # GitHub 액세스 토큰 요청
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_REDIRECT_URI,
            },
            headers={"Accept": "application/json"}
        )
        
        if token_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="GitHub 인증에 실패했습니다."
            )
        
        token_data = token_response.json()
        github_token = token_data.get("access_token")
        
        if not github_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="GitHub 토큰을 가져오지 못했습니다."
            )
        
        # GitHub 사용자 정보 요청
        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/json"
            }
        )
        
        if user_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="GitHub 사용자 정보를 가져오지 못했습니다."
            )
        
        github_user = user_response.json()
        github_id = github_user.get("login")
        
        # 사용자 DB 조회 또는 생성
        user = db.query(User).filter(User.github_id == github_id).first()
        
        if not user:
            # 신규 사용자 등록
            user = User(
                github_id=github_id,
                github_api_token=github_token
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            # 기존 사용자 토큰 업데이트
            user.github_api_token = github_token
            db.commit()
            db.refresh(user)
        
        # JWT 토큰 생성
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(minutes=config.auth.get("token_expire_minutes", 1440))
        )
        
        # 프론트엔드 페이지로 리다이렉트 (토큰을 쿠키에 저장)
        response = RedirectResponse(url="/")
        response.set_cookie(
            key=TOKEN_COOKIE_NAME,
            value=access_token,
            httponly=True,
            max_age=config.auth.get("token_expire_minutes", 1440) * 60,
            samesite="lax"
        )
        
        return response

# 토큰 검증 및 사용자 정보 반환
@router.get("/auth/me", response_model=UserInfo, tags=["auth"])
async def get_user_info(current_user: User = Depends(get_current_user)):
    """현재 로그인한 사용자 정보 반환"""
    return {
        "id": current_user.id,
        "github_id": current_user.github_id,
        "github_profile_url": f"https://avatars.githubusercontent.com/{current_user.github_id}"
    }

# 로그아웃
@router.get("/auth/logout", tags=["auth"])
async def logout():
    """로그아웃 (토큰 쿠키 삭제)"""
    response = RedirectResponse(url="/")
    response.delete_cookie(key=TOKEN_COOKIE_NAME)
    return response