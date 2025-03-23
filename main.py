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
        await websocket.accept()
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

    async def broadcast_to_task(self, task_id: str, message: dict):
        if task_id in self.task_connections:
            for receiver in self.task_connections[task_id]["receiver"]:
                await receiver.send_text(json.dumps(message))


manager = ConnectionManager()

# 内存中存储任务
tasks: Dict[str, Task] = {}


@app.get("/")
async def read_root():
    return FileResponse("static/index.html")


@app.websocket("/ws")
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

        if "type" not in init_data or init_data["type"] != "init":
            logger.warning(f"收到无效的初始化数据类型: {init_data.get('type')}")
            await websocket.close(code=1008, reason="需要初始化数据")
            return

        task_id = init_data.get("task_id")
        role = init_data.get("role")
        logger.debug(f"初始化数据解析: task_id={task_id}, role={role}")

        if not task_id or not role or role not in ["sender", "receiver"]:
            logger.warning(f"无效的task_id或role: task_id={task_id}, role={role}")
            await websocket.close(code=1008, reason="无效的task_id或role")
            return

        # 检查任务是否存在
        if task_id not in tasks:
            logger.warning(f"尝试连接不存在的任务: task_id={task_id}")
            await websocket.close(code=1008, reason="任务不存在")
            return

        # 连接WebSocket
        logger.debug(f"正在将WebSocket连接到任务 {task_id} 作为 {role}")
        await manager.connect(websocket, task_id, role)
        logger.info(f"WebSocket已成功连接到任务 {task_id} 作为 {role}")

        # 根据角色处理消息
        while True:
            logger.debug(f"等待来自 {role} 的新消息...")
            data = await websocket.receive_text()
            logger.debug(f"收到消息: {data}")
            message = json.loads(data)

            if role == "sender":
                if message["type"] == "update_task_log":
                    task_id = message["task_id"]
                    logger.debug(f"处理来自sender的日志更新: task_id={task_id}")
                    if task_id in tasks:
                        task = tasks[task_id]
                        log_data = message["log"]
                        log = TaskLog(
                            timestamp=datetime.fromisoformat(
                                log_data["timestamp"]),
                            content=log_data["content"],
                            level=log_data.get("level", "info")
                        )
                        task.logs.append(log)
                        task.updated_at = datetime.now()
                        logger.debug(
                            f"已添加新日志: content={log.content}, level={log.level}")

                        # 广播给该任务的所有接收者
                        logger.debug(f"准备广播更新到任务 {task_id} 的所有接收者")
                        await manager.broadcast_to_task(task_id, {
                            "type": "task_updated",
                            "task": task.model_dump()
                        })
                        logger.debug("广播完成")
                    else:
                        logger.warning(f"尝试更新不存在的任务日志: task_id={task_id}")
            else:  # receiver
                logger.debug(f"收到来自receiver的消息，无需处理: {message}")

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
