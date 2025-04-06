from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.services.github_service import get_user_commits, get_user_commits_stats
from app.models.github_commit import GitHubCommit
from app.models.user import User
from datetime import datetime, timedelta, date
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
        secret_key = config.auth.get("secret_key")
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        user_id = payload.get("sub")
        
        if not user_id:
            return None
        
        # 데이터베이스에서 사용자 조회
        user = db.query(User).filter(User.id == user_id).first()
        return user
    except Exception as e:
        logger.error(f"사용자 인증 중 오류 발생: {str(e)}")
        return None


@router.get("/github-commits/{github_id}", response_model=dict)
async def read_user_commits(
    github_id: str, 
    skip: int = Query(0, ge=0), 
    limit: int = Query(10, ge=1, le=100),
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    특정 사용자의 GitHub 커밋 내역을 조회합니다.
    
    Args:
        github_id: GitHub 사용자 ID
        skip: 건너뛸 레코드 수 (페이지네이션)
        limit: 가져올 최대 레코드 수 (페이지네이션)
        from_date: 시작 날짜 (YYYY-MM-DD 형식)
        to_date: 종료 날짜 (YYYY-MM-DD 형식)
        db: 데이터베이스 세션
        current_user: 현재 로그인한 사용자
    
    Returns:
        Dict: 커밋 내역 및 페이지네이션 정보
    """
    try:
        # 날짜 파라미터 처리
        start_date = None
        end_date = None
        
        # 날짜 파라미터가 없는 경우 프로젝트 기간 사용
        if not from_date and not to_date and config.project:
            # 프로젝트 시작일 가져오기
            if "start_date" in config.project:
                try:
                    start_date = date.fromisoformat(config.project["start_date"])
                except ValueError:
                    logger.warning("프로젝트 시작일 형식이 잘못되었습니다.")
            
            # 프로젝트 종료일은 오늘로 설정 (또는 프로젝트 정의된 종료일)
            end_date = date.today()
        
        # 명시적으로 지정된 날짜 범위가 있는 경우
        if from_date:
            try:
                start_date = date.fromisoformat(from_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="시작 날짜 형식이 잘못되었습니다. YYYY-MM-DD 형식을 사용하세요.")
        
        if to_date:
            try:
                end_date = date.fromisoformat(to_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="종료 날짜 형식이 잘못되었습니다. YYYY-MM-DD 형식을 사용하세요.")
        
        # 총 커밋 수 조회 (페이지네이션용)
        stats = await get_user_commits_stats(
            db, 
            github_id,
            from_date=start_date,
            to_date=end_date
        )
        total_commits = stats["total_commits"]
        
        # 커밋 내역 조회
        db_commits = await get_user_commits(
            db, 
            github_id, 
            skip=skip, 
            limit=limit,
            from_date=start_date,
            to_date=end_date
        )

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
        
        # 페이지네이션 정보 추가
        result = {
            "commits": commits,
            "pagination": {
                "total": total_commits,
                "page": skip // limit + 1 if limit > 0 else 1,
                "pages": (total_commits + limit - 1) // limit if limit > 0 else 1,
                "limit": limit,
                "has_more": skip + limit < total_commits
            }
        }
        
        return result
    
    except Exception as e:
        logger.error(f"커밋 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail="커밋 내역을 조회하는 중 오류가 발생했습니다.")


@router.get("/github-commits/{github_id}/stats")
async def read_user_commits_stats(
    github_id: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    특정 사용자의 GitHub 커밋 통계 정보를 조회합니다.
    
    Args:
        github_id: GitHub 사용자 ID
        from_date: 시작 날짜 (YYYY-MM-DD 형식)
        to_date: 종료 날짜 (YYYY-MM-DD 형식)
        db: 데이터베이스 세션
        
    Returns:
        Dict: 커밋 통계 정보 (총 커밋 수, 저장소 수, 가장 최근 커밋 날짜)
    """
    try:
        # 날짜 파라미터 처리
        start_date = None
        end_date = None
        
        # 날짜 파라미터가 없는 경우 프로젝트 기간 사용
        if not from_date and not to_date and config.project:
            # 프로젝트 시작일 가져오기
            if "start_date" in config.project:
                try:
                    start_date = date.fromisoformat(config.project["start_date"])
                except ValueError:
                    logger.warning("프로젝트 시작일 형식이 잘못되었습니다.")
            
            # 프로젝트 종료일은 오늘로 설정 (또는 프로젝트 정의된 종료일)
            end_date = date.today()
        
        # 명시적으로 지정된 날짜 범위가 있는 경우
        if from_date:
            try:
                start_date = date.fromisoformat(from_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="시작 날짜 형식이 잘못되었습니다. YYYY-MM-DD 형식을 사용하세요.")
        
        if to_date:
            try:
                end_date = date.fromisoformat(to_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="종료 날짜 형식이 잘못되었습니다. YYYY-MM-DD 형식을 사용하세요.")
        
        # 통계 정보 조회
        stats = await get_user_commits_stats(
            db, 
            github_id,
            from_date=start_date,
            to_date=end_date
        )
        
        # 날짜 범위 정보 추가
        stats["from_date"] = start_date.isoformat() if start_date else None
        stats["to_date"] = end_date.isoformat() if end_date else None
        
        # 최근 커밋 날짜가 있는 경우 ISO 형식으로 변환
        if stats.get("latest_commit_date"):
            stats["latest_commit_date"] = stats["latest_commit_date"].isoformat()
            
            # 오늘과의 날짜 차이 계산
            latest_date = datetime.fromisoformat(stats["latest_commit_date"].split("T")[0])
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            days_diff = (today - latest_date).days
            
            stats["days_since_last_commit"] = days_diff
        else:
            stats["days_since_last_commit"] = None
            
        return stats
    
    except Exception as e:
        logger.error(f"커밋 통계 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail="커밋 통계를 조회하는 중 오류가 발생했습니다.")