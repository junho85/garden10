import httpx
from datetime import datetime, date, timedelta

from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app.models.user import User
from app.models.attendance import Attendance
from app.services.github_service import get_github_commits, fetch_and_save_commits
from app.config import config
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_user_commit_and_save(
        github_id: str,
        check_date: date,
        github_api_token: str,
        db: Session
) -> Dict[str, Any]:
    """
    특정 사용자의 특정 날짜 출석을 확인하고 DB에 저장합니다.
    
    Args:
        github_id: GitHub 사용자 ID
        check_date: 확인할 날짜
        github_api_token: GitHub API 토큰
        db: 데이터베이스 세션
        
    Returns:
        Dict: 처리 결과
    """
    # 사용자 확인
    user = db.query(User).filter(User.github_id == github_id).first()
    if not user:
        logger.warning(f"사용자를 찾을 수 없음: {github_id}")
        return {"status": "error", "message": f"사용자를 찾을 수 없음: {github_id}"}

    try:
        # GitHub 커밋 조회 및 저장
        fetch_result = await fetch_and_save_commits(db, github_id, check_date, github_api_token)
        commit_count = fetch_result["total_commits"]

        # 출석 기록 조회 또는 생성
        attendance = db.query(Attendance).filter(
            Attendance.github_id == user.github_id,
            Attendance.attendance_date == check_date
        ).first()

        if not attendance:
            # 신규 출석 기록 생성
            attendance = Attendance(
                github_id=str(user.github_id),
                attendance_date=check_date,
                commit_count=commit_count,
                is_attended=commit_count > 0
            )
            db.add(attendance)
        else:
            # 기존 출석 기록 업데이트
            attendance.commit_count = commit_count
            attendance.is_attended = commit_count > 0
            attendance.updated_at = datetime.now()

        db.commit()

        return {
            "status": "success",
            "date": check_date.isoformat(),
            "github_id": github_id,
            "commit_count": commit_count,
            "is_attended": commit_count > 0,
            "commits_saved": fetch_result["saved_commits"]
        }

    except Exception as e:
        logger.error(f"출석 확인 중 오류 발생: {e}", exc_info=True)
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
    user = db.query(User).filter(User.github_id == github_id).first()
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
        user = db.query(User).filter(User.github_id == attendance.github_id).first()
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
