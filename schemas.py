from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, Any, List, Dict
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskLog(BaseModel):
    """任务日志模型"""
    timestamp: datetime = Field(..., description="日志时间戳")
    content: str = Field(..., description="日志内容")
    level: str = Field(default="info", description="日志级别")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2024-03-23T10:00:00",
                "content": "开始处理任务",
                "level": "info"
            }
        }
    )


class TaskBase(BaseModel):
    """任务基础模型"""
    params: Dict = Field(default_factory=dict, description="任务参数")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    result: Optional[Dict] = Field(default=None, description="任务结果")
    logs: List[TaskLog] = Field(default_factory=list, description="任务日志列表")


class TaskCreate(TaskBase):
    """任务创建模型"""
    pass


class TaskUpdate(BaseModel):
    """任务更新模型"""
    status: Optional[TaskStatus] = None
    result: Optional[Dict] = None
    logs: Optional[List[TaskLog]] = None
    params: Optional[Dict] = None

    model_config = ConfigDict(
        json_schema_extra={
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
    )


class Task(TaskBase):
    """任务模型"""
    id: str = Field(..., description="任务ID")
    created_at: datetime = Field(
        default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(
        default_factory=datetime.now, description="更新时间")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "1",
                "params": {
                    "name": "测试任务",
                    "description": "这是一个测试任务",
                    "priority": "high"
                },
                "status": "pending",
                "result": None,
                "logs": [
                    {
                        "timestamp": "2024-03-23T10:00:00",
                        "content": "任务创建成功",
                        "level": "info"
                    }
                ],
                "created_at": "2024-03-23T10:00:00",
                "updated_at": "2024-03-23T10:00:00"
            }
        }
    )
