"""微信群消息监听模块

macOS 方案: 监听剪贴板 —— 从微信群复制消息后自动解析用户名和下注内容
零依赖，macOS 原生支持，无封号风险

新格式下，金额嵌入在下注文本中（如 3/1000），不再需要单独的金额字段。

支持的微信消息格式（从微信群直接复制）:
  格式1: "张三:\n3/1000"          （微信 macOS 复制格式）
  格式2: "张三：3/1000"           （中文冒号，单行）
  格式3: "张三:3/1000"            （英文冒号，单行）
  格式4: "张三 3/1000"            （空格分隔）
"""
import subprocess
import time
import re
from typing import Callable, List, Tuple, Optional


def get_clipboard() -> str:
    """获取 macOS 剪贴板内容"""
    result = subprocess.run(["pbpaste"], capture_output=True, text=True)
    return result.stdout.strip()


def parse_wechat_messages(text: str) -> List[Tuple[str, str]]:
    """解析微信群复制的消息，提取 (用户名, 下注内容)

    微信 macOS 复制多条消息的格式:
        张三:
        3/1000
        李四:
        2/3/500

    也支持单行格式:
        张三: 3/1000
        张三：2/3/500
        张三 3/1000
    """
    results = []
    lines = text.strip().splitlines()
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # ---- 模式1: "用户名:" 单独一行，下注在下一行 ----
        name_match = re.match(r'^(.+?)[：:]$', line)
        if name_match:
            user = name_match.group(1).strip()
            i += 1
            # 读取下一行作为下注内容
            if i < len(lines):
                bet_line = lines[i].strip()
                if bet_line:
                    results.append((user, bet_line))
                i += 1
            continue

        # ---- 模式2: "用户名: 下注内容" 同一行 ----
        inline_match = re.match(r'^(.+?)[：:]\s*(.+)$', line)
        if inline_match:
            user = inline_match.group(1).strip()
            bet_text = inline_match.group(2).strip()
            if bet_text:
                results.append((user, bet_text))
            i += 1
            continue

        # ---- 模式3: "用户名 下注内容" 空格分隔 ----
        parts = line.split(None, 1)
        if len(parts) == 2:
            user = parts[0]
            bet_text = parts[1].strip()
            if bet_text:
                results.append((user, bet_text))
        i += 1

    return results


class ClipboardWatcher:
    """剪贴板监听器 —— 检测到新的微信消息时自动解析下注"""

    def __init__(self, on_message: Callable[[str, str], None],
                 poll_interval: float = 1.0):
        """
        Args:
            on_message: 回调函数 (user, bet_text)
            poll_interval: 轮询间隔（秒）
        """
        self.on_message = on_message
        self.poll_interval = poll_interval
        self._last_clip = ""
        self._running = False

    def start(self):
        """开始监听（阻塞）"""
        self._running = True
        self._last_clip = get_clipboard()
        print("👀 剪贴板监听已启动")
        print("   从微信群选中消息 → 右键复制 → 自动识别下注")
        print("   按 Ctrl+C 返回主菜单\n")

        while self._running:
            try:
                clip = get_clipboard()
                if clip and clip != self._last_clip:
                    self._last_clip = clip
                    self._handle(clip)
                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                self.stop()
                break

    def stop(self):
        self._running = False
        print("\n👀 剪贴板监听已停止")

    def _handle(self, text: str):
        """处理剪贴板内容"""
        msgs = parse_wechat_messages(text)
        if not msgs:
            return
        for user, bet_text in msgs:
            try:
                self.on_message(user, bet_text)
            except Exception as e:
                print(f"⚠️  {user} 下注失败 [{bet_text}]: {e}")

