import sys
import os
from cx_Freeze import setup, Executable

# 依赖包
packages = ["os", "sys", "PyQt6", "requests", "bs4", "urllib", "json", "subprocess"]

# 需要包含的文件
include_files = []
if os.path.exists("settings.json"):
    include_files.append("settings.json")

# 构建选项
build_exe_options = {
    "packages": packages,
    "include_files": include_files,
    "include_msvcr": True,  # 包含Visual C++ 运行库
}

# 可执行文件基础
base = None
if sys.platform == "win32":
    base = "Win32GUI"  # 不显示控制台窗口

# 可执行文件
executables = [
    Executable(
        "main.py",  # 替换为您的主文件名
        base=base,
        target_name="文件管理工具.exe",
        icon="app_icon.ico",
    )
]

# 设置
setup(
    name="文件管理工具",
    version="1.0.0",
    description="文件管理和网页爬虫工具",
    options={"build_exe": build_exe_options},
    executables=executables
)