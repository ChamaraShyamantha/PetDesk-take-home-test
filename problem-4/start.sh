#!/bin/sh
set -e
gunicorn --bind 127.0.0.1:8000 --workers 2 --chdir /app app:app &
exec nginx -g "daemon off;"
