# 🚀 Quick Start Guide (桌面快速启动指南)

## 📁 Project Location

**Desktop folder**: `C:\Users\30974\Desktop\medical_agent`

---

## ✅ Script Fixed!

The startup script has been fixed to avoid encoding issues.

---

## 🎯 How to Start (启动方法)

### Step 1: Open Desktop Folder

1. Go to your Desktop
2. Find folder: **medical_agent**
3. Open it

### Step 2: Double-click Startup Script

Double-click: **一键启动.bat**

### Step 3: First Run Setup

**First run only** - the script will automatically:

1. **[1/5] Check Python**
   - Checks if Python is installed
   - Shows Python version

2. **[2/5] Install Dependencies**
   - Installs required packages
   - May take a few minutes

3. **[3/5] Check Config File**
   - Creates `.env` file from `.env.example`
   - Opens Notepad automatically

4. **[4/5] Configure API Key**
   - In Notepad, find: `ZHIPUAI_API_KEY=`
   - Paste your API Key after the `=` sign
   - Example: `ZHIPUAI_API_KEY=your_api_key_here`
   - Save and close Notepad
   - Press Enter to continue

5. **[5/5] Start Server**
   - Server starts automatically
   - Shows access URLs

---

## 🌐 Access URLs

After server starts:

- **User Portal**: http://localhost:5000
- **Admin Portal**: http://localhost:5000/admin/login

---

## 🔑 How to Get API Key

1. Visit: https://open.bigmodel.cn/
2. Register/Login
3. Go to: Console → API Keys
4. Click: "Create New Key"
5. Copy the API Key

---

## ⚠️ Troubleshooting

### Issue: "Python not found"

**Solution**:
1. Visit: https://www.python.org/downloads/
2. Download Python 3.8 or higher
3. Install with "Add Python to PATH" checked

### Issue: "Port 5000 is occupied"

**Solution**:
1. Close other applications
2. Or modify port in `.env` file: `FLASK_PORT=5001`

### Issue: "Dependencies installation failed"

**Solution**:
1. Manually install: `pip install -r requirements.txt`
2. Or use mirror: `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

---

## 🛑 How to Stop Server

**Press Ctrl+C** in the command window

---

## 📋 Other Scripts Available

| Script | Purpose |
|--------|---------|
| **一键启动.bat** | Local quick start |
| **部署云服务.bat** | Cloud deployment (free, no VM) |
| **上传到GitHub.bat** | Upload to GitHub |
| **start.bat** | Direct server start |
| **start_quick.bat** | Quick start |

---

## 📚 Documentation

| File | Description |
|------|-------------|
| **README.md** | Project documentation |
| **桌面使用指南.md** | Desktop usage guide |
| **快速上手.md** | Quick start guide |
| **云服务部署指南.md** | Cloud deployment guide |

---

## 🎉 Start Now!

**Easiest way**:
1. Open Desktop folder: `medical_agent`
2. Double-click: `一键启动.bat`
3. Configure API Key
4. Access: http://localhost:5000

**Enjoy!** 🚀