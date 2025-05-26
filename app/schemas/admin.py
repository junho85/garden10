from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class AttendanceUpdateRequest(BaseModel):
    github_id: str
    date: str
    is_attended: bool


class AddUserRequest(BaseModel):
    github_id: str


class LogEntry(BaseModel):
    timestamp: datetime
    level: str
    message: str


class MotivationalPromptRequest(BaseModel):
    prompt_template: str


class EncouragementMessageRequest(BaseModel):
    prompt: Optional[str] = None
    use_auto_prompt: Optional[bool] = True
    prompt_template: Optional[str] = "정원사들의 출석 현황을 보고 따뜻하고 격려적인 응원 메시지를 작성해주세요."


class SystemStatusResponse(BaseModel):
    timestamp: str
    system: dict
    process: dict


class GitHubAPIStatusResponse(BaseModel):
    status: str
    message: str
    response_time_ms: float
    github_zen: Optional[str]


class AttendanceRefreshResponse(BaseModel):
    success: bool
    message: str
    date: str
    updated_users: List[str]
    detailed_results: List[dict]
    errors: List[dict]
    stats: dict


class UserAddResponse(BaseModel):
    success: bool
    message: str
    user: Optional[dict] = None