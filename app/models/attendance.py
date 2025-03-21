from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class Attendance(Base):
    """출석 모델"""
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    github_id = Column(String, nullable=False, index=True)  # 사용자의 GitHub ID (e.g. junho85)
    attendance_date = Column(Date, nullable=False, index=True)
    is_attended = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 사용자와 날짜의 조합은 고유해야 함
    __table_args__ = (
        UniqueConstraint('github_id', 'attendance_date', name='uix_github_id_attendance_date'),
    )

    def __repr__(self):
        return f"<Attendance(user_id={self.github_id}, date={self.attendance_date}, is_attended={self.is_attended})>"
