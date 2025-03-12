import os
import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from datetime import date, timedelta
from typing import Optional, List, Dict, Any, ClassVar


class UserConfig(BaseSettings):
    """사용자 설정"""
    github_id: str
    github_api_token: Optional[str] = None


class Settings(BaseSettings):
    """애플리케이션 설정"""

    # 데이터베이스 설정
    DATABASE_URL: str = Field(default="postgresql://myuser:mypassword@db:5432/mydatabase")

    # GitHub API 설정
    GITHUB_API_TOKEN: Optional[str] = None

    # 참가자 목록
    USERS: List[UserConfig] = []


def load_config_from_yaml(file_path: str = None) -> Dict[str, Any]:
    """YAML 설정 파일에서 설정을 로드합니다."""
    if file_path is None:
        # 환경 변수에서 설정 파일 경로를 가져오거나 기본값 사용
        file_path = os.getenv("CONFIG_FILE_PATH", "config.yaml")

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    except Exception as e:
        print(f"YAML 설정 파일 로드 중 오류 발생: {e}")
        return {}


# YAML 설정 파일 로드
yaml_config = load_config_from_yaml()

# 환경 변수와 YAML 설정을 결합하여 설정 인스턴스 생성
settings_dict = {}

# YAML 설정에서 값 가져오기
if yaml_config:
    # 기본 설정
    settings_dict.update({
        k.upper(): v for k, v in yaml_config.items()
        if k not in ['users']
    })

    # 사용자 목록 변환
    if 'users' in yaml_config and isinstance(yaml_config['users'], list):
        users = []
        for user_item in yaml_config['users']:
            # 문자열인 경우 (github_id만 있는 경우)
            if isinstance(user_item, str):
                users.append(UserConfig(github_id=user_item))
            # 딕셔너리인 경우
            elif isinstance(user_item, dict) and 'github_id' in user_item:
                user_config = {
                    'github_id': user_item['github_id'],
                }
                # 개별 사용자의 GitHub API 토큰이 있으면 추가
                if 'github_api_token' in user_item:
                    user_config['github_api_token'] = user_item['github_api_token']
                
                users.append(UserConfig(**user_config))

        settings_dict['USERS'] = users

# 환경 변수에서 설정 로드
env_settings = {}

# 환경 변수 설정이 YAML 설정보다 우선함
settings_dict.update(env_settings)

# 설정 인스턴스 생성
settings = Settings(**settings_dict)


# 참가자 목록 관련 함수
def get_users() -> List[UserConfig]:
    """설정에서 참가자 목록을 반환합니다."""
    return settings.USERS


def get_github_ids() -> List[str]:
    """참가자들의 GitHub ID 목록을 반환합니다."""
    return [user.github_id for user in settings.USERS]
