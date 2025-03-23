from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Dict
import json
from datetime import datetime
import os
from schemas import Task, TaskCreate, TaskUpdate, TaskStatus, TaskLog

app = FastAPI(title="任务管理器API")

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 存储所有活动的WebSocket连接
active_connections: List[WebSocket] = []

# 内存中存储任务
tasks: Dict[str, Task] = {}


@app.get("/")
async def read_root():
    return FileResponse("static/index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message["type"] == "create_task":
                task_data = message["task"]
                task = Task(
                    id=task_data["id"],
                    params=task_data["params"],
                    status=TaskStatus.PENDING,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                tasks[task.id] = task
                await broadcast_task_update("task_created", task)

            elif message["type"] == "update_task":
                task_id = message["task_id"]
                if task_id in tasks:
                    task = tasks[task_id]
                    if "status" in message:
                        task.status = TaskStatus(message["status"])
                    if "result" in message:
                        task.result = message["result"]
                    if "log" in message:
                        log_data = message["log"]
                        log = TaskLog(
                            timestamp=datetime.fromisoformat(
                                log_data["timestamp"]),
                            content=log_data["content"],
                            level=log_data.get("level", "info")
                        )
                        task.logs.append(log)
                    task.updated_at = datetime.now()
                    await broadcast_task_update("task_updated", task)

            elif message["type"] == "delete_task":
                task_id = message["task_id"]
                if task_id in tasks:
                    task = tasks.pop(task_id)
                    await broadcast_task_update("task_deleted", task)

    except WebSocketDisconnect:
        active_connections.remove(websocket)


async def broadcast_task_update(event_type: str, task: Task):
    message = {
        "type": event_type,
        "task": task.dict()
    }
    for connection in active_connections:
        await connection.send_text(json.dumps(message))


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
    return task


@app.post("/tasks/{task_id}/result")
async def submit_task_result(task_id: str, result: dict):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    task.result = result
    task.status = TaskStatus.COMPLETED
    task.updated_at = datetime.now()

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
    return {"message": "任务已删除", "task": task.dict()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
