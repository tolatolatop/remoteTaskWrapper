from schemas import Task, TaskCreate, TaskUpdate, TaskStatus, TaskLog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Dict, Set, Optional
import json
from datetime import datetime
import os
import logging
from logging.handlers import RotatingFileHandler
import asyncio
# 配置日志


def setup_logger():
    # 创建日志目录
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # 创建logger对象
    logger = logging.getLogger("task_manager")
    logger.setLevel(logging.DEBUG)

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # 创建文件处理器
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "task_manager.log"),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)

    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # 添加处理器到logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# 创建全局logger对象
logger = setup_logger()


app = FastAPI(title="任务管理器API")

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 创建上传文件存储目录
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 存储所有活动的WebSocket连接


class ConnectionManager:
    def __init__(self):
        # 按task_id分组的连接
        self.task_connections: Dict[str, Dict[str, Set[WebSocket]]] = {}
        # 存储每个连接的task_id和角色
        self.connection_info: Dict[WebSocket, Dict[str, str]] = {}

    async def connect(self, websocket: WebSocket, task_id: str, role: str):
        if task_id not in self.task_connections:
            self.task_connections[task_id] = {
                "sender": set(), "receiver": set()}

        self.task_connections[task_id][role].add(websocket)
        self.connection_info[websocket] = {"task_id": task_id, "role": role}

    def disconnect(self, websocket: WebSocket):
        if websocket in self.connection_info:
            info = self.connection_info[websocket]
            task_id = info["task_id"]
            role = info["role"]

            if task_id in self.task_connections:
                self.task_connections[task_id][role].remove(websocket)
                if not self.task_connections[task_id]["sender"] and not self.task_connections[task_id]["receiver"]:
                    del self.task_connections[task_id]

            del self.connection_info[websocket]

    def _serialize_datetime(self, obj):
        """递归处理datetime对象的序列化"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._serialize_datetime(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_datetime(item) for item in obj]
        return obj

    async def broadcast_to_task(self, task_id: str, message: dict):
        if task_id in self.task_connections:
            # 序列化消息中的所有datetime对象
            serialized_message = {
                "type": message["type"],
                "task": self._serialize_datetime(message["task"])
            }
            # 获取所有接收者
            receivers = self.task_connections[task_id]["receiver"]
            logger.debug(f"准备向 {len(receivers)} 个接收者广播消息")

            # 并发发送消息给所有接收者
            for receiver in receivers:
                try:
                    await receiver.send_json(serialized_message)
                    await receiver.receive_json()
                    logger.debug(f"消息已发送到接收者: {receiver}")
                except Exception as e:
                    logger.error(f"发送消息到接收者时出错: {str(e)}")
                    # 如果发送失败，断开连接
                    self.disconnect(receiver)


manager = ConnectionManager()

# 内存中存储任务
tasks: Dict[str, Task] = {}


@app.get("/")
async def read_root():
    return FileResponse("static/index.html")


@app.websocket("/ws/sender")
async def websocket_endpoint(websocket: WebSocket):
    try:
        logger.debug("收到新的WebSocket连接请求")
        # 先接受WebSocket连接
        await websocket.accept()
        logger.debug("WebSocket连接已接受")

        # 等待客户端发送初始化数据
        logger.debug("等待客户端发送初始化数据...")
        data = await websocket.receive_text()
        logger.debug(f"收到初始化数据: {data}")
        init_data = json.loads(data)

        task_id = init_data.get("task_id")
        # 检查任务是否存在
        if task_id not in tasks:
            logger.warning(f"尝试连接不存在的任务: task_id={task_id}")
            await websocket.close(code=1008, reason="任务不存在")
            return

        while True:
            data = await websocket.receive_text()
            logger.debug(f"收到消息: {data}")
            task = tasks[task_id]
            task.logs.append(
                TaskLog(level="INFO", content=data, timestamp=datetime.now().isoformat()))
            if data == "END_SIGNAL":
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket连接断开: {websocket}")
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket处理过程中发生错误: {str(e)}", exc_info=True)
        manager.disconnect(websocket)
        raise e


@app.websocket("/ws/receiver")
async def websocket_endpoint(websocket: WebSocket):
    try:
        logger.debug("收到新的WebSocket连接请求")
        # 先接受WebSocket连接
        await websocket.accept()
        logger.debug("WebSocket连接已接受")

        # 等待客户端发送初始化数据
        logger.debug("等待客户端发送初始化数据...")
        data = await websocket.receive_text()
        logger.debug(f"收到初始化数据: {data}")
        init_data = json.loads(data)

        task_id = init_data.get("task_id")
        # 检查任务是否存在
        if task_id not in tasks:
            logger.warning(f"尝试连接不存在的任务: task_id={task_id}")
            await websocket.close(code=1008, reason="任务不存在")
            return

        log_index = 0
        while True:
            if log_index < len(tasks[task_id].logs):
                content = tasks[task_id].logs[log_index].content
                await websocket.send_text(content)
                logger.debug(f"index: {log_index} 发送消息: {content}")
                if content == "END_SIGNAL":
                    break
                log_index += 1
            else:
                await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        logger.info(f"WebSocket连接断开: {websocket}")
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket处理过程中发生错误: {str(e)}", exc_info=True)
        manager.disconnect(websocket)
        raise e


# REST API endpoints
@app.get("/tasks", response_model=List[Task])
async def get_tasks():
    return list(tasks.values())


@app.post("/tasks", response_model=Task)
async def create_task(
    file: Optional[UploadFile] = File(None),
    params: str = Form(...)
):
    try:
        # 解析参数
        params_dict = json.loads(params)
        logger.debug(f"创建新任务，参数: {params_dict}")

        # 处理文件上传
        file_path = None
        if file:
            # 生成唯一的文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_extension = os.path.splitext(file.filename)[1]
            unique_filename = f"{timestamp}_{file.filename}"
            file_path = os.path.join(UPLOAD_DIR, unique_filename)

            # 保存文件
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

            # 将文件路径添加到参数中
            params_dict["file_path"] = file_path
            logger.debug(f"文件已上传: {file_path}")

        # 创建任务
        task_id = str(len(tasks) + 1)
        new_task = Task(
            id=task_id,
            params=params_dict,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        tasks[task_id] = new_task
        logger.info(f"任务创建成功: {task_id}")

        await manager.broadcast_to_task(task_id, {
            "type": "task_created",
            "task": new_task.model_dump()
        })
        return new_task
    except json.JSONDecodeError:
        logger.error(f"创建任务失败: 无效的参数格式")
        raise HTTPException(status_code=400, detail="无效的参数格式")
    except Exception as e:
        logger.error(f"创建任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    return tasks[task_id]


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: str, task_update: TaskUpdate):
    if task_id not in tasks:
        logger.warning(f"更新任务失败: 任务不存在 {task_id}")
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    update_data = task_update.model_dump()
    logger.debug(f"更新任务 {task_id}: {update_data}")

    # 更新任务字段
    for field, value in update_data.items():
        if value is not None:  # 只更新非None的字段
            if field == "params":
                # 对于params字段，直接更新整个字典
                task.params = value
                logger.debug(f"更新任务参数: {value}")
            else:
                setattr(task, field, value)
                logger.debug(f"更新任务字段 {field}: {value}")

    task.updated_at = datetime.now()
    logger.info(f"任务更新成功: {task_id}")

    await manager.broadcast_to_task(task_id, {
        "type": "task_updated",
        "task": task.model_dump()
    })
    return task


@app.post("/tasks/{task_id}/result")
async def submit_task_result(
    task_id: str,
    file: Optional[UploadFile] = File(None),
    result_params: str = Form(...)
):
    if task_id not in tasks:
        logger.warning(f"提交任务结果失败: 任务不存在 {task_id}")
        raise HTTPException(status_code=404, detail="任务不存在")

    try:
        # 解析结果参数
        result_dict = json.loads(result_params)
        logger.debug(f"提交任务结果 {task_id}: {result_dict}")

        # 处理结果文件上传
        file_path = None
        if file:
            # 生成唯一的文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_extension = os.path.splitext(file.filename)[1]
            unique_filename = f"{timestamp}_{file.filename}"
            file_path = os.path.join(UPLOAD_DIR, unique_filename)

            # 保存文件
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

            # 将文件路径和原始文件名添加到结果中
            result_dict["file_path"] = file_path
            result_dict["original_filename"] = file.filename  # 保存原始文件名
            logger.debug(f"结果文件已上传: {file_path}")

        task = tasks[task_id]
        task.result = result_dict
        task.status = TaskStatus.COMPLETED
        task.updated_at = datetime.now()
        logger.info(f"任务结果提交成功: {task_id}")

        await manager.broadcast_to_task(task_id, {
            "type": "task_updated",
            "task": task.model_dump()
        })
        return {"message": "任务结果已提交", "task": task.model_dump()}
    except json.JSONDecodeError:
        logger.error(f"提交任务结果失败: 无效的结果参数格式")
        raise HTTPException(status_code=400, detail="无效的结果参数格式")
    except Exception as e:
        logger.error(f"提交任务结果失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    if task.result is None:
        raise HTTPException(status_code=404, detail="任务结果不存在")

    return task.result


@app.get("/tasks/{task_id}/result/file")
async def get_task_result_file(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    if task.result is None:
        raise HTTPException(status_code=404, detail="任务结果不存在")

    file_path = task.result.get("file_path")
    if not file_path:
        raise HTTPException(status_code=404, detail="任务结果没有关联的文件")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="结果文件不存在")

    # 使用保存的原始文件名
    original_filename = task.result.get(
        "original_filename", os.path.basename(file_path))

    return FileResponse(
        path=file_path,
        filename=original_filename,
        media_type='application/octet-stream'
    )


@app.post("/tasks/{task_id}/log")
async def add_task_log(task_id: str, log: TaskLog):
    if task_id not in tasks:
        logger.warning(f"添加任务日志失败: 任务不存在 {task_id}")
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    task.logs.append(log)
    task.updated_at = datetime.now()
    logger.info(f"任务日志添加成功: {task_id}, 级别: {log.level}, 内容: {log.content}")

    await manager.broadcast_to_task(task_id, {
        "type": "task_updated",
        "task": task.model_dump()
    })
    return {"message": "日志已添加", "task": task.model_dump()}


@app.get("/tasks/{task_id}/logs")
async def get_task_logs(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    return task.logs


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks.pop(task_id)
    await manager.broadcast_to_task(task_id, {
        "type": "task_deleted",
        "task": task.model_dump()
    })
    return {"message": "任务已删除", "task": task.model_dump()}


@app.get("/tasks/{task_id}/params")
async def get_task_params(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    return {
        "params": task.params,
        "file_path": task.params.get("file_path")
    }


@app.get("/tasks/{task_id}/file")
async def get_task_file(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    file_path = task.params.get("file_path")

    if not file_path:
        raise HTTPException(status_code=404, detail="任务没有关联的文件")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        path=file_path,
        filename=os.path.basename(file_path),
        media_type='application/octet-stream'
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
