"""微信自动监听模块（Windows 专用，基于 wxauto）

仅在 Windows + 已登录 PC 微信下可用。其他平台 import 失败时 IS_AVAILABLE=False，
模块仍可被导入，调用 start/stop 会返回友好错误。

工作方式：后台 daemon 线程轮询 wx.GetListenMessage() 拉新消息，
按微信群名分发到回调 (bound_group, sender, content)。
"""
import sys
import time
import threading
import logging
from typing import Callable, Optional, Dict

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform.startswith("win")
IS_AVAILABLE = False
_import_error: Optional[str] = None
_WeChat = None

if IS_WINDOWS:
    try:
        from wxauto import WeChat as _WeChat  # type: ignore
        IS_AVAILABLE = True
    except Exception as e:
        _import_error = f"{type(e).__name__}: {e}"
        logger.warning("wxauto 加载失败: %s", _import_error)
else:
    _import_error = f"当前平台 {sys.platform} 不支持 wxauto（仅 Windows）"


# 回调签名：(bound_group, sender, content)
OnMessage = Callable[[str, str, str], None]


class WechatAutoListener:
    """单例：监听若干微信群 → 转发消息到业务层"""

    _instance: Optional["WechatAutoListener"] = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._wx = None
        self._wx_lock = threading.Lock()
        # wechat_group -> {'bound_group': str, 'on_message': OnMessage}
        self._watchers: Dict[str, dict] = {}
        self._watchers_lock = threading.Lock()
        self._poll_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()

    @property
    def available(self) -> bool:
        return IS_AVAILABLE

    @property
    def import_error(self) -> Optional[str]:
        return _import_error

    def _ensure_wx(self):
        if not IS_AVAILABLE:
            raise RuntimeError(_import_error or "wxauto 不可用")
        if self._wx is None:
            with self._wx_lock:
                if self._wx is None:
                    self._wx = _WeChat()
        return self._wx

    def start(self, wechat_group: str, bound_group: str, on_message: OnMessage):
        with self._watchers_lock:
            if wechat_group in self._watchers:
                raise RuntimeError(f"已在监听微信群「{wechat_group}」")
        wx = self._ensure_wx()
        # 先把目标聊天切到前台，避免 AddListenChat 拿到失效句柄（错误码 1400）
        try:
            wx.ChatWith(wechat_group)
        except Exception as e:
            logger.debug("ChatWith 失败（忽略，继续尝试 AddListenChat）: %s", e)
        try:
            try:
                wx.AddListenChat(who=wechat_group)
            except TypeError:
                # 兼容老版/wxautox 的参数名
                wx.AddListenChat(nickname=wechat_group)
        except Exception as e:
            msg = str(e)
            low = msg.lower()
            if "1400" in msg or "句柄" in msg or "handle" in low:
                # 缓存的 WeChat 主窗口句柄已失效（微信被关闭/重启/最小化到托盘）
                # 丢弃实例，下次 start 会重新抓取
                with self._wx_lock:
                    self._wx = None
                raise RuntimeError(
                    f"无法监听「{wechat_group}」：微信窗口句柄失效（{msg}）。\n"
                    f"请确认：1) PC 微信已登录且主窗口未被关闭/最小化到托盘；"
                    f"2) 该群在微信会话列表里能看到（先在微信里点开一次该群）；"
                    f"然后重试。"
                )
            raise RuntimeError(f"添加监听失败：{msg}")
        with self._watchers_lock:
            self._watchers[wechat_group] = {
                "bound_group": bound_group,
                "on_message": on_message,
            }
        self._ensure_poll_thread()
        logger.info("启动监听: 微信群「%s」→ 本程序群「%s」", wechat_group, bound_group)

    def stop(self, wechat_group: str):
        with self._watchers_lock:
            if wechat_group not in self._watchers:
                raise RuntimeError(f"未在监听「{wechat_group}」")
            if self._wx:
                try:
                    try:
                        self._wx.RemoveListenChat(who=wechat_group)
                    except TypeError:
                        self._wx.RemoveListenChat(nickname=wechat_group)
                except Exception as e:
                    logger.warning("移除监听失败: %s", e)
            del self._watchers[wechat_group]
        logger.info("停止监听: 微信群「%s」", wechat_group)

    def status(self) -> dict:
        with self._watchers_lock:
            watchers = [
                {"wechat_group": wg, "bound_group": info["bound_group"]}
                for wg, info in self._watchers.items()
            ]
        return {
            "available": IS_AVAILABLE,
            "platform": sys.platform,
            "import_error": _import_error,
            "watchers": watchers,
        }

    def _ensure_poll_thread(self):
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._stop_flag.clear()
        t = threading.Thread(target=self._poll_loop, name="wxauto-poll", daemon=True)
        self._poll_thread = t
        t.start()

    def _poll_loop(self):
        while not self._stop_flag.is_set():
            try:
                msgs = self._wx.GetListenMessage() if self._wx else None
            except Exception as e:
                logger.exception("拉取消息失败: %s", e)
                msgs = None
            if msgs:
                for chat, ms in msgs.items():
                    chat_name = getattr(chat, "who", None) or getattr(chat, "nickname", None) or str(chat)
                    info = self._watchers.get(chat_name)
                    if not info:
                        continue
                    for m in ms:
                        self._dispatch(info, m)
            time.sleep(1.0)

    @staticmethod
    def _dispatch(info: dict, msg) -> None:
        try:
            attr = (getattr(msg, "attr", "") or "").lower()
            if attr in ("self", "system", "time", "tickle"):
                return
            sender = (getattr(msg, "sender", "") or "").strip()
            content = (getattr(msg, "content", "") or "").strip()
            if not sender or not content:
                return
            info["on_message"](info["bound_group"], sender, content)
        except Exception as e:
            logger.exception("分发消息异常: %s", e)


def get_listener() -> WechatAutoListener:
    return WechatAutoListener()

