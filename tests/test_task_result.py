import pytest
from fastapi.testclient import TestClient
from main import app
import json
from datetime import datetime
import os

client = TestClient(app)

# 测试数据
TEST_PARAMS = {
    "name": "测试任务",
    "description": "这是一个测试任务",
    "priority": "high"
}

# 测试结果数据
TEST_RESULT = {
    "output": "任务处理完成",
    "metrics": {
        "accuracy": 0.95,
        "processing_time": 1.5
    }
}


@pytest.fixture
def test_task():
    """创建测试任务"""
    response = client.post(
        "/tasks",
        data={"params": json.dumps(TEST_PARAMS)}
    )
    return response.json()


@pytest.fixture
def test_file():
    """创建测试文件"""
    test_file_path = "test_result.txt"
    with open(test_file_path, "w") as f:
        f.write("这是测试结果文件的内容")
    yield test_file_path
    # 清理测试文件
    if os.path.exists(test_file_path):
        os.remove(test_file_path)


def test_submit_task_result(test_task):
    """测试提交任务结果"""
    task_id = test_task["id"]

    # 提交任务结果
    response = client.post(
        f"/tasks/{task_id}/result",
        data={"result_params": json.dumps(TEST_RESULT)}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["task"]["result"] == TEST_RESULT
    assert data["task"]["status"] == "completed"
    assert "updated_at" in data["task"]
    assert data["task"]["updated_at"] != test_task["updated_at"]


def test_submit_task_result_with_file(test_task, test_file):
    """测试提交带文件的任务结果"""
    task_id = test_task["id"]

    # 准备文件上传
    with open(test_file, "rb") as f:
        files = {"file": ("test_result.txt", f, "text/plain")}
        data = {"result_params": json.dumps(TEST_RESULT)}

        # 提交任务结果和文件
        response = client.post(
            f"/tasks/{task_id}/result",
            files=files,
            data=data
        )

    assert response.status_code == 200
    data = response.json()
    assert data["task"]["result"]["output"] == TEST_RESULT["output"]
    assert data["task"]["result"]["metrics"] == TEST_RESULT["metrics"]
    assert "file_path" in data["task"]["result"]
    assert data["task"]["status"] == "completed"


def test_get_task_result(test_task):
    """测试获取任务结果"""
    task_id = test_task["id"]

    # 先提交结果
    client.post(
        f"/tasks/{task_id}/result",
        data={"result_params": json.dumps(TEST_RESULT)}
    )

    # 获取任务结果
    response = client.get(f"/tasks/{task_id}/result")

    assert response.status_code == 200
    data = response.json()
    assert data == TEST_RESULT


def test_get_task_result_file(test_task, test_file):
    """测试获取任务结果文件"""
    task_id = test_task["id"]

    # 先提交结果和文件
    with open(test_file, "rb") as f:
        files = {"file": ("test_result.txt", f, "text/plain")}
        data = {"result_params": json.dumps(TEST_RESULT)}
        client.post(
            f"/tasks/{task_id}/result",
            files=files,
            data=data
        )

    # 获取结果文件
    response = client.get(f"/tasks/{task_id}/result/file")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"] == 'attachment; filename="test_result.txt"'


def test_get_task_result_not_found(test_task):
    """测试获取不存在的任务结果"""
    task_id = test_task["id"]

    response = client.get(f"/tasks/{task_id}/result")

    assert response.status_code == 404
    assert response.json()["detail"] == "任务结果不存在"


def test_get_task_result_file_not_found(test_task):
    """测试获取不存在的任务结果文件"""
    task_id = test_task["id"]

    # 先提交结果（不带文件）
    client.post(
        f"/tasks/{task_id}/result",
        data={"result_params": json.dumps(TEST_RESULT)}
    )

    # 尝试获取结果文件
    response = client.get(f"/tasks/{task_id}/result/file")

    assert response.status_code == 404
    assert response.json()["detail"] == "任务结果没有关联的文件"
