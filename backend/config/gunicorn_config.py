# Gunicorn configuration file
import multiprocessing
import os
from pathlib import Path

# Корень backend для путей к логам
BACKEND_DIR = Path(__file__).resolve().parent.parent

# Server socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 300
keepalive = 5

# Logging — логи в backend/logs
log_dir = BACKEND_DIR / "logs"
log_dir.mkdir(exist_ok=True)
accesslog = str(log_dir / "access.log")
errorlog = str(log_dir / "error.log")
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

proc_name = "bonds-screener-api"
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None
preload_app = True
max_requests = 1000
max_requests_jitter = 50
