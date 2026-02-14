"""
Gunicorn configuration for production deployment on Fly.io
Optimized for CPU and memory efficiency
"""

import multiprocessing
import os

# Server behavior
bind = "0.0.0.0:8080"
backlog = 2048
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5

# Process naming
proc_name = "kuccps-courses"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Server hooks
def when_ready(server):
    """Called just after the server is started"""
    print(f"✅ Gunicorn server is ready with {workers} workers")

def on_exit(server):
    """Called just before exiting Gunicorn"""
    print("🛑 Gunicorn server shutting down")

# Application environment
raw_env = [
    f"FLASK_ENV={os.getenv('FLASK_ENV', 'production')}",
]

# Optimization flags
preload_app = False  # Don't preload to allow hot-reloading
max_requests = 10000  # Restart worker after 10k requests to prevent memory leaks
max_requests_jitter = 1000  # Random jitter to prevent thundering herd

# Socket settings
forwarded_allow_ips = "*"  # Trust X-Forwarded-* headers from proxy (Fly.io sets these)
secure_scheme_headers = {
    "X-FORWARDED_PROTOCOL": "ssl",
    "X-FORWARDED_PROTO": "https",
    "X-FORWARDED_SSL": "on",
}

print(f"🔧 Gunicorn configured for {workers} workers")
