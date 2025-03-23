import pytest
from fastapi.testclient import TestClient
from main import app
import json
from datetime import datetime
import logging
import asyncio
import threading
import time

# 配置日志记录器
logger = logging.getLogger("test_task_log")
logger.setLevel(logging.DEBUG)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# 创建格式化器
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# 添加处理器到logger
logger.addHandler(console_handler)

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
    logger.info("开始创建测试任务")
    task_data = {
        "params": {"test": "data"},
        "status": "pending"
    }
    response = client.post("/tasks", data={"params": json.dumps(task_data)})
    logger.info(f"测试任务创建完成，ID: {response.json()['id']}")
    return response.json()


def send_log_in_threading(client, task_id):
    """在多线程中发送日志"""
    def send_log():
        with client.websocket_connect("/ws/sender") as sender:
            # 初始化连接
            logger.debug("正在发送初始化数据...")
            sender.send_text(json.dumps({"task_id": task_id}))

            # 发送测试日志
            for i in range(2):
                logger.debug(f"发送日志: {i}")
                sender.send_text("测试日志")
                time.sleep(0.2)

            # 发送结束信号
            logger.debug("正在发送结束信号...")
            sender.send_text("END_SIGNAL")
            logger.debug("结束信号发送完成")

    threading.Thread(target=send_log).start()


def test_task_log_websocket(test_task):
    """测试基本的日志功能"""
    logger.info("开始测试基本的WebSocket日志功能")
    task_id = test_task["id"]

    # 连接receiver
    logger.debug("正在建立WebSocket连接...")
    with client.websocket_connect("/ws/receiver") as receiver:
        logger.debug("WebSocket连接已建立")

        # 发送初始化数据
        receiver.send_text(json.dumps({"task_id": task_id}))
        logger.debug("初始化数据发送完成")

        # 启动sender线程
        send_log_in_threading(client, task_id)

        # 接收日志
        received_logs = []
        while True:
            try:
                logger.debug("等待receiver接收消息...")
                message = receiver.receive_text()
                received_logs.append(message)
                logger.debug(f"receiver已收到消息: {message}")

                if message == "END_SIGNAL":
                    logger.debug("receiver已收到结束信号")
                    break
            except Exception as e:
                logger.exception(e)
                break

    assert len(received_logs) == 3  # 2条测试日志 + 1条结束信号
    assert received_logs[-1] == "END_SIGNAL"
    logger.info("基本WebSocket日志功能测试完成")


def test_task_log_sender_only(test_task):
    """测试只有sender连接的情况"""
    task_id = test_task["id"]

    # 只连接sender
    with client.websocket_connect("/ws/sender") as sender:
        # 初始化连接
        sender.send_text(json.dumps({"task_id": task_id}))

        # 发送测试日志
        sender.send_text("只有sender的测试日志")

        # 验证任务日志已更新
        response = client.get(f"/tasks/{task_id}/logs")
        assert response.status_code == 200
        logs = response.json()
        assert len(logs) == 1
        assert logs[0]["content"] == "只有sender的测试日志"
        assert logs[0]["level"] == "INFO"

        # 发送结束信号
        sender.send_text("END_SIGNAL")

        # 验证结束信号已记录
        response = client.get(f"/tasks/{task_id}/logs")
        assert response.status_code == 200
        logs = response.json()
        assert len(logs) == 2
        assert logs[1]["content"] == "END_SIGNAL"


def test_task_log_invalid_task():
    """测试连接不存在的任务"""
    with client.websocket_connect("/ws/sender") as websocket:
        # 尝试连接不存在的任务
        websocket.send_text(json.dumps({"task_id": "non_existent_task"}))
        # 验证连接被关闭
        with pytest.raises(Exception):
            websocket.receive_text()
