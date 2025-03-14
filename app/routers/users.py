from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import httpx

from app.database import get_db
from app.models.user import User

router = APIRouter()


# Pydantic 모델 정의
class UserBase(BaseModel):
    id: int
    github_id: str


class UserResponse(UserBase):
    github_profile_url: Optional[str] = None


# 모든 사용자 조회
@router.get("/users", response_model=List[UserResponse], tags=["users"])
async def get_users(db: Session = Depends(get_db)):
    """모든 사용자 목록을 데이터베이스에서 가져옵니다."""
    users = db.query(User).all()

    for user in users:
        user.github_profile_url = f"https://avatars.githubusercontent.com/{user.github_id}"

    return users
