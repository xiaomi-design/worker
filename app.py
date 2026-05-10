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


def _pause_on_exit(msg=""):
    """崩溃时保持控制台窗口打开，方便看错误"""
    if msg:
        print("\n" + "=" * 60)
        print(msg)
        print("=" * 60)
    try:
        input("\n按回车键退出...")
    except Exception:
        try:
            os.system("pause")
        except Exception:
            pass


def main():
    import traceback
    try:
        import webview
    except Exception as e:
        traceback.print_exc()
        _pause_on_exit(f"❌ 加载 pywebview 失败: {e}\n请检查 PyInstaller 是否正确打包了 webview 模块")
        return
    try:
        from web import app
    except Exception as e:
        traceback.print_exc()
        _pause_on_exit(f"❌ 加载 web 模块失败: {e}")
        return

    def run_flask():
        try:
            app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
        except Exception:
            traceback.print_exc()

    try:
        t = threading.Thread(target=run_flask, daemon=True)
        t.start()
        time.sleep(0.8)
        webview.create_window(
            "🧾 微信记账机器人",
            "http://127.0.0.1:5000",
            width=1100,
            height=750,
            resizable=True,
        )
        webview.start()
    except Exception as e:
        traceback.print_exc()
        _pause_on_exit(f"❌ 窗口启动失败: {e}")


if __name__ == "__main__":
    main()

