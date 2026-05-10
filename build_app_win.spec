# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包脚本 - 生成 Windows .exe 桌面程序

使用方法（在 Windows 上）：
  pip install -r requirements.txt pyinstaller
  pyinstaller build_app_win.spec --clean --noconfirm
生成结果：dist\\微信记账机器人\\微信记账机器人.exe
"""

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
    ],
    hiddenimports=[
        'engine', 'parser', 'models', 'config', 'wechat', 'wechat_auto', 'report', 'web',
        'wxauto', 'uiautomation', 'comtypes',
    ],
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
    console=False,           # False=无控制台窗口；调试时可改 True 看错误
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

