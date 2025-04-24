import multiprocessing
import os

# Binding
port = os.environ.get('PORT', '10000')
bind = f"0.0.0.0:{port}"

# Worker Processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gthread"
threads = 4
max_requests = 1000
max_requests_jitter = 50

# Timeout
timeout = 120
graceful_timeout = 120
keepalive = 5

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'
capture_output = True
enable_stdio_inheritance = True

# SSL (if needed)
# keyfile = "path/to/keyfile"
# certfile = "path/to/certfile"

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# Process Naming
proc_name = "certificados_app"

# Server Mechanics
preload_app = True
reload = False  # Disable reload in production
daemon = False
forwarded_allow_ips = '*'

# Error Handling
worker_abort_on_error = False
retry_on_term = True

def when_ready(server):
    """Log when server is ready"""
    print(f"Gunicorn Server is ready. Listening on port {port}")

def on_starting(server):
    """Log when server is starting"""
    print(f"Starting Gunicorn Server on port {port}...")

def on_exit(server):
    """Log when server is shutting down"""
    print("Shutting down Gunicorn Server...") 