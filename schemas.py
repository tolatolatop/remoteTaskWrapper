from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="任务标题")
    description: str = Field(..., min_length=1,
                             max_length=1000, description="任务描述")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(
        None, min_length=1, max_length=100, description="任务标题")
    description: Optional[str] = Field(
        None, min_length=1, max_length=1000, description="任务描述")
    status: Optional[TaskStatus] = Field(None, description="任务状态")


class Task(TaskBase):
    id: str = Field(..., description="任务ID")
    created_at: datetime = Field(
        default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(
        default_factory=datetime.now, description="更新时间")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "1",
                "title": "完成项目文档",
                "description": "编写详细的项目文档，包括API说明和使用指南",
                "status": "pending",
                "created_at": "2024-03-23T10:00:00",
                "updated_at": "2024-03-23T10:00:00"
            }
        }
