@echo off
REM 在 Windows 上打包成可执行 .exe
REM 双击或在 cmd 里运行: build_win.bat

cd /d "%~dp0"

echo [1/3] 安装依赖...
pip install -r requirements.txt
pip install pyinstaller
if errorlevel 1 goto :err

echo [2/3] 清理旧的 build/dist...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/3] 打包中（约需 1-3 分钟）...
pyinstaller build_app_win.spec --clean --noconfirm
if errorlevel 1 goto :err

echo.
echo =====================================================
echo  打包成功！
echo  可执行程序: dist\下注机器人\下注机器人.exe
echo  把整个 dist\下注机器人 文件夹复制走即可使用
echo =====================================================
pause
exit /b 0

:err
echo.
echo [失败] 请检查上方错误信息
pause
exit /b 1

