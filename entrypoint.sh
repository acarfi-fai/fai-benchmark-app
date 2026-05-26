#!/bin/sh
set -e

/usr/sbin/sshd

exec python /app/start_inspect_view.py