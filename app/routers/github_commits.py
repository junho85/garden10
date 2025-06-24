from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
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
            if hasattr(config.project, 'start_date'):
                try:
                    start_date = date.fromisoformat(config.project.start_date)
                except ValueError:
                    logger.warning("프로젝트 시작일 형식이 잘못되었습니다.")
            
            # 프로젝트 종료일 계산
            if start_date and hasattr(config.project, 'total_days'):
                try:
                    total_days = int(config.project.total_days)
                    project_end_date = start_date + timedelta(days=total_days - 1)
                    # 프로젝트가 종료되었으면 프로젝트 종료일, 아니면 오늘 날짜 사용
                    end_date = min(date.today(), project_end_date)
                except ValueError:
                    logger.warning("프로젝트 총 일수 형식이 잘못되었습니다.")
                    end_date = date.today()
            else:
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
            if hasattr(config.project, 'start_date'):
                try:
                    start_date = date.fromisoformat(config.project.start_date)
                except ValueError:
                    logger.warning("프로젝트 시작일 형식이 잘못되었습니다.")
            
            # 프로젝트 종료일 계산
            if start_date and hasattr(config.project, 'total_days'):
                try:
                    total_days = int(config.project.total_days)
                    project_end_date = start_date + timedelta(days=total_days - 1)
                    # 프로젝트가 종료되었으면 프로젝트 종료일, 아니면 오늘 날짜 사용
                    end_date = min(date.today(), project_end_date)
                except ValueError:
                    logger.warning("프로젝트 총 일수 형식이 잘못되었습니다.")
                    end_date = date.today()
            else:
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


@router.get("/github-commits/{github_id}/daily-counts")
async def read_user_daily_commits(
    github_id: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    특정 사용자의 일별 GitHub 커밋 수를 조회합니다.
    
    Args:
        github_id: GitHub 사용자 ID
        from_date: 시작 날짜 (YYYY-MM-DD 형식)
        to_date: 종료 날짜 (YYYY-MM-DD 형식)
        db: 데이터베이스 세션
        
    Returns:
        Dict: 날짜별 커밋 수 정보
    """
    try:
        # 날짜 파라미터 처리
        start_date = None
        end_date = None
        
        # 날짜 파라미터가 없는 경우 프로젝트 기간 또는 최근 1년 사용
        if not from_date and not to_date:
            # 기본값: 최근 1년 (약 365일)
            end_date = date.today()
            start_date = end_date - timedelta(days=365)
            
            # 프로젝트 설정 확인
            if config.project:
                # 프로젝트 시작일 확인
                project_start = None
                if hasattr(config.project, 'start_date'):
                    try:
                        project_start = date.fromisoformat(config.project.start_date)
                        start_date = project_start  # 프로젝트 시작일 사용
                    except ValueError:
                        logger.warning("프로젝트 시작일 형식이 잘못되었습니다.")
                
                # 총 일수(total_days)를 이용하여 종료일 계산
                if project_start and hasattr(config.project, 'total_days'):
                    try:
                        total_days = int(config.project.total_days)
                        # 시작일 + 총 일수 - 1 = 종료일
                        project_end_date = project_start + timedelta(days=total_days - 1)
                        # 프로젝트가 종료되었으면 프로젝트 종료일 사용
                        end_date = min(date.today(), project_end_date)
                    except (ValueError, TypeError):
                        logger.warning("프로젝트 총 일수(total_days) 형식이 잘못되었습니다.")
                        
                # total_days 없이 직접 종료일이 설정된 경우
                elif hasattr(config.project, 'end_date'):
                    try:
                        project_end = date.fromisoformat(config.project.end_date)
                        end_date = project_end
                    except ValueError:
                        logger.warning("프로젝트 종료일 형식이 잘못되었습니다.")
        
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
                
        # 날짜 범위 체크
        if start_date and end_date and start_date > end_date:
            raise HTTPException(status_code=400, detail="시작 날짜가 종료 날짜보다 늦습니다.")
            
        # 일별 커밋 수 쿼리 생성
        query = db.query(
            func.date(func.timezone('Asia/Seoul', GitHubCommit.commit_date)).label('commit_date'),
            func.count().label('count')
        ).filter(
            GitHubCommit.github_id == github_id
        ).group_by(
            func.date(func.timezone('Asia/Seoul', GitHubCommit.commit_date))
        ).order_by(
            func.date(func.timezone('Asia/Seoul', GitHubCommit.commit_date))
        )
        
        # 시간 보정 (KST 기준)
        kst_offset = timedelta(hours=9)  # UTC+9
        
        # 날짜 필터 적용
        if start_date:
            start_datetime = datetime.combine(start_date, datetime.min.time()) - kst_offset
            query = query.filter(GitHubCommit.commit_date >= start_datetime)
            
        if end_date:
            end_datetime = datetime.combine(end_date, datetime.max.time()) - kst_offset
            query = query.filter(GitHubCommit.commit_date <= end_datetime)
            
        # 쿼리 실행
        results = query.all()
        
        # 결과를 딕셔너리로 변환
        daily_commits = {}
        
        # 날짜 범위 내의 모든 날짜에 대해 빈 데이터 생성 (비어있는 날짜도 0으로 표시)
        if start_date and end_date:
            current_date = start_date
            while current_date <= end_date:
                daily_commits[current_date.isoformat()] = 0
                current_date += timedelta(days=1)
        
        # 실제 데이터 채우기
        for result in results:
            date_str = result.commit_date.isoformat()
            daily_commits[date_str] = result.count
            
        return {
            "github_id": github_id,
            "from_date": start_date.isoformat() if start_date else None,
            "to_date": end_date.isoformat() if end_date else None,
            "daily_commits": daily_commits
        }
        
    except Exception as e:
        logger.error(f"일별 커밋 수 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail="일별 커밋 수를 조회하는 중 오류가 발생했습니다.")