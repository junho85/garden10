from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    """사용자 모델"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    github_id = Column(String, unique=True, nullable=False, index=True)
    github_profile_url = Column(String, nullable=True)
    github_api_token = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, github_id={self.github_id})>"

    @property
    def display_name(self):
        """표시 이름을 반환합니다. 이름이 없으면 GitHub ID를 사용합니다."""
        return self.name or self.github_id