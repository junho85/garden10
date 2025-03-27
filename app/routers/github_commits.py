from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.services.github_service import get_user_commits
from app.models.github_commit import GitHubCommit
from app.models.user import User
from datetime import datetime, timedelta
import logging
import jwt
from app.config import config

# 로깅 설정
logger = logging.getLogger(__name__)

router = APIRouter()


async def get_current_user(request: Request, db: Session = Depends(get_db)):
    """쿠키 또는 세션에서 현재 로그인한 사용자 정보를 가져옵니다."""
    try:
        # 쿠키에서 토큰 가져오기
        token = request.cookies.get("access_token")
        if not token:
            return None
        
        # JWT 토큰 디코딩
        jwt_secret = config.auth.get("jwt_secret", "")
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        github_id = payload.get("sub")
        
        if not github_id:
            return None
        
        # 데이터베이스에서 사용자 조회
        user = db.query(User).filter(User.github_id == github_id).first()
        return user
    except Exception as e:
        logger.error(f"사용자 인증 중 오류 발생: {str(e)}")
        return None


@router.get("/github-commits/{github_id}", response_model=List[dict])
async def read_user_commits(
    github_id: str, 
    skip: int = Query(0, ge=0), 
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    특정 사용자의 GitHub 커밋 내역을 조회합니다.
    
    Args:
        github_id: GitHub 사용자 ID
        skip: 건너뛸 레코드 수 (페이지네이션)
        limit: 가져올 최대 레코드 수 (페이지네이션)
        db: 데이터베이스 세션
        current_user: 현재 로그인한 사용자
    
    Returns:
        List[dict]: 커밋 내역 목록
    """
    try:
        db_commits = await get_user_commits(db, github_id, skip, limit)
        
        # 현재 로그인한 사용자가 조회 대상 사용자와 동일한지 확인
        is_same_user = current_user is not None and current_user.github_id == github_id
        
        # ORM 모델을 dict로 변환
        commits = []
        for commit in db_commits:
            # private 레포지토리의 커밋인 경우 처리
            message = commit.message
            if commit.is_private and not is_same_user:
                message = "[비공개 커밋]"  # 다른 사용자의 비공개 커밋 메시지는 숨김
            
            commits.append({
                "id": commit.id,
                "github_id": commit.github_id,
                "commit_id": commit.commit_id,
                "repository": commit.repository,
                "message": message,
                "commit_url": commit.commit_url,
                "commit_date": commit.commit_date,
                "is_private": commit.is_private,
                "created_at": commit.created_at,
                "updated_at": commit.updated_at
            })
        
        return commits
    
    except Exception as e:
        logger.error(f"커밋 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail="커밋 내역을 조회하는 중 오류가 발생했습니다.")