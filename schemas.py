from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskBase(BaseModel):
    params: dict = Field(..., description="任务参数")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    status: Optional[TaskStatus] = Field(None, description="任务状态")
    result: Optional[dict] = Field(None, description="任务结果")


class Task(TaskBase):
    id: str = Field(..., description="任务ID")
    created_at: datetime = Field(
        default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(
        default_factory=datetime.now, description="更新时间")
    result: Optional[dict] = Field(None, description="任务结果")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "1",
                "params": {"input": "测试数据"},
                "status": "pending",
                "result": None,
                "created_at": "2024-03-23T10:00:00",
                "updated_at": "2024-03-23T10:00:00"
            }
        }
