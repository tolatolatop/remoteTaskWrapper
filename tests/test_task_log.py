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
    task_data = {
        "params": {"test": "data"},
        "status": "pending"
    }
    response = client.post("/tasks", data={"params": json.dumps(task_data)})
    return response.json()


def test_task_log_websocket(test_task):
    """测试基本的日志功能"""
    task_id = test_task["id"]

    # 连接sender和receiver
    with client.websocket_connect("/ws") as sender, client.websocket_connect("/ws") as receiver:
        # 初始化连接
        sender.send_json({
            "type": "init",
            "task_id": task_id,
            "role": "sender"
        })
        receiver.send_json({
            "type": "init",
            "task_id": task_id,
            "role": "receiver"
        })

        # 发送日志
        log_data = {
            "type": "update_task_log",
            "task_id": task_id,
            "log": {
                "timestamp": datetime.now().isoformat(),
                "content": "测试日志",
                "level": "info"
            }
        }
        sender.send_json(log_data)

        # 验证receiver收到更新
        response = receiver.receive_json()
        assert response["type"] == "task_updated"
        assert response["task"]["id"] == task_id
        assert len(response["task"]["logs"]) == 1
        assert response["task"]["logs"][0]["content"] == "测试日志"

        # 发送结束信号
        end_signal = {
            "type": "update_task_log",
            "task_id": task_id,
            "log": {
                "timestamp": datetime.now().isoformat(),
                "content": "END_SIGNAL",
                "level": "info"
            }
        }
        sender.send_json(end_signal)

        # 验证receiver收到结束信号
        response = receiver.receive_json()
        assert response["type"] == "task_updated"
        assert response["task"]["id"] == task_id
        assert len(response["task"]["logs"]) == 2
        assert response["task"]["logs"][1]["content"] == "END_SIGNAL"


def test_task_log_multiple_receivers(test_task):
    """测试多个receiver的情况"""
    task_id = test_task["id"]

    # 连接一个sender和两个receiver
    with client.websocket_connect("/ws") as sender, \
            client.websocket_connect("/ws") as receiver1, \
            client.websocket_connect("/ws") as receiver2:
        # 初始化连接
        sender.send_json({
            "type": "init",
            "task_id": task_id,
            "role": "sender"
        })
        receiver1.send_json({
            "type": "init",
            "task_id": task_id,
            "role": "receiver"
        })
        receiver2.send_json({
            "type": "init",
            "task_id": task_id,
            "role": "receiver"
        })

        # 发送日志
        log_data = {
            "type": "update_task_log",
            "task_id": task_id,
            "log": {
                "timestamp": datetime.now().isoformat(),
                "content": "广播测试日志",
                "level": "info"
            }
        }
        sender.send_json(log_data)

        # 验证两个receiver都收到更新
        for receiver in [receiver1, receiver2]:
            response = receiver.receive_json()
            assert response["type"] == "task_updated"
            assert response["task"]["id"] == task_id
            assert len(response["task"]["logs"]) == 1
            assert response["task"]["logs"][0]["content"] == "广播测试日志"

        # 发送结束信号
        end_signal = {
            "type": "update_task_log",
            "task_id": task_id,
            "log": {
                "timestamp": datetime.now().isoformat(),
                "content": "END_SIGNAL",
                "level": "info"
            }
        }
        sender.send_json(end_signal)

        # 验证两个receiver都收到结束信号
        for receiver in [receiver1, receiver2]:
            response = receiver.receive_json()
            assert response["type"] == "task_updated"
            assert response["task"]["id"] == task_id
            assert len(response["task"]["logs"]) == 2
            assert response["task"]["logs"][1]["content"] == "END_SIGNAL"


def test_task_log_sender_only(test_task):
    """测试只有sender连接的情况"""
    task_id = test_task["id"]

    # 只连接sender
    with client.websocket_connect("/ws") as sender:
        # 初始化连接
        sender.send_json({
            "type": "init",
            "task_id": task_id,
            "role": "sender"
        })

        # 发送日志
        log_data = {
            "type": "update_task_log",
            "task_id": task_id,
            "log": {
                "timestamp": datetime.now().isoformat(),
                "content": "只有sender的测试日志",
                "level": "info"
            }
        }
        sender.send_json(log_data)

        # 验证任务日志已更新
        response = client.get(f"/tasks/{task_id}/logs")
        assert response.status_code == 200
        logs = response.json()
        assert len(logs) == 1
        assert logs[0]["content"] == "只有sender的测试日志"
        assert logs[0]["level"] == "info"

        # 验证任务状态已更新
        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        task = response.json()
        assert task["updated_at"] is not None

        # 发送结束信号
        end_signal = {
            "type": "update_task_log",
            "task_id": task_id,
            "log": {
                "timestamp": datetime.now().isoformat(),
                "content": "END_SIGNAL",
                "level": "info"
            }
        }
        sender.send_json(end_signal)

        # 验证结束信号已记录
        response = client.get(f"/tasks/{task_id}/logs")
        assert response.status_code == 200
        logs = response.json()
        assert len(logs) == 2
        assert logs[1]["content"] == "END_SIGNAL"


def test_task_log_invalid_role(test_task):
    """测试无效的角色"""
    task_id = test_task["id"]

    with client.websocket_connect("/ws") as websocket:
        # 尝试使用无效的角色
        websocket.send_json({
            "type": "init",
            "task_id": task_id,
            "role": "invalid_role"
        })
        # 验证连接被关闭
        with pytest.raises(Exception):
            websocket.receive_json()


def test_task_log_invalid_task():
    """测试连接不存在的任务"""
    with client.websocket_connect("/ws") as websocket:
        # 尝试连接不存在的任务
        websocket.send_json({
            "type": "init",
            "task_id": "non_existent_task",
            "role": "sender"
        })
        # 验证连接被关闭
        with pytest.raises(Exception):
            websocket.receive_json()
