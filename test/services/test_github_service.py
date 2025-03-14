import json
from datetime import datetime
from unittest import TestCase, IsolatedAsyncioTestCase
from app.services.github_service import get_github_commits
import os


class Test(IsolatedAsyncioTestCase):
    async def test_get_github_commits(self):
        check_date = datetime.strptime("2025-03-13", "%Y-%m-%d").date()
        # 환경 변수나 테스트용 토큰 사용
        api_token = os.environ.get("GITHUB_API_TOKEN", "test_token")
        # github_id = "junho85"
        github_id = "kevinoriginal"
        result = await get_github_commits(github_id, check_date, api_token)
        print(json.dumps(result, indent=2))

        # Assert: Verify the result and mock call
        # self.assertEqual(len(result), 1)
        # self.assertEqual(result[0]["sha"], "8450bd720c642e7c1927db43fa050cccaca84768")
