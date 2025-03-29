from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
from app.database import get_db
from app.models.user import User
from app.models.attendance import Attendance
from app.services.attendance_service import (
    check_all_attendances,
    check_user_commit_and_save,
    get_user_attendance_history,
    get_daily_attendance_stats
)
from app.config import config
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["attendance"])


@router.post("/attendance/check")
async def check_attendance_api(check_date: Optional[str] = None, db: Session = Depends(get_db)):
    """모든 사용자의 출석 체크를 실행합니다."""
    date_to_check = None
    if check_date:
        try:
            date_to_check = date.fromisoformat(check_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    result = await check_all_attendances(date_to_check, db)
    return result


@router.post("/attendance/check/{github_id}")
async def check_user_attendance_api(
        github_id: str,
        check_date: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """특정 사용자의 출석 체크를 실행합니다."""
    date_to_check = None
    if check_date:
        try:
            date_to_check = date.fromisoformat(check_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        date_to_check = date.today()

    # 사용자 확인
    user = db.query(User).filter(User.github_id == github_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with github_id {github_id} not found")

    # 사용자별 토큰이 있으면 사용, 없으면 공통 토큰 사용
    api_token = user.github_api_token or config.github.get("api_token", "")
    if not api_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub API token not configured"
        )

    result = await check_user_commit_and_save(github_id, date_to_check, api_token, db)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return result


@router.get("/attendance/history/{github_id}")
async def get_attendance_history(
        github_id: str,
        start_date: str,
        end_date: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """특정 사용자의 출석 기록을 조회합니다."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date) if end_date else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    user = db.query(User).filter(User.github_id == github_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with github_id {github_id} not found")

    history = await get_user_attendance_history(github_id, start, end, db)
    return history


@router.get("/attendance/stats")
async def get_attendance_stats(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """출석 통계를 조회합니다."""
    print("get_attendance_stats")
    print("start_date", start_date)
    print("end_date", end_date)

    # 시작일과 종료일 설정
    if start_date:
        try:
            start = date.fromisoformat(start_date)
        except ValueError as e:
            logger.error(f"Invalid start_date format: {e}")
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")
    else:
        # 기본 시작일 (프로젝트 설정값 사용)
        try:
            project_config = config.project
            if project_config and "start_date" in project_config:
                start = date.fromisoformat(project_config["start_date"])
            else:
                logger.warning("Project start_date not configured, using default")
                start = date(2025, 3, 10)  # 기본값
        except (ValueError, KeyError) as e:
            logger.error(f"Error parsing project start_date: {e}")
            start = date(2025, 3, 10)  # 기본값

    if end_date:
        try:
            end = date.fromisoformat(end_date)
        except ValueError as e:
            logger.error(f"Invalid end_date format: {e}")
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")
    else:
        end = date.today()

    # 날짜 범위 생성
    days_completed = (end - start).days + 1
    
    # 총 프로젝트 일수 설정
    total_project_days = 100  # 기본값
    try:
        project_config = config.project
        if project_config and "total_days" in project_config:
            total_project_days = int(project_config["total_days"])
    except (ValueError, KeyError) as e:
        logger.error(f"Error parsing project total_days: {e}")
    
    date_list = [(start + timedelta(days=i)).isoformat() for i in range(days_completed)]

    # 사용자별 출석 데이터 조회
    users = db.query(User).all()
    user_stats = []

    for user in users:
        attendances = db.query(Attendance).filter(
            Attendance.github_id == user.github_id,
            Attendance.attendance_date >= start,
            Attendance.attendance_date <= end
        ).all()

        # 출석 여부 맵 생성
        attendance_map = {att.attendance_date.isoformat(): att.is_attended for att in attendances}

        # 날짜별 출석 여부 리스트
        attendance_list = [attendance_map.get(d, False) for d in date_list]

        # 출석률 계산
        attended_count = sum(1 for a in attendance_list if a)
        attendance_rate = round(attended_count / len(date_list) * 100) if date_list else 0

        user_stats.append({
            "github_id": user.github_id,
            "attendance_rate": attendance_rate,
            "attended_count": attended_count,
            "total_days": len(date_list),
            "attendance": attendance_list
        })

    # 출석률 기준으로 정렬하고 순위 부여
    user_stats.sort(key=lambda x: x["attendance_rate"], reverse=True)
    for i, user in enumerate(user_stats):
        user["rank"] = i + 1

    # 날짜별 출석률 계산
    daily_rates = []
    for i, d in enumerate(date_list):
        attended_count = sum(1 for user in user_stats if user["attendance"][i])
        daily_rate = round(attended_count / len(users) * 100) if users else 0
        daily_rates.append({
            "date": d,
            "rate": daily_rate
        })

    # 총 출석/미출석 수 계산
    total_present = sum(user["attended_count"] for user in user_stats)
    total_possible = len(users) * len(date_list)
    total_absent = total_possible - total_present
    overall_attendance_rate = round(total_present / total_possible * 100) if total_possible else 0

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days_completed": days_completed,
        "total_days": total_project_days,  # 총 프로젝트 일수
        "dates": date_list,
        "users": user_stats,
        "daily_rates": daily_rates,
        "total_present": total_present,
        "total_absent": total_absent,
        "overall_attendance_rate": overall_attendance_rate
    }


@router.get("/attendance/stats/{date_str}")
async def get_attendance_stats_for_date(date_str: str, db: Session = Depends(get_db)):
    """특정 날짜의 출석 통계를 조회합니다."""
    print("get_attendance_stats_for_date")
    try:
        check_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    stats = await get_daily_attendance_stats(check_date, db)
    return stats


@router.get("/attendance/ranking")
async def get_attendance_ranking(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """출석률 순위를 조회합니다."""
    print("start_date", start_date)
    print("end_date", end_date)

    stats = await get_attendance_stats(start_date, end_date, db)
    return stats["users"]


@router.get("/attendance/{date_str}")
async def get_attendance(date_str: str, db: Session = Depends(get_db)):
    """특정 날짜의 출석 현황을 조회합니다."""
    try:
        check_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    attendance_data = db.query(
        Attendance.github_id,
        Attendance.attendance_date,
        Attendance.is_attended,
    ).filter(
        Attendance.attendance_date == check_date
    ).all()

    result = [
        {
            "github_id": github_id,
            "attendance_date": attendance_date,
            "is_attended": is_attended,
        }
        for github_id, attendance_date, is_attended in attendance_data
    ]

    return result
