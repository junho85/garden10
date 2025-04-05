import asyncio
import logging
from datetime import date, datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from app.database import SessionLocal
from app.services.attendance_service import check_all_attendances, create_attendance_from_commits

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 스케줄러 초기화
scheduler = AsyncIOScheduler()

async def run_attendance_check():
    """
    출석 체크를 실행합니다.
    1시간마다 실행되도록 설정됩니다.
    """
    logger.info(f"출석 체크 시작: {datetime.now()}")
    
    try:
        # 데이터베이스 세션 생성
        db = SessionLocal()
        
        # 오늘과 어제 날짜 계산
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        dates_to_check = [yesterday, today]
        
        for check_date in dates_to_check:
            logger.info(f"날짜 {check_date.isoformat()} 출석 체크 중...")
            
            # 기존 방식 출석 체크 (GitHub API 호출)
            api_result = await check_all_attendances(check_date, db)
            logger.info(f"{check_date.isoformat()} API 출석 체크 결과: {api_result['status']}")
            
            # 커밋 내역 기반 출석 체크 (DB에 저장된 커밋 사용)
            commit_result = await create_attendance_from_commits(db, check_date)
            logger.info(f"{check_date.isoformat()} 커밋 기반 출석 체크 결과: {commit_result['status']}")
        
        logger.info("모든 날짜 출석 체크 완료")
        
    except Exception as e:
        logger.error(f"출석 체크 중 오류 발생: {e}", exc_info=True)
    finally:
        db.close()

def init_scheduler(run_scheduler=False):
    """
    스케줄러를 초기화하고 작업을 등록합니다.
    
    Args:
        run_scheduler: 스케줄러를 실행할지 여부. 기본값은 False
    
    Returns:
        AsyncIOScheduler: 초기화된 스케줄러 객체
    """
    if not run_scheduler:
        # 비활성화 메시지는 lifespan에서 이미 출력하므로 여기서는 생략
        return scheduler
    
    # 1시간마다 출석 체크 수행
    scheduler.add_job(
        run_attendance_check,
        IntervalTrigger(hours=1),
        id="hourly_attendance_check",
        replace_existing=True
    )
    
    # 매일 자정(UTC 0시)에도 출석 체크 수행 (중요한 시점)
    scheduler.add_job(
        run_attendance_check,
        CronTrigger(hour=0, minute=0, second=0),
        id="daily_attendance_check",
        replace_existing=True
    )
    
    # 스케줄러 시작 시 한 번 출석 체크 수행
    scheduler.add_job(
        run_attendance_check,
        id="initial_attendance_check",
        replace_existing=True
    )
    
    logger.info("스케줄러 초기화 완료 - 1시간 간격으로 출석 체크가 실행됩니다.")
    
    # 스케줄러 시작
    scheduler.start()
    
    return scheduler