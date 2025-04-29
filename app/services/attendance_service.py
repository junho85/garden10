import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from app.config import config
from app.models.attendance import Attendance
from app.models.github_commit import GitHubCommit
from app.models.user import User
from app.services.github_service import fetch_and_save_commits, apply_date_filters
from app.utils.date_utils import get_kst_datetime_range

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_user_commit_and_save(
        github_id: str,
        check_date: date,
        github_api_token: str,
        db: Session
) -> Dict[str, Any]:
    """
    특정 사용자의 특정 날짜 출석을 확인하고 DB에 저장합니다.
    GitHub API를 호출하여 커밋을 가져오고, 이를 DB에 저장한 후 출석 여부를 결정합니다.
    
    Args:
        github_id: GitHub 사용자 ID
        check_date: 확인할 날짜
        github_api_token: GitHub API 토큰
        db: 데이터베이스 세션
        
    Returns:
        Dict: 처리 결과
    """
    # 사용자 확인
    user = get_user_by_github_id(db, github_id)
    if not user:
        logger.warning(f"사용자를 찾을 수 없음: {github_id}")
        return {"status": "error", "message": f"사용자를 찾을 수 없음: {github_id}"}

    try:
        # GitHub API로 커밋을 가져와서 DB에 저장
        fetch_result = await fetch_and_save_commits(db, github_id, check_date, github_api_token)
        
        # DB에 저장된 커밋을 기반으로 출석 정보 생성
        return await create_attendance_from_db_commits(github_id, check_date, db)

    except Exception as e:
        logger.error(f"출석 확인 중 오류 발생: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}


def get_user_by_github_id(db: Session, github_id: str) -> Optional[User]:
    """
    GitHub ID로 사용자를 조회합니다.
    
    Args:
        db: 데이터베이스 세션
        github_id: GitHub 사용자 ID
        
    Returns:
        Optional[User]: 사용자 객체 또는 None
    """
    return db.query(User).filter(User.github_id == github_id).first()

async def create_attendance_from_db_commits(
        github_id: str,
        check_date: date,
        db: Session
) -> Dict[str, Any]:
    """
    DB에 저장된 GitHub 커밋 내역을 바탕으로 특정 사용자의 출석 정보를 생성합니다.
    
    Args:
        github_id: GitHub 사용자 ID
        check_date: 확인할 날짜
        db: 데이터베이스 세션
        
    Returns:
        Dict: 처리 결과
    """
    try:
        # 사용자 확인
        user = get_user_by_github_id(db, github_id)
        if not user:
            logger.warning(f"사용자를 찾을 수 없음: {github_id}")
            return {"status": "error", "message": f"사용자를 찾을 수 없음: {github_id}"}
        
        # 해당 날짜에 사용자의 커밋 수 조회
        query = db.query(GitHubCommit).filter(GitHubCommit.github_id == github_id)
        query = apply_date_filters(query, check_date, check_date)
        commits = query.all()
        
        commit_count = len(commits)
        is_attended = commit_count > 0
        
        # 출석 기록 조회 또는 생성
        attendance = db.query(Attendance).filter(
            Attendance.github_id == github_id,
            Attendance.attendance_date == check_date
        ).first()

        if not attendance:
            # 신규 출석 기록 생성
            attendance = Attendance(
                github_id=github_id,
                attendance_date=check_date,
                commit_count=commit_count,
                is_attended=is_attended
            )
            db.add(attendance)
        else:
            # 기존 출석 기록 업데이트
            attendance.commit_count = commit_count
            attendance.is_attended = is_attended
            attendance.updated_at = datetime.now()

        db.commit()

        return {
            "status": "success",
            "date": check_date.isoformat(),
            "github_id": github_id,
            "commit_count": commit_count,
            "is_attended": is_attended
        }
        
    except Exception as e:
        logger.error(f"DB 커밋 기반 출석 확인 중 오류 발생: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}


async def check_all_attendances(
        check_date: Optional[date] = None,
        db: Session = None
) -> Dict[str, Any]:
    """
    모든 사용자의 특정 날짜 출석을 확인하고 DB에 저장합니다.
    
    Args:
        check_date: 확인할 날짜 (None이면 오늘)
        db: 데이터베이스 세션
        
    Returns:
        Dict: 처리 결과
    """
    if check_date is None:
        check_date = date.today()

    # 공통 GitHub API 토큰 
    common_github_api_token = config.github.get("api_token", "")
    if not common_github_api_token:
        return {"status": "error", "message": "GitHub API 토큰이 설정되지 않았습니다."}

    results = []
    users = db.query(User).all()

    for user in users:
        # 사용자별 토큰이 있으면 그것을 사용
        github_api_token = user.github_api_token or common_github_api_token

        # 사용자 출석 확인
        result = await check_user_commit_and_save(
            github_id=str(user.github_id),
            check_date=check_date,
            github_api_token=github_api_token,
            db=db
        )

        results.append(result)

    return {
        "status": "success",
        "date": check_date.isoformat(),
        "results": results
    }


async def get_user_attendance_history(
        github_id: str,
        start_date: date,
        end_date: date,
        db: Session
) -> List[Dict[str, Any]]:
    """
    특정 사용자의 출석 기록을 조회합니다.
    
    Args:
        github_id: GitHub 사용자 ID
        start_date: 시작 날짜
        end_date: 종료 날짜
        db: 데이터베이스 세션
        
    Returns:
        List[Dict]: 출석 기록 목록
    """
    user = get_user_by_github_id(db, github_id)
    if not user:
        return []

    attendances = db.query(Attendance).filter(
        Attendance.github_id == user.github_id,
        Attendance.attendance_date >= start_date,
        Attendance.attendance_date <= end_date
    ).order_by(Attendance.attendance_date.desc()).all()

    results = []
    for attendance in attendances:
        results.append({
            "attendance_date": attendance.attendance_date.isoformat(),
            "commit_count": attendance.commit_count,
            "is_attended": attendance.is_attended,
        })

    return results


async def create_attendance_from_commits(db: Session, check_date: Optional[date] = None) -> Dict[str, Any]:
    """
    DB에 저장된 GitHub 커밋 내역을 기반으로 모든 사용자의 출석 기록을 생성합니다.
    
    Args:
        db: 데이터베이스 세션
        check_date: 확인할 날짜 (None이면 오늘)
        
    Returns:
        Dict: 처리 결과
    """
    if check_date is None:
        check_date = date.today()
    
    # 모든 사용자 가져오기
    users = db.query(User).all()
    results = []
    
    for user in users:
        github_id = user.github_id
        
        # DB에 저장된 커밋을 기반으로 출석 정보 생성
        result = await create_attendance_from_db_commits(github_id, check_date, db)
        results.append(result)
    
    return {
        "status": "success",
        "date": check_date.isoformat(),
        "results": results
    }

async def get_daily_attendance_stats(check_date: date, db: Session) -> Dict[str, Any]:
    """
    특정 날짜의 출석 통계를 조회합니다.
    
    Args:
        check_date: 조회할 날짜
        db: 데이터베이스 세션
        
    Returns:
        Dict: 출석 통계
    """
    # 전체 사용자 수
    total_users = db.query(User).count()

    # 출석한 사용자 수
    present_count = db.query(Attendance).filter(
        Attendance.attendance_date == check_date,
        Attendance.is_attended == True
    ).count()

    # 출석률
    attendance_rate = (present_count / total_users * 100) if total_users > 0 else 0

    # 출석한 사용자 정보
    attendances = db.query(Attendance).filter(
        Attendance.attendance_date == check_date,
        Attendance.is_attended == True
    ).all()

    present_users = []
    for attendance in attendances:
        user = get_user_by_github_id(db, attendance.github_id)
        if user:
            present_users.append({
                "github_id": user.github_id,
                "commit_count": attendance.commit_count,
            })

    return {
        "date": check_date.isoformat(),
        "total_users": total_users,
        "present_count": present_count,
        "attendance_rate": attendance_rate,
        "present_users": present_users
    }
