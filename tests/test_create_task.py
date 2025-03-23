import pytest
from fastapi.testclient import TestClient
from main import app
import os
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
def test_file():
    # 创建测试文件
    test_file_path = "test_file.txt"
    with open(test_file_path, "w") as f:
        f.write("这是一个测试文件内容")
    yield test_file_path
    # 清理测试文件
    if os.path.exists(test_file_path):
        os.remove(test_file_path)


def test_create_task_without_file():
    """测试创建不带文件的任务"""
    response = client.post(
        "/tasks",
        data={"params": json.dumps(TEST_PARAMS)}
    )

    assert response.status_code == 200
    data = response.json()

    # 验证返回的任务数据
    assert "id" in data
    assert data["params"] == TEST_PARAMS
    assert data["status"] == "pending"
    assert "created_at" in data
    assert "updated_at" in data
    assert data["result"] is None
    assert data["logs"] == []


def test_create_task_with_file(test_file):
    """测试创建带文件的任务"""
    with open(test_file, "rb") as f:
        response = client.post(
            "/tasks",
            files={"file": ("test_file.txt", f, "text/plain")},
            data={"params": json.dumps(TEST_PARAMS)}
        )

    assert response.status_code == 200
    data = response.json()

    # 验证返回的任务数据
    assert "id" in data
    assert data["params"]["name"] == TEST_PARAMS["name"]
    assert data["params"]["description"] == TEST_PARAMS["description"]
    assert data["params"]["priority"] == TEST_PARAMS["priority"]
    assert "file_path" in data["params"]
    assert data["status"] == "pending"
    assert "created_at" in data
    assert "updated_at" in data
    assert data["result"] is None
    assert data["logs"] == []

    # 验证文件是否被正确保存
    file_path = data["params"]["file_path"]
    assert os.path.exists(file_path)

    # 清理测试文件
    if os.path.exists(file_path):
        os.remove(file_path)


def test_create_task_invalid_params():
    """测试使用无效参数创建任务"""
    response = client.post(
        "/tasks",
        data={"params": "invalid json"}
    )

    assert response.status_code == 400
    assert "无效的参数格式" in response.json()["detail"]


def test_create_task_empty_params():
    """测试使用空参数创建任务"""
    response = client.post(
        "/tasks",
        data={"params": "{}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["params"] == {}
    assert data["status"] == "pending"
