import yaml
from pydantic_settings import BaseSettings
from typing import Optional, Dict


# YAML 파일 로더 함수
def load_yaml_config(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


class ProjectConfig(BaseSettings):
    start_date: str  # YYYY-MM-DD 형식
    total_days: int


class AppConfig(BaseSettings):
    database: dict
    github: dict
    admin: Optional[dict] = None
    auth: Optional[dict] = None
    project: Optional[Dict] = None

    @classmethod
    def from_yaml(cls, file_path: str):
        config_data = load_yaml_config(file_path)
        return cls(**config_data)


# 기본 YAML 설정 로드
config = AppConfig.from_yaml("config.yaml")

# TODO 환경변수 설정이 있으면 해당 설정이 우선 될 수 있도록 덮어 쓰기
