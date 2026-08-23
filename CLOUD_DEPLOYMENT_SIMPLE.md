# AI 导诊系统 - 云服务部署指南（无虚拟机）

## 🌐 支持的云平台（无需虚拟机）

### ✅ 推荐方案（最简单）

| 云平台 | 部署方式 | 费用 | 域名 | SSL |
|-------|----------|------|------|-----|
| **Cloudflare Pages** | 静态托管 | 免费 | 支持 | 免费 |
| **Vercel** | 静态托管 | 免费 | 支持 | 免费 |
| **Netlify** | 静态托管 | 免费 | 支持 | 免费 |
| **GitHub Pages** | 静态托管 | 免费 | 支持 | 免费 |

### ✅ 服务器方案

| 云平台 | 服务 | 费用 | 优势 |
|-------|------|------|------|
| **阿里云** | 轻量应用服务器 | 99元/月起 | 性能好，国内访问快 |
| **腾讯云** | 轻量应用服务器 | 99元/月起 | 稳定，生态完善 |
| **华为云** | 云耀服务器 | 99元/月起 | 性价比高 |
| **AWS** | Lightsail | 5美元/月起 | 全球覆盖 |
| **DigitalOcean** | Droplets | 5美元/月起 | 简单易用 |

---

## 🚀 方案一：静态托管（推荐）

### 适用平台：Cloudflare Pages / Vercel / Netlify

#### 1. 创建静态版本

```bash
# 安装静态站点生成工具
pip install flask-static-renderer

# 生成静态文件
python generate_static.py
```

#### 2. 部署到 Cloudflare Pages

**步骤**：
1. 注册 Cloudflare 账号
2. 登录 Cloudflare Dashboard → Pages
3. 连接 GitHub 仓库
4. 自动构建和部署
5. 设置域名和 SSL

#### 3. 部署到 Vercel

**步骤**：
1. 注册 Vercel 账号
2. 连接 GitHub 仓库
3. 配置构建设置
4. 自动部署

### 静态托管的优缺点

**✅ 优点**：
- 完全免费
- 自动 HTTPS
- 全球 CDN 加速
- 无需管理服务器
- 自动扩容

**❌ 缺点**：
- 不能运行 Python（后端无法使用 DeepSeek V4）
- 只能静态展示

---

## 🚀 方案二：PaaS 平台（推荐）

### 适用平台：Render / Heroku / PythonAnywhere

#### 1. Render 部署（推荐）

**优势**：免费额度，自动 SSL，支持 Python

**步骤**：
1. 注册 Render 账号
2. 连接 GitHub 仓库
3. 创建 Web Service
4. 配置环境变量
5. 设置构建设置

**配置**：
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`
- Environment: Python 3.11

#### 2. Heroku 部署

**步骤**：
1. 注册 Heroku 账号
2. 安装 Heroku CLI
3. 创建应用
4. 配置 `Procfile`
5. 部署

**Procfile**：
```
web: gunicorn app:app --timeout 120
```

#### 3. PythonAnywhere 部署

**优势**：专门支持 Python，简单易用

**步骤**：
1. 注册 PythonAnywhere 账号
2. 创建 Web 应用
3. 上传代码
4. 配置环境变量

### PaaS 平台的优缺点

**✅ 优点**：
- 无需管理服务器
- 自动 SSL
- 自动扩容
- 支持完整 Python 功能
- 有免费额度

**❌ 缺点**：
- 免费额度有限制
- 自定义配置需要付费

---

## 🚀 方案三：轻量服务器（推荐生产环境）

### 适用平台：阿里云轻量 / 腾讯云轻量 / AWS Lightsail

#### 1. 部署到阿里云轻量应用服务器

**配置建议**：
- 2核2GB（99元/月）
- Ubuntu 22.04 LTS
- 40GB SSD

**部署步骤**：
```bash
# SSH 连接到服务器
ssh root@your-server-ip

# 更新系统
apt update && apt upgrade -y

# 安装 Python
apt install python3 python3-pip python3-venv -y

# 上传项目代码
scp -r /path/to/medical_agent root@your-server-ip:/opt/

# 配置环境
cd /opt/medical_agent
pip install -r requirements.txt

# 配置 .env 文件
nano .env

# 启动应用
nohup gunicorn app:app --bind 0.0.0.0:5000 --workers 2 --timeout 120 > app.log 2>&1 &

# 配置 Nginx
apt install nginx -y
cat > /etc/nginx/sites-available/medical_agent << EOF
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

ln -s /etc/nginx/sites-available/medical_agent /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx
```

#### 2. 使用一键部署脚本

```bash
# 在服务器上运行
curl -o deploy.sh https://raw.githubusercontent.com/your-repo/deploy.sh
chmod +x deploy.sh
./deploy.sh
```

### 轻量服务器的优缺点

**✅ 优点**：
- 完全控制服务器
- 性能稳定
- 可自由配置
- 性价比高
- 支持完整功能

**❌ 缺点**：
- 需要基础运维知识
- 需要手动维护安全
- SSL 需要额外配置

---

## 🚀 方案四：容器平台（高级）

### 适用平台：AWS ECS / Google Cloud Run / Azure Container Instances

#### Cloud Run 部署（最推荐）

**优势**：自动扩容，按使用付费，无需管理服务器

**步骤**：
1. 构建 Docker 镜像
2. 推送到 Google Container Registry
3. 部署到 Cloud Run
4. 设置环境变量
5. 配置域名和 SSL

---

## 🎯 推荐方案选择

### 个人开发者（免费）

**首选**：Render + Vercel
- Render 运行后端（DeepSeek V4）
- Vercel 静态展示前端
- 总费用：免费

### 小团队（低成本）

**首选**：阿里云轻量服务器
- 配置：2核2GB，99元/月
- 性能稳定，国内访问快
- 一键部署脚本

### 企业级（高可用）

**首选**：阿里云 + Cloudflare CDN
- 阿里云服务器（2核4GB）
- Cloudflare 免费 CDN
- 负载均衡，自动备份

---

## 📋 部署清单

### Render 部署清单

- [ ] 注册 Render 账号
- [ ] 连接 GitHub 仓库
- [ ] 创建 Web Service
- [ ] 设置环境变量：
  ```
  ZHIPUAI_API_KEY=***
  FLASK_HOST=0.0.0.0
  FLASK_PORT=5000
  ```
- [ ] 配置构建设置：
  ```
  Build Command: pip install -r requirements.txt
  Start Command: gunicorn app:app --timeout 120
  ```
- [ ] 设置域名
- [ ] 启动部署

### 阿里云轻量服务器清单

- [ ] 购买轻量应用服务器（2核2GB Ubuntu 22.04）
- [ ] 重置 root 密码
- [ ] 配置安全组（开放 80, 443, 22 端口）
- [ ] 上传项目代码
- [ ] 运行部署脚本
- [ ] 配置域名解析
- [ ] 申请免费 SSL（使用 Let's Encrypt）

---

## 💡 推荐方案

### 对于初学者：**Render**
- 完全免费
- 无需运维
- 自动 HTTPS
- 支持 Python

### 对于国内用户：**阿里云轻量服务器**
- 性能好
- 访问快
- 性价比高
- 一键部署

### 对于想要免费的用户：**GitHub + Render + Vercel**
- GitHub Pages 静态展示
- Render 运行后端
- 总成本：免费

---

## 🎉 总结

**最推荐的部署方案**：

1. **免费方案**：Render（后端）+ Vercel（前端）
2. **低成本方案**：阿里云轻量服务器 + 一键部署脚本
3. **生产环境**：阿里云服务器 + Cloudflare CDN

**都不需要虚拟机！** 🎉