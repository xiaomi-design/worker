# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包脚本 - 生成 Windows .exe 桌面程序

使用方法（在 Windows 上）：
  pip install -r requirements.txt pyinstaller
  pyinstaller build_app_win.spec --clean --noconfirm
生成结果：dist\\微信记账机器人\\微信记账机器人.exe
"""

import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# 显式确认 pywebview 已装在打包环境，否则 collect_all 会静默返回空导致运行时找不到模块
try:
    import webview as _webview_check
    print(f"[spec] pywebview located: {_webview_check.__file__}")
except Exception as e:
    raise SystemExit(
        f"[spec] FATAL: pywebview 未安装在打包 Python ({sys.executable}) 中: {e}\n"
        f"请先运行: pip install pywebview"
    )

# 完整收集 pywebview（动态加载 winforms/edge 后端，必须用 collect_all）
_wv_datas, _wv_bins, _wv_hidden = collect_all('webview')
print(f"[spec] webview collected: {len(_wv_datas)} data, {len(_wv_bins)} bin, {len(_wv_hidden)} hidden")
if not _wv_hidden:
    raise SystemExit("[spec] FATAL: collect_all('webview') 返回空，pywebview 安装可能损坏")

# 完整收集 wxauto（依赖 uiautomation/comtypes 类型库）— 缺失不致命，仅警告
def _safe_collect(pkg):
    try:
        d, b, h = collect_all(pkg)
        print(f"[spec] {pkg} collected: {len(d)} data, {len(b)} bin, {len(h)} hidden")
        return d, b, h
    except Exception as e:
        print(f"[spec] WARN: collect_all({pkg!r}) failed: {e}")
        return [], [], []

_wa_datas, _wa_bins, _wa_hidden = _safe_collect('wxauto')
_ua_datas, _ua_bins, _ua_hidden = _safe_collect('uiautomation')
_ct_datas, _ct_bins, _ct_hidden = _safe_collect('comtypes')

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=_wv_bins + _wa_bins + _ua_bins + _ct_bins,
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
    ] + _wv_datas + _wa_datas + _ua_datas + _ct_datas,
    hiddenimports=[
        'engine', 'parser', 'models', 'config', 'wechat', 'wechat_auto', 'report', 'web',
        'clr_loader', 'clr_loader.netfx', 'clr_loader.types',
        'proxy_tools', 'bottle', 'typing_extensions',
    ] + _wv_hidden + _wa_hidden + _ua_hidden + _ct_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='微信记账机器人',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,            # 调试期：True=带控制台便于看错误；稳定后改 False
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='微信记账机器人',
)

