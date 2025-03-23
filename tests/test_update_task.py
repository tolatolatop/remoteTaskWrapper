import pytest
from fastapi.testclient import TestClient
from main import app
import json
from datetime import datetime

client = TestClient(app)

# 测试数据
TEST_PARAMS = {
    "name": "测试任务",
    "description": "这是一个测试任务",
    "priority": "high"
}


@pytest.fixture
def test_task():
    """创建测试任务"""
    response = client.post(
        "/tasks",
        data={"params": json.dumps(TEST_PARAMS)}
    )
    return response.json()


def test_update_task_status(test_task):
    """测试更新任务状态"""
    task_id = test_task["id"]

    # 更新任务状态为进行中
    update_data = {
        "status": "in_progress"
    }
    response = client.put(
        f"/tasks/{task_id}",
        json=update_data
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "in_progress"
    assert data["params"] == TEST_PARAMS
    assert "updated_at" in data
    assert data["updated_at"] != test_task["updated_at"]


def test_update_task_params(test_task):
    """测试更新任务参数"""
    task_id = test_task["id"]

    # 更新任务参数
    new_params = {
        "name": "更新后的任务",
        "description": "这是更新后的描述",
        "priority": "low"
    }
    update_data = {
        "params": new_params
    }
    response = client.put(
        f"/tasks/{task_id}",
        json=update_data
    )

    assert response.status_code == 200
    data = response.json()
    assert data["params"] == new_params
    assert data["status"] == "pending"
    assert "updated_at" in data
    assert data["updated_at"] != test_task["updated_at"]


def test_update_task_not_found():
    """测试更新不存在的任务"""
    update_data = {
        "status": "in_progress"
    }
    response = client.put(
        "/tasks/999",
        json=update_data
    )

    assert response.status_code == 404
    assert "任务不存在" in response.json()["detail"]


def test_update_task_invalid_status(test_task):
    """测试使用无效的状态更新任务"""
    task_id = test_task["id"]

    # 使用无效的状态
    update_data = {
        "status": "invalid_status"
    }
    response = client.put(
        f"/tasks/{task_id}",
        json=update_data
    )

    assert response.status_code == 422  # FastAPI 的验证错误状态码


def test_update_task_multiple_fields(test_task):
    """测试同时更新多个字段"""
    task_id = test_task["id"]

    # 同时更新状态和参数
    update_data = {
        "status": "in_progress",
        "params": {
            "name": "多字段更新测试",
            "description": "这是多字段更新的描述"
        }
    }
    response = client.put(
        f"/tasks/{task_id}",
        json=update_data
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "in_progress"
    assert data["params"]["name"] == "多字段更新测试"
    assert data["params"]["description"] == "这是多字段更新的描述"
    assert "updated_at" in data
    assert data["updated_at"] != test_task["updated_at"]
