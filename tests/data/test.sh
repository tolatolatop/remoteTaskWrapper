# 创建任务
python client.py create tests/data/task_params.json tests/data/input.csv

# 获取任务文件
python client.py get-file task_id tests/data/downloaded_input.csv

# 提交任务结果
python client.py push-result task_id tests/data/task_result.json

# 获取任务结果
python client.py get-result task_id tests/data/downloaded_result.json

# 获取任务日志
python client.py get-log task_id tests/data/downloaded_logs.json

# 发送日志内容
cat tests/data/run.log | python client.py sender task_id