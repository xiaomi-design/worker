"""微信自动监听模块（Windows 专用，基于 wxauto4 / wxauto）

仅在 Windows + 已登录 PC 微信下可用。其他平台 import 失败时 IS_AVAILABLE=False，
模块仍可被导入，调用 start/stop 会返回友好错误。

兼容两种 API：
  - wxauto4（适配微信 4.x，回调模式）：AddListenChat(name, callback) + 内部线程
  - wxauto 3.x（适配微信 3.x，轮询模式）：AddListenChat(who=name) + GetListenMessage()
两条路径都向上层暴露统一回调签名 (bound_group, sender, content)。
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
_BACKEND = None  # 'wxauto4' 或 'wxauto'

if IS_WINDOWS:
    # 优先 wxauto4（适配微信 4.x），不行再回退 wxauto 3.x
    try:
        from wxauto4 import WeChat as _WeChat  # type: ignore
        _BACKEND = "wxauto4"
        IS_AVAILABLE = True
    except Exception as e4:
        try:
            from wxauto import WeChat as _WeChat  # type: ignore
            _BACKEND = "wxauto"
            IS_AVAILABLE = True
            logger.warning("wxauto4 不可用 (%s)，回退到 wxauto 3.x（仅支持微信 3.x）", e4)
        except Exception as e3:
            _import_error = f"wxauto4: {type(e4).__name__}: {e4}; wxauto: {type(e3).__name__}: {e3}"
            logger.warning("wxauto4 / wxauto 均加载失败: %s", _import_error)
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

    def _make_callback(self, bound_group: str, on_message: OnMessage):
        """构造适配 wxauto4 (msg, chat) 签名的回调，转发为统一签名 (bound_group, sender, content)"""
        def _cb(msg, chat=None):
            try:
                attr = (getattr(msg, "attr", "") or "").lower()
                if attr in ("self", "system", "time", "tickle"):
                    return
                sender = (getattr(msg, "sender", "") or "").strip()
                content = (getattr(msg, "content", "") or "").strip()
                if not sender or not content:
                    return
                on_message(bound_group, sender, content)
            except Exception as e:
                logger.exception("回调处理异常: %s", e)
        return _cb

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
        callback = self._make_callback(bound_group, on_message)
        used_mode = None
        try:
            if _BACKEND == "wxauto4":
                # wxauto4：回调模式，框架内部线程会自动调用回调
                wx.AddListenChat(wechat_group, callback)
                used_mode = "callback"
            else:
                # wxauto 3.x：轮询模式，外部用 GetListenMessage() 拉
                try:
                    wx.AddListenChat(who=wechat_group)
                except TypeError:
                    wx.AddListenChat(nickname=wechat_group)
                used_mode = "polling"
        except Exception as e:
            msg = str(e)
            low = msg.lower()
            if "1400" in msg or "句柄" in msg or "handle" in low:
                # 缓存的 WeChat 主窗口句柄已失效（微信被关闭/重启/切换账号 等）
                # 丢弃实例，下次 start 会重新抓取
                with self._wx_lock:
                    self._wx = None
                raise RuntimeError(
                    f"无法监听「{wechat_group}」：微信窗口句柄失效（{msg}）。\n"
                    f"请确认：1) PC 微信已登录且主窗口未被关闭/最小化到托盘；"
                    f"2) 该群在微信会话列表里能看到（先在微信里点开一次该群）；"
                    f"3) 微信版本与 {_BACKEND} 兼容（当前 {_BACKEND}：4.x 用 wxauto4，3.x 用 wxauto）；"
                    f"然后重试。"
                )
            raise RuntimeError(f"添加监听失败：{msg}")
        with self._watchers_lock:
            self._watchers[wechat_group] = {
                "bound_group": bound_group,
                "on_message": on_message,
                "mode": used_mode,
            }
        if used_mode == "callback":
            # wxauto4：启动框架内部监听线程（如果未启动）
            for starter in ("_listener_start", "StartListening", "Start"):
                fn = getattr(wx, starter, None)
                if callable(fn):
                    try:
                        fn()
                        logger.debug("wxauto4 内部监听已通过 %s() 启动", starter)
                        break
                    except Exception as e:
                        logger.debug("调用 %s() 失败: %s", starter, e)
        else:
            self._ensure_poll_thread()
        logger.info("启动监听: 微信群「%s」→ 本程序群「%s」（%s 模式）",
                    wechat_group, bound_group, used_mode)

    def stop(self, wechat_group: str):
        with self._watchers_lock:
            if wechat_group not in self._watchers:
                raise RuntimeError(f"未在监听「{wechat_group}」")
            if self._wx:
                # 多种参数签名兜底
                removed = False
                for kw in ({"who": wechat_group}, {"nickname": wechat_group}):
                    try:
                        self._wx.RemoveListenChat(**kw)
                        removed = True
                        break
                    except TypeError:
                        continue
                    except Exception as e:
                        logger.warning("移除监听失败 (kw=%s): %s", kw, e)
                        break
                if not removed:
                    try:
                        self._wx.RemoveListenChat(wechat_group)
                    except Exception as e:
                        logger.warning("移除监听失败 (positional): %s", e)
            del self._watchers[wechat_group]
        logger.info("停止监听: 微信群「%s」", wechat_group)

    def status(self) -> dict:
        with self._watchers_lock:
            watchers = [
                {"wechat_group": wg, "bound_group": info["bound_group"], "mode": info.get("mode")}
                for wg, info in self._watchers.items()
            ]
        return {
            "available": IS_AVAILABLE,
            "platform": sys.platform,
            "backend": _BACKEND,
            "import_error": _import_error,
            "watchers": watchers,
        }

    def _ensure_poll_thread(self):
        # 仅 wxauto 3.x 走轮询；wxauto4 由框架内部回调
        if _BACKEND != "wxauto":
            return
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
                        self._dispatch_polling(info, m)
            time.sleep(1.0)

    @staticmethod
    def _dispatch_polling(info: dict, msg) -> None:
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

