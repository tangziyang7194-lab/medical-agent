#!/usr/bin/env python3
"""
一键启动脚本 - 不需要 Docker，直接本地运行
适合完全不懂部署的用户
"""

import sys
import os
import subprocess
from pathlib import Path

def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 版本太低，需要 Python 3.8 或更高版本")
        print(f"   当前版本: Python {version.major}.{version.minor}.{version.micro}")
        print("   请从 https://www.python.org/downloads/ 下载安装")
        return False
    print(f"✅ Python 版本: {version.major}.{version.minor}.{version.micro}")
    return True

def check_pip():
    """检查 pip"""
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"],
                      check=True, capture_output=True)
        print("✅ pip 已安装")
        return True
    except:
        print("❌ pip 未安装")
        print("   请重新安装 Python 并勾选 'Add Python to PATH'")
        return False

def install_dependencies():
    """安装依赖"""
    print("\n📦 安装依赖包...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                      check=True)
        print("✅ 依赖包安装完成")
        return True
    except Exception as e:
        print(f"❌ 依赖包安装失败: {e}")
        return False

def check_config():
    """检查配置文件"""
    print("\n⚙️  检查配置文件...")

    if not Path(".env").exists():
        if Path(".env.example").exists():
            print("   .env 文件不存在，从 .env.example 创建...")
            from shutil import copyfile
            copyfile(".env.example", ".env")
            print("✅ .env 文件已创建")
            print("\n⚠️  重要：请编辑 .env 文件，设置 ZHIPUAI_API_KEY")
            print("   获取方式: https://open.bigmodel.cn/")
            print("   文件位置: " + str(Path(".env").absolute()))
            return False
        else:
            print("❌ .env.example 文件不存在")
            return False

    # 检查关键配置
    from dotenv import load_dotenv
    load_dotenv()

    if not os.getenv("ZHIPUAI_API_KEY"):
        print("⚠️  ZHIPUAI_API_KEY 未配置")
        print("   请编辑 .env 文件，添加: ZHIPUAI_API_KEY=your_key_here")
        return False

    print("✅ 配置文件检查完成")
    return True

def init_database():
    """初始化数据库"""
    print("\n🗄️  初始化数据库...")
    try:
        sys.path.insert(0, str(Path.cwd()))
        from mysql_store import init_database
        init_database()
        print("✅ 数据库初始化完成")
        return True
    except Exception as e:
        print(f"⚠️  数据库初始化失败: {e}")
        print("   系统将在首次运行时自动创建数据库")
        return True

def start_server():
    """启动服务器"""
    print("\n🚀 启动服务器...")
    print("=" * 60)
    print("  AI 导诊系统启动成功！")
    print("=" * 60)
    print()
    print("  访问地址:")
    print("    用户端: http://localhost:5000")
    print("    管理端: http://localhost:5000/admin/login")
    print()
    print("  按 Ctrl+C 停止服务器")
    print("=" * 60)
    print()

    try:
        # 导入 Flask 应用
        from app import app

        # 启动应用
        app.run(host='127.0.0.1', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\n\n🛑 服务器已停止")
    except Exception as e:
        print(f"\n❌ 服务器启动失败: {e}")
        print("\n💡 建议:")
        print("   1. 检查是否安装了所有依赖: pip install -r requirements.txt")
        print("   2. 检查 .env 文件配置是否正确")
        print("   3. 检查端口 5000 是否被占用")

def main():
    print("=" * 60)
    print("  AI 导诊系统 - 一键启动")
    print("=" * 60)
    print()

    # 检查 Python 版本
    if not check_python_version():
        return 1

    # 检查 pip
    if not check_pip():
        return 1

    # 安装依赖
    if not install_dependencies():
        return 1

    # 检查配置
    if not check_config():
        print("\n请先配置好 .env 文件，然后重新运行此脚本")
        input("按回车键退出...")
        return 1

    # 初始化数据库
    init_database()

    # 启动服务器
    start_server()

    return 0

if __name__ == "__main__":
    sys.exit(main())