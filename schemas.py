from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any, List, Dict
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskLog(BaseModel):
    timestamp: datetime = Field(
        default_factory=datetime.now, description="日志时间戳")
    content: str = Field(..., description="日志内容")
    level: str = Field(default="info", description="日志级别")


class TaskBase(BaseModel):
    params: dict = Field(..., description="任务参数")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    logs: List[TaskLog] = Field(default_factory=list, description="任务日志")


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    """任务更新模型"""
    status: Optional[TaskStatus] = None
    result: Optional[Dict] = None
    logs: Optional[List[TaskLog]] = None
    params: Optional[Dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "status": "running",
                "result": {"output": "处理完成"},
                "logs": [
                    {
                        "timestamp": "2024-03-23T10:00:00",
                        "content": "开始处理任务",
                        "level": "info"
                    }
                ],
                "params": {
                    "name": "更新后的任务",
                    "description": "这是更新后的描述"
                }
            }
        }


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
                "logs": [
                    {
                        "timestamp": "2024-03-23T10:00:00",
                        "content": "任务开始执行",
                        "level": "info"
                    }
                ],
                "created_at": "2024-03-23T10:00:00",
                "updated_at": "2024-03-23T10:00:00"
            }
        }
