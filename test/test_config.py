from unittest import TestCase

from app.config import config


class TestConfig(TestCase):
    def test_load_config(self):
        print(f"Database URL: {config.database['url']}")  # 환경 변수 값 적용
        print(f"GitHub API Token: {config.github['api_token']}")

