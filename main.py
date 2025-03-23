from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Dict, Set
import json
from datetime import datetime
import os
from schemas import Task, TaskCreate, TaskUpdate, TaskStatus, TaskLog

app = FastAPI(title="任务管理器API")

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

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
        # 等待客户端发送初始化数据
        data = await websocket.receive_text()
        init_data = json.loads(data)

        if "type" not in init_data or init_data["type"] != "init":
            await websocket.close(code=1008, reason="需要初始化数据")
            return

        task_id = init_data.get("task_id")
        role = init_data.get("role")

        if not task_id or not role or role not in ["sender", "receiver"]:
            await websocket.close(code=1008, reason="无效的task_id或role")
            return

        # 检查任务是否存在
        if task_id not in tasks:
            await websocket.close(code=1008, reason="任务不存在")
            return

        # 连接WebSocket
        await manager.connect(websocket, task_id, role)

        # 根据角色处理消息
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if role == "sender":
                if message["type"] == "update_task_log":
                    task_id = message["task_id"]
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
                        # 广播给该任务的所有接收者
                        await manager.broadcast_to_task(task_id, {
                            "type": "task_updated",
                            "task": task.dict()
                        })
            else:  # receiver
                # 接收者不需要处理消息
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)
        raise e


# REST API endpoints
@app.get("/tasks", response_model=List[Task])
async def get_tasks():
    return list(tasks.values())


@app.post("/tasks", response_model=Task)
async def create_task(task: TaskCreate):
    task_id = str(len(tasks) + 1)
    new_task = Task(
        id=task_id,
        params=task.params,
        status=task.status,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    tasks[task_id] = new_task
    await manager.broadcast_to_task(task_id, {
        "type": "task_created",
        "task": new_task.dict()
    })
    return new_task


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    return tasks[task_id]


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: str, task_update: TaskUpdate):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    update_data = task_update.dict(exclude_unset=True)

    for field, value in update_data.items():
        setattr(task, field, value)

    task.updated_at = datetime.now()
    await manager.broadcast_to_task(task_id, {
        "type": "task_updated",
        "task": task.dict()
    })
    return task


@app.post("/tasks/{task_id}/result")
async def submit_task_result(task_id: str, result: dict):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    task.result = result
    task.status = TaskStatus.COMPLETED
    task.updated_at = datetime.now()

    await manager.broadcast_to_task(task_id, {
        "type": "task_updated",
        "task": task.dict()
    })
    return {"message": "任务结果已提交", "task": task.dict()}


@app.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    if task.result is None:
        raise HTTPException(status_code=404, detail="任务结果不存在")

    return task.result


@app.post("/tasks/{task_id}/log")
async def add_task_log(task_id: str, log: TaskLog):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    task.logs.append(log)
    task.updated_at = datetime.now()

    await manager.broadcast_to_task(task_id, {
        "type": "task_updated",
        "task": task.dict()
    })
    return {"message": "日志已添加", "task": task.dict()}


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
        "task": task.dict()
    })
    return {"message": "任务已删除", "task": task.dict()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
