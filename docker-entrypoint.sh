#!/usr/bin/env bash
set -euo pipefail
# 确保我们在应用目录中
cd /data
# 传递所有参数并以无缓冲输出运行 bot.py
exec python -u bot.py "$@"
