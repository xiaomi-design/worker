#!/usr/bin/env python3
"""微信记账机器人 — 桌面窗口版（pywebview）"""
import sys
import os
import io
import threading
import time

# Windows 下 stdout 默认 GBK，遇到 emoji 会抛 UnicodeEncodeError；
# PyInstaller --windowed 模式下 stdout/stderr 可能为 None，需要兜底
def _force_utf8(stream_name):
    s = getattr(sys, stream_name, None)
    if s is None:
        setattr(sys, stream_name, open(os.devnull, "w", encoding="utf-8"))
        return
    try:
        s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        try:
            setattr(sys, stream_name,
                    io.TextIOWrapper(s.buffer, encoding="utf-8", errors="replace"))
        except Exception:
            pass

_force_utf8("stdout")
_force_utf8("stderr")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

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
        "🧾 微信记账机器人",
        "http://127.0.0.1:5000",
        width=1100,
        height=750,
        resizable=True,
    )
    webview.start()

