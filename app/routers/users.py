from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import httpx

from app.database import get_db
from app.models.user import User
from app.config import config

router = APIRouter()


# 관리자 인증 함수
async def verify_admin_api_key(x_api_key: str = Header(...)):
    admin_config = config.admin
    if not admin_config or x_api_key != admin_config.get("api_key"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다."
        )
    return True


# Pydantic 모델 정의
class UserBase(BaseModel):
    github_id: str


class UserCreate(UserBase):
    github_api_token: Optional[str] = None


class UserUpdate(BaseModel):
    github_api_token: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    github_id: str
    github_profile_url: Optional[str] = None


# 모든 사용자 조회
@router.get("/users", response_model=List[UserResponse], tags=["users"])
async def get_users(db: Session = Depends(get_db)):
    """모든 사용자 목록을 데이터베이스에서 가져옵니다."""
    users = db.query(User).all()

    for user in users:
        user.github_profile_url = f"https://avatars.githubusercontent.com/{user.github_id}"

    return users


# 사용자 조회
@router.get("/users/{user_id}", response_model=UserResponse, tags=["users"])
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """특정 ID의 사용자를 조회합니다."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    
    user.github_profile_url = f"https://avatars.githubusercontent.com/{user.github_id}"
    return user


# 사용자 추가 (관리자 권한 필요)
@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["users"])
async def create_user(
    user: UserCreate, 
    db: Session = Depends(get_db),
    is_admin: bool = Depends(verify_admin_api_key)
):
    """새로운 사용자를 추가합니다. 관리자 권한이 필요합니다."""
    # 이미 존재하는 github_id 확인
    db_user = db.query(User).filter(User.github_id == user.github_id).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 등록된 github_id입니다."
        )
    
    # 새 사용자 생성
    new_user = User(
        github_id=user.github_id,
        github_api_token=user.github_api_token
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 응답 데이터 생성
    new_user.github_profile_url = f"https://avatars.githubusercontent.com/{new_user.github_id}"
    
    return new_user


# 사용자 정보 업데이트 (관리자 권한 필요)
@router.put("/users/{user_id}", response_model=UserResponse, tags=["users"])
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    is_admin: bool = Depends(verify_admin_api_key)
):
    """사용자 정보를 업데이트합니다. 관리자 권한이 필요합니다."""
    # 사용자 존재 확인
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    
    # 업데이트할 필드 설정
    if user_update.github_api_token is not None:
        db_user.github_api_token = user_update.github_api_token
    
    # 변경 내용 저장
    db.commit()
    db.refresh(db_user)
    
    # 응답 데이터 생성
    db_user.github_profile_url = f"https://avatars.githubusercontent.com/{db_user.github_id}"
    
    return db_user
