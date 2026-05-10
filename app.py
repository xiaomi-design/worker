#!/usr/bin/env python3
"""下注机器人 — 桌面窗口版（pywebview）"""
import sys
import os
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import webview
from web import app


def run_flask():
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    # Flask 在后台线程启动
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    # 等服务起来
    time.sleep(0.8)
    # 创建窗口
    webview.create_window(
        "🎲 下注机器人",
        "http://127.0.0.1:5000",
        width=1100,
        height=750,
        resizable=True,
    )
    webview.start()

