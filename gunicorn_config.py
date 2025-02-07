import multiprocessing

# Binding
bind = "0.0.0.0:10000"

# Worker Processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gthread"
threads = 4

# Timeout
timeout = 300
graceful_timeout = 300
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

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
reload = True
daemon = False

# Server Hooks
def on_starting(server):
    print("Starting Gunicorn Server...") 