from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Dict
import json
from datetime import datetime
from pydantic import BaseModel
import os

app = FastAPI()

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 存储所有活动的WebSocket连接
active_connections: List[WebSocket] = []

# 任务模型


class Task(BaseModel):
    id: str
    title: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime


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
                task = Task(
                    id=message["task"]["id"],
                    title=message["task"]["title"],
                    description=message["task"]["description"],
                    status="pending",
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                tasks[task.id] = task
                await broadcast_task_update("task_created", task)

            elif message["type"] == "update_task":
                task_id = message["task_id"]
                if task_id in tasks:
                    task = tasks[task_id]
                    task.status = message["status"]
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


@app.get("/tasks")
async def get_tasks():
    return list(tasks.values())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
