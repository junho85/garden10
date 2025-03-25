from sqlalchemy import Column, Integer, String, DateTime, Text, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class GitHubCommit(Base):
    """GitHub 커밋 내역 모델"""
    __tablename__ = "github_commits"

    id = Column(Integer, primary_key=True, index=True)  # 기본 ID (자동 증가)
    github_id = Column(String, nullable=False, index=True)  # 사용자의 GitHub ID (e.g. junho85)
    commit_id = Column(String, nullable=False, index=True)  # GitHub 커밋 해시 ID (e.g. a1b2c3d4...)
    repository = Column(String, nullable=False)  # 커밋이 속한 저장소 이름 (e.g. username/repo-name)
    message = Column(Text, nullable=False)  # 커밋 메시지
    commit_url = Column(String, nullable=False)  # 커밋 URL (e.g. https://github.com/username/repo-name/commit/a1b2c3d4...)
    commit_date = Column(DateTime(timezone=True), nullable=False)  # 커밋이 이루어진 날짜 및 시간
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # 생성 시간
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # 업데이트 시간
    
    # commit_id와 repository 조합에 대한 유니크 제약조건 추가
    __table_args__ = (
        UniqueConstraint('commit_id', 'repository', name='uix_commit_repo'),
    )

    def __repr__(self):
        return f"<GitHubCommit(github_id={self.github_id}, commit_id={self.commit_id}, repository={self.repository})>"