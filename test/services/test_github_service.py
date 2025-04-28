import json
import os
from datetime import datetime, date
from unittest import TestCase, IsolatedAsyncioTestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.github_commit import GitHubCommit
from app.models.user import Base
from app.services.github_service import get_github_commits, apply_date_filters


class Test(IsolatedAsyncioTestCase):
    async def test_get_github_commits(self):
        check_date = datetime.strptime("2025-03-14", "%Y-%m-%d").date()

        api_token = os.environ.get("GITHUB_API_TOKEN")
        github_id = "junho85"
        # github_id = "kevinoriginal"
        result = await get_github_commits(github_id, check_date, api_token)
        print(json.dumps(result, indent=2))

        # Assert: Verify the result and mock call
        # self.assertEqual(len(result), 1)
        # self.assertEqual(result[0]["sha"], "8450bd720c642e7c1927db43fa050cccaca84768")


class TestDateFilterFunction(TestCase):
    def setUp(self):
        # Create an in-memory SQLite database for testing
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()
        
        # Insert sample data
        self.insert_sample_data()
        
    def tearDown(self):
        self.db.close()
        
    def insert_sample_data(self):
        # Create test commits with specific dates for predictable test results
        # Creating 5 commits on March 2-6, 2023
        commits = [
            GitHubCommit(
                github_id="testuser",
                commit_id="commit1",
                repository="repo1",
                message="Test commit 1",
                commit_url="https://github.com/test/commit1",
                commit_date=datetime(2023, 3, 2, 12, 0, 0),  # March 2
                is_private=False
            ),
            GitHubCommit(
                github_id="testuser",
                commit_id="commit2",
                repository="repo2",
                message="Test commit 2",
                commit_url="https://github.com/test/commit2",
                commit_date=datetime(2023, 3, 3, 12, 0, 0),  # March 3
                is_private=False
            ),
            GitHubCommit(
                github_id="testuser",
                commit_id="commit3",
                repository="repo3",
                message="Test commit 3",
                commit_url="https://github.com/test/commit3",
                commit_date=datetime(2023, 3, 4, 12, 0, 0),  # March 4
                is_private=False
            ),
            GitHubCommit(
                github_id="testuser",
                commit_id="commit4",
                repository="repo1",
                message="Test commit 4",
                commit_url="https://github.com/test/commit4",
                commit_date=datetime(2023, 3, 5, 12, 0, 0),  # March 5
                is_private=False
            ),
            GitHubCommit(
                github_id="testuser",
                commit_id="commit5",
                repository="repo2",
                message="Test commit 5",
                commit_url="https://github.com/test/commit5",
                commit_date=datetime(2023, 3, 6, 12, 0, 0),  # March 6
                is_private=False
            )
        ]
        
        self.db.add_all(commits)
        self.db.commit()
        
    def test_apply_date_filters(self):
        """Test that the apply_date_filters function properly filters by date range."""
        # Base query
        base_query = self.db.query(GitHubCommit).filter(GitHubCommit.github_id == "testuser")
        
        # First, check that we have 5 total commits as expected
        all_results = base_query.all()
        self.assertEqual(len(all_results), 5)  # Total sample data
        
        # Print out the dates to debug
        for commit in all_results:
            print(f"Commit date: {commit.commit_date}")
            
        # Test with from_date only
        from_date = date(2023, 3, 3)  # March 3, 2023
        filtered_query = apply_date_filters(base_query, from_date=from_date)
        results = filtered_query.all()
        # Should include commits from March 3, 4, 5, 6
        self.assertEqual(len(results), 4)  
        
        # Test with to_date only
        to_date = date(2023, 3, 4)  # March 4, 2023
        filtered_query = apply_date_filters(base_query, to_date=to_date)
        results = filtered_query.all()
        # Should include commits from March 2, 3, 4
        self.assertEqual(len(results), 3)  
        
        # Test with both from_date and to_date
        from_date = date(2023, 3, 3)  # March 3, 2023
        to_date = date(2023, 3, 4)  # March 4, 2023
        filtered_query = apply_date_filters(base_query, from_date=from_date, to_date=to_date)
        results = filtered_query.all()
        # Should include commits from March 3, 4
        self.assertEqual(len(results), 2)
