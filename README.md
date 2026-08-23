---
title: AI Medical Agent
emoji: 🏥
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# 🏥 AI 导诊系统

一个基于 DeepSeek V4 大模型的智能医疗问诊系统，支持用户端和管理端双入口，具备完整的问诊流程、病历管理、健康建议等功能。

## ✨ 功能特点

- 🤖 **AI 智能问诊** - 基于 DeepSeek V4 大模型
- 🔍 **向量搜索** - ChromaDB 向量数据库
- 📋 **5步问诊流程** - 结构化问诊
- 📊 **病历管理** - 完整的病历记录
- 🎯 **健康建议** - 个性化建议生成
- 🔐 **双端管理** - 用户端 + 管理端
- 📄 **PDF 报告** - 自动生成诊断报告
- 🚀 **多种部署** - 本地/云服务/生产环境

## 🚀 快速开始

### 方法 1：本地运行（最简单）

**Windows 用户**：
```cmd
双击运行：一键启动.bat
```

**Linux/macOS 用户**：
```bash
python 启动.py
```

### 方法 2：云服务部署（免费）

**Windows 用户**：
```cmd
双击运行：部署云服务.bat
选择：1）Render（免费，推荐）
```

**Linux/macOS 用户**：
```bash
chmod +x deploy_cloud.sh
./deploy_cloud.sh
```

### 方法 3：生产环境部署

- 阿里云轻量服务器：99元/月
- 腾讯云轻量服务器：99元/月

## 📋 前置条件

- Python 3.8+
- DeepSeek AI API Key（从 https://open.bigmodel.cn 获取）

## 🔧 配置

1. 复制配置文件：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，设置 API Key：
```bash
ZHIPUAI_API_KEY=your_api_key_here
```

## 📁 项目结构

```
medical_agent/
├── app.py                      # Flask 主应用
├── ai_glm_agent.py             # AI 代理
├── vector_store.py             # 向量数据库
├── mysql_store.py              # MySQL 存储
├── templates/                  # HTML 模板
│   ├── index.html             # 首页
│   ├── user/                  # 用户端模板
│   └── admin/                 # 管理端模板
├── static/                     # 静态资源
│   ├── css/                   # 样式文件
│   └── js/                    # JavaScript 文件
├── requirements.txt            # Python 依赖
├── .env.example               # 环境变量模板
├── Dockerfile                 # Docker 配置
├── docker-compose.yml         # Docker Compose 配置
├── deploy.sh                  # Linux 部署脚本
├── 部署云服务.bat             # Windows 云部署脚本
├── 一键启动.bat               # Windows 一键启动
└── README.md                  # 项目说明
```

## 🌐 访问地址

启动后访问：
- **用户端**: http://localhost:5000
- **管理端**: http://localhost:5000/admin/login

## 📚 文档

- [本地运行指南](本地运行指南.md) - 本地运行详细说明
- [快速上手](快速上手.md) - 三步快速上手
- [云服务部署指南](云服务部署指南.md) - 云服务部署详细说明
- [CLOUD_DEPLOYMENT_SIMPLE.md](CLOUD_DEPLOYMENT_SIMPLE.md) - 完整云部署文档

## 🎯 技术栈

- **后端**: Flask, Python 3.11
- **AI 模型**: DeepSeek V4 (DeepSeek AI)
- **向量数据库**: ChromaDB
- **关系数据库**: MySQL
- **前端**: HTML5, JavaScript, Bootstrap
- **部署**: Docker, Gunicorn, Nginx

## 🔐 安全说明

- `.env` 文件包含敏感信息，已添加到 `.gitignore`
- 用户密码使用加密存储
- 管理员密码使用加密存储
- SQL 注入防护
- XSS 攻击防护

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 联系方式

- GitHub Issues: https://github.com/your-username/medical-agent/issues

## 🎉 致谢

- DeepSeek AI - DeepSeek V4 大模型
- ChromaDB - 向量数据库
- Flask - Web 框架

---

**祝你使用愉快！** 🎊