from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import httpx

from app.config import get_github_ids

router = APIRouter()


# Pydantic 모델 정의
class UserBase(BaseModel):
    github_id: str
    github_profile_url: str


class UserResponse(UserBase):
    github_id: str
    github_profile_url: str


# 모든 사용자 조회
@router.get("/users", response_model=List[UserResponse], tags=["users"])
async def get_users():
    """모든 사용자 목록을 반환합니다."""
    github_ids = get_github_ids()

    users = [
        {"github_id": github_id, "github_profile_url": f"https://avatars.githubusercontent.com/{github_id}"}
        for github_id in github_ids
    ]
    return users
