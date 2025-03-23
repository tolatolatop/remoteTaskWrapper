FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# 将poetry添加到PATH
ENV PATH="/root/.local/bin:$PATH"

# 复制项目文件
COPY pyproject.toml poetry.lock ./
COPY README.md ./
COPY demo-warpper ./demo-warpper

# 配置poetry
RUN poetry config virtualenvs.create false

# 安装依赖
RUN poetry install --no-interaction --no-ansi --no-root

# 复制源代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["poetry", "run", "python", "main.py"] 