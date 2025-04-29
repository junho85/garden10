from datetime import datetime, date, timedelta
from typing import Tuple, Optional

# KST 오프셋 상수
KST_OFFSET = timedelta(hours=9)  # UTC+9

def get_kst_datetime_range(target_date: date) -> Tuple[datetime, datetime]:
    """
    특정 날짜의 KST 기준 시작 시간과 종료 시간을 반환합니다.
    
    Args:
        target_date: 대상 날짜
        
    Returns:
        Tuple[datetime, datetime]: (시작 시간, 종료 시간) 튜플
    """
    start_datetime = datetime.combine(target_date, datetime.min.time()) - KST_OFFSET
    end_datetime = datetime.combine(target_date, datetime.max.time()) - KST_OFFSET
    
    return start_datetime, end_datetime