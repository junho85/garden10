import os
import unittest
from datetime import date

from app.database import get_db
from app.services.attendance_service import check_user_commit_and_save


class TestAttendanceService(unittest.IsolatedAsyncioTestCase):
    """출석 서비스 테스트"""

    async def test_check_user_attendance(self):
        """사용자 출석 체크 성공 테스트"""
        github_id = "junho85"
        check_date = date(2025, 3, 14)
        api_token = os.getenv("GITHUB_TOKEN")
        db = get_db()

        result = await check_user_commit_and_save(github_id, check_date, api_token, db)
        print(result)


if __name__ == "__main__":
    unittest.main()