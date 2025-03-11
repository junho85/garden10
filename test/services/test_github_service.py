from datetime import datetime
from unittest import TestCase, IsolatedAsyncioTestCase
from app.services.github_service import get_github_commits


class Test(IsolatedAsyncioTestCase):
    async def test_get_github_commits(self):
        check_date = datetime.strptime("2025-03-10", "%Y-%m-%d").date()
        result = await get_github_commits("junho85", check_date)
        print(result)

        # Assert: Verify the result and mock call
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["sha"], "8450bd720c642e7c1927db43fa050cccaca84768")
