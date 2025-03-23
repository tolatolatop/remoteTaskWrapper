import click
import requests
import json
import os
import websockets
import asyncio
import sys
from datetime import datetime

# 服务器地址
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"


def load_json_file(file_path):
    """加载JSON文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json_file(data, file_path):
    """保存JSON文件"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@click.group()
def cli():
    """任务管理器客户端"""
    pass


@cli.command()
@click.argument('params_file', type=click.Path(exists=True))
@click.argument('file_path', type=click.Path(exists=True), required=False)
def create(params_file, file_path):
    """创建新任务"""
    try:
        params = load_json_file(params_file)

        # 准备请求数据
        files = {}
        if file_path:
            files['file'] = ('file', open(file_path, 'rb'))

        data = {'params': json.dumps(params)}

        # 发送请求
        response = requests.post(f"{BASE_URL}/tasks", files=files, data=data)
        response.raise_for_status()

        task = response.json()
        click.echo(f"任务创建成功: {task['id']}")
        save_json_file(task, f"task_{task['id']}.json")

    except Exception as e:
        click.echo(f"创建任务失败: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('task_id')
@click.argument('output_path', type=click.Path())
def get_file(task_id, output_path):
    """获取任务文件"""
    try:
        response = requests.get(f"{BASE_URL}/tasks/{task_id}/file")
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            f.write(response.content)
        click.echo(f"文件已保存到: {output_path}")

    except Exception as e:
        click.echo(f"获取文件失败: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('task_id')
@click.argument('result_file', type=click.Path(exists=True))
@click.argument('file_path', type=click.Path(exists=True), required=False)
def push_result(task_id, result_file, file_path):
    """提交任务结果"""
    try:
        result = load_json_file(result_file)

        # 准备请求数据
        files = {}
        if file_path:
            files['file'] = ('file', open(file_path, 'rb'))

        data = {'result_params': json.dumps(result)}

        # 发送请求
        response = requests.post(
            f"{BASE_URL}/tasks/{task_id}/result", files=files, data=data)
        response.raise_for_status()

        click.echo("结果提交成功")

    except Exception as e:
        click.echo(f"提交结果失败: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('task_id')
@click.argument('output_file', type=click.Path())
def get_result(task_id, output_file):
    """获取任务结果"""
    try:
        response = requests.get(f"{BASE_URL}/tasks/{task_id}/result")
        response.raise_for_status()

        result = response.json()
        save_json_file(result, output_file)
        click.echo(f"结果已保存到: {output_file}")

    except Exception as e:
        click.echo(f"获取结果失败: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('task_id')
@click.argument('output_file', type=click.Path())
def get_log(task_id, output_file):
    """获取任务日志"""
    try:
        response = requests.get(f"{BASE_URL}/tasks/{task_id}/logs")
        response.raise_for_status()

        logs = response.json()
        save_json_file(logs, output_file)
        click.echo(f"日志已保存到: {output_file}")

    except Exception as e:
        click.echo(f"获取日志失败: {str(e)}", err=True)
        sys.exit(1)


async def sender_websocket(task_id):
    """WebSocket发送者"""
    uri = f"{WS_URL}/ws/sender"
    try:
        async with websockets.connect(uri) as websocket:
            # 发送初始化数据
            await websocket.send(json.dumps({"task_id": task_id}))
            click.echo("WebSocket连接已建立，开始发送数据...")

            # 从标准输入读取并发送数据
            while True:
                try:
                    line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                    if not line:
                        click.echo("输入流已关闭")
                        break
                    await websocket.send(line)
                except KeyboardInterrupt:
                    click.echo("\n检测到键盘中断，正在关闭连接...")
                    break
                except Exception as e:
                    click.echo(f"读取输入时发生错误: {str(e)}", err=True)
                    break

    except websockets.exceptions.ConnectionClosed:
        click.echo("WebSocket连接已关闭", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"WebSocket连接失败: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('task_id')
def sender(task_id):
    """启动WebSocket发送者"""
    asyncio.run(sender_websocket(task_id))


if __name__ == '__main__':
    cli()
