"""Gunicorn config for Hostinger VPS.

Binds a dedicated port so the existing website on :80 is not replaced.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = 2
timeout = 120
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
capture_output = True
worker_tmp_dir = "/dev/shm"
