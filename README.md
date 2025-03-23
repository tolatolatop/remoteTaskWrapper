# 实时任务管理器

这是一个使用FastAPI和WebSocket构建的实时任务管理器。它提供了以下功能：

- 创建新任务
- 更新任务状态
- 删除任务
- 实时任务状态更新
- 响应式Web界面

## 功能特点

- 实时更新：使用WebSocket实现任务状态的实时更新
- 简洁的界面：直观的用户界面设计
- RESTful API：提供标准的REST API接口
- 响应式设计：适配各种屏幕尺寸

## 安装和运行

1. 确保已安装Python 3.11或更高版本
2. 安装依赖：
   ```bash
   poetry install
   ```
3. 运行应用：
   ```bash
   poetry run python main.py
   ```
4. 在浏览器中访问：`http://localhost:8000`

## API接口

### WebSocket接口
- WebSocket URL: `ws://localhost:8000/ws`

支持的消息类型：
- `create_task`: 创建新任务
- `update_task`: 更新任务状态
- `delete_task`: 删除任务

### REST API接口
- GET `/tasks`: 获取所有任务列表

## 使用说明

1. 在主页面上，您可以：
   - 创建新任务（填写标题和描述）
   - 查看所有任务列表
   - 更新任务状态（完成/待完成）
   - 删除任务

2. 所有操作都会实时反映在所有连接的客户端上

## 技术栈

- FastAPI
- WebSocket
- HTML5
- JavaScript
- CSS3 