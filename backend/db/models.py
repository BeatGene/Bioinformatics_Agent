"""
数据库模型 —— 对话线程、消息记录、研究报告持久化。
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _gen_id() -> str:
    return uuid.uuid4().hex[:12]


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    """对话线程 —— 一次完整的研究会话"""
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=_gen_id)
    title = Column(String(200), nullable=False, default="未命名研究")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
    status = Column(String(20), nullable=False, default="active")  # active / completed / archived

    # 关联
    messages = relationship("Message", back_populates="conversation",
                            order_by="Message.created_at", cascade="all, delete-orphan")
    research_records = relationship("ResearchRecord", back_populates="conversation",
                                    cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status": self.status,
            "message_count": len(self.messages) if self.messages else 0,
        }


class Message(Base):
    """对话消息"""
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_gen_id)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)          # user / assistant / system
    content = Column(Text, nullable=False, default="") # Markdown 内容
    snapshot_json = Column(JSON, nullable=True)        # 如果是 assistant 消息，存完整 ResearchSnapshot
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    conversation = relationship("Conversation", back_populates="messages")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "snapshot": self.snapshot_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ResearchRecord(Base):
    """研究记录 —— 一次 Agent 执行的完整状态存档"""
    __tablename__ = "research_records"

    id = Column(String, primary_key=True, default=_gen_id)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    thread_id = Column(String, nullable=False, index=True)     # LangGraph checkpoint thread_id
    query = Column(Text, nullable=False)                       # 用户查询
    max_papers = Column(Integer, nullable=False, default=5)
    final_report = Column(Text, nullable=True)                 # 最终报告 Markdown
    state_snapshot = Column(JSON, nullable=True)               # 完整状态快照
    status = Column(String(20), nullable=False, default="running")  # running / paused / completed / failed
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    conversation = relationship("Conversation", back_populates="research_records")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "thread_id": self.thread_id,
            "query": self.query,
            "max_papers": self.max_papers,
            "status": self.status,
            "has_report": bool(self.final_report),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
