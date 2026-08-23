"""
Flask Web 界面 - 医疗问诊智能体
"""

import os
import sys
import uuid
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, send_file, Response
from datetime import datetime
import time
from functools import wraps

# 确保能导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from medical_agent import MedicalConsultationAgent
from regions import get_provinces, get_cities, get_districts, format_location
from email_pdf import validate_email, get_email_provider_name, generate_pdf, send_report_email

app = Flask(__name__)

# ========== 防 DoS 限流：1 秒最多 10 次请求/IP ==========
from collections import defaultdict, deque

RATE_LIMIT_PER_SEC = 10
_rate_buckets = defaultdict(deque)
_rate_last_cleanup = time.time()

# ========== 云端精简模式（PythonAnywhere 免费版无数据库） ==========
CLOUD_MODE = os.environ.get("CLOUD_MODE") == "1"


@app.context_processor
def inject_cloud_mode():
    return {"is_cloud": CLOUD_MODE}


@app.before_request
def rate_limit_requests():
    """全局限流：静态资源不限，其余请求 1 秒最多 10 次/IP，超限返回 429"""
    global _rate_last_cleanup
    if request.path.startswith("/static/"):
        return None
    now = time.time()
    # 每 5 分钟清理无活跃窗口的 IP，防止内存膨胀
    if now - _rate_last_cleanup > 300:
        for ip in [k for k, q in _rate_buckets.items() if not q or q[-1] < now - 5]:
            _rate_buckets.pop(ip, None)
        _rate_last_cleanup = now
    ip = request.remote_addr or "unknown"
    q = _rate_buckets[ip]
    while q and q[0] < now - 1.0:
        q.popleft()
    if len(q) >= RATE_LIMIT_PER_SEC:
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "请求过于频繁，请 1 秒后再试"}), 429
        return ("<!doctype html><html><meta charset='utf-8'><body style='font-family:sans-serif;text-align:center;margin-top:80px;color:#555;'><h2>⏳ 请求过于频繁</h2><p>请 1 秒后再试（429 Too Many Requests）</p></body></html>", 429)
    q.append(now)
    return None

app.secret_key = os.urandom(24)

# ========== 管理员认证（基于admin_auth模块）==========
from admin_auth import (
    register_admin, login_admin, get_admin_user, has_admin_users,
    send_sms_code, verify_sms_code, validate_phone, get_all_admins
)

def admin_required(f):
    """管理员登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required_api(f):
    """管理员API验证装饰器 (返回JSON)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return jsonify({"success": False, "error": "未登录或权限不足，请先登录管理端"}), 403
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    """用户登录验证装饰器 (用户或管理员都可以访问)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 检查是否是用户
        if session.get("user"):
            return f(*args, **kwargs)
        # 检查是否是管理员
        if session.get("admin_logged_in"):
            return f(*args, **kwargs)
        # 都未登录，重定向到首页
        return redirect(url_for("landing"))
    return decorated_function

def user_required(f):
    """仅普通用户访问装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user"):
            return f(*args, **kwargs)
        # 管理员不能访问用户专用页面
        if session.get("admin_logged_in"):
            return redirect(url_for("admin_dashboard"))
        # 未登录
        return redirect(url_for("user_login"))
    return decorated_function

# 让Jinja模板可以检查管理员登录状态
app.jinja_env.globals.update(admin_logged_in=lambda: session.get("admin_logged_in", False))
app.jinja_env.globals.update(has_admin_users=has_admin_users)

# 让Jinja模板可以调用region函数
app.jinja_env.globals.update(get_cities=get_cities, get_districts=get_districts)

# 存储各用户会话的agent实例
_agents = {}


# ========== 管理员认证路由 ==========



@app.route("/register")
def unified_register():
    return render_template("register.html")


@app.route("/")
def landing():
    """首页 - 选择用户端/管理端"""
    return render_template("landing.html")

@app.route("/user/login", methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        from user_auth import verify_user

        # 检查是否是管理员用户名
        from admin_auth import _load_users as _load_admin_users
        admins = _load_admin_users()
        if any(u.get("username") == username for u in admins):
            return render_template("user_login.html",
                                  error="该账号为管理员账号，请从管理端登录")

        if verify_user(username, password):
            session["user"] = username
            return redirect("/home")
        return render_template("user_login.html", error="用户名或密码错误")
    return render_template("user_login.html")

@app.route("/user/register", methods=["GET", "POST"])
def user_register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")
        if password != password2:
            return render_template("user_register.html", error="两次密码不一致")
        from user_auth import register_user
        result = register_user(username, password)
        if result["success"]:
            return render_template("user_register.html", msg="注册成功！请登录")
        return render_template("user_register.html", error=result["error"])
    return render_template("user_register.html")

@app.route("/api/user/status")
def api_user_status():
    return jsonify({"logged_in": "user" in session, "username": session.get("user", "")})

@app.route("/user/logout")
def user_logout():
    session.pop("user", None)
    return redirect("/")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """管理员登录页（支持密码登录和短信验证码登录）"""
    error = ""
    if request.method == "POST":
        login_type = request.form.get("login_type", "password")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        sms_code = request.form.get("sms_code", "").strip()
        
        if login_type == "sms":
            # 短信验证码登录
            result = login_admin(username_or_phone=username, sms_code=sms_code)
        else:
            # 密码登录
            result = login_admin(username_or_phone=username, password=password)
        
        if result["success"]:
            session["admin_logged_in"] = True
            session["admin_user"] = result["user"]
            return redirect(url_for("admin_dashboard"))
        else:
            error = result.get("error", "登录失败")
    
    return render_template("admin_login.html", error=error,
                           has_users=has_admin_users())

@app.route("/admin/logout")
def admin_logout():
    """管理员退出"""
    session.pop("admin_logged_in", None)
    session.pop("admin_user", None)
    return redirect(url_for("index"))

@app.route("/admin/register", methods=["GET", "POST"])
def admin_register():
    """管理员注册页（用户名+密码，与用户端注册方式一致）"""
    error = ""
    success = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        password2 = request.form.get("password2", "").strip()
        if password != password2:
            error = "两次密码不一致"
        else:
            result = register_admin(username, password, "")
            if result["success"]:
                success = "注册成功！请使用您刚注册的账号登录"
            else:
                error = result.get("error", "注册失败")

    return render_template("admin_register.html", error=error, success=success,
                           has_users=has_admin_users())

@app.route("/api/admin/send_sms", methods=["POST"])
def admin_send_sms():
    """发送短信验证码（用于注册/登录）"""
    try:
        data = request.get_json()
        phone = data.get("phone", "").strip()
        if not phone or not validate_phone(phone):
            return jsonify({"success": False, "error": "请输入有效的手机号"})
        result = send_sms_code(phone)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/admin/check_username", methods=["POST"])
def admin_check_username():
    """检查用户名是否可用"""
    try:
        data = request.get_json()
        username = data.get("username", "").strip()
        if not username:
            return jsonify({"available": False})
        user = get_admin_user(username=username)
        return jsonify({"available": user is None})
    except Exception:
        return jsonify({"available": False})

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    """管理端面板（云端精简模式：只显示不依赖数据库的功能）"""
    if CLOUD_MODE:
        return render_template("admin_cloud.html")
    stats = {"patients": 0, "cases": 0, "consultations": 0}
    cases = []
    consultations = []
    try:
        import pymysql
        conn = pymysql.connect(host="localhost", port=3306, user="root",
                               password="123456", database="患者病历库", charset="utf8mb4")
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM learned_cases")
            stats["cases"] = cur.fetchone()[0] or 0
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM consultations")
            stats["consultations"] = cur.fetchone()[0] or 0
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM patients")
            stats["patients"] = cur.fetchone()[0] or 0
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("""SELECT id, case_text AS symptom, diagnosis, department AS dept,
                       severity, source, source_url, project_group,
                       symptoms_keywords AS keywords
                FROM learned_cases ORDER BY id DESC LIMIT 100""")
            cases = cur.fetchall()
            for r in cases:
                r["id"] = r["id"] or 0
                r["symptom"] = (r["symptom"] or "")[:200]
                r["diagnosis"] = r["diagnosis"] or ""
                r["dept"] = r["dept"] or "未知"
                r["severity"] = r["severity"] or "green"
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("""SELECT id, patient_id, symptom_text, department, diagnosis,
                       severity, triage_level, created_at
                FROM consultations ORDER BY created_at DESC LIMIT 50""")
            consultations = cur.fetchall()
            for r in consultations:
                r["created_at"] = str(r["created_at"])[:19] if r.get("created_at") else ""
                r["symptom_text"] = (r["symptom_text"] or "")[:100]
        conn.close()
    except Exception as e:
        print(f"[管理端] 加载数据出错: {e}")
    admin_user = session.get("admin_user", {})
    return render_template("admin_dashboard.html", stats=stats, cases=cases,
                           consultations=consultations, admin_user=admin_user,
                           admins=get_all_admins())

@app.route("/api/admin/cases")
@admin_required_api
def admin_api_cases():
    """管理端获取病例列表API"""
    try:
        search = request.args.get("search", "").strip()
        import pymysql
        conn = pymysql.connect(host="localhost", port=3306, user="root",
                               password="123456", database="患者病历库", charset="utf8mb4")
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            if search:
                cur.execute("""SELECT id, case_text AS symptom, diagnosis, department AS dept,
                       severity, source, source_url, project_group, symptoms_keywords AS keywords
                FROM learned_cases WHERE case_text LIKE %s OR diagnosis LIKE %s OR department LIKE %s
                ORDER BY id DESC LIMIT 2000""", (f"%{search}%", f"%{search}%", f"%{search}%"))
            else:
                cur.execute("""SELECT id, case_text AS symptom, diagnosis, department AS dept,
                       severity, source, source_url, project_group, symptoms_keywords AS keywords
                FROM learned_cases ORDER BY id DESC LIMIT 2000""")
            rows = cur.fetchall()
            for r in rows:
                r["id"] = r["id"] or 0
                r["symptom"] = (r["symptom"] or "")[:200]
                r["diagnosis"] = r["diagnosis"] or ""
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/case/delete", methods=["POST"])
@admin_required_api
def admin_delete_case():
    """管理端 - 删除病例（仅管理员）"""
    try:
        data = request.get_json()
        case_id = data.get("id", "")
        if not case_id:
            return jsonify({"success": False, "error": "缺少ID"})
        import pymysql
        conn = pymysql.connect(host="localhost", port=3306, user="root",
                               password="123456", database="患者病历库", charset="utf8mb4")
        with conn.cursor() as cur:
            cur.execute("DELETE FROM learned_cases WHERE id=%s", (int(case_id),))
            conn.commit()
            deleted = cur.rowcount
        conn.close()
        try:
            from vector_store import delete_case
            delete_case(int(case_id))
        except Exception:
            pass
        return jsonify({"success": True, "deleted": deleted})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/admin/consultation/delete", methods=["POST"])
@admin_required_api
def admin_delete_consultation():
    """管理端 - 删除咨询记录（仅管理员）"""
    try:
        data = request.get_json()
        cid = data.get("id", "")
        if not cid:
            return jsonify({"success": False, "error": "缺少ID"})
        import pymysql
        conn = pymysql.connect(host="localhost", port=3306, user="root",
                               password="123456", database="患者病历库", charset="utf8mb4")
        with conn.cursor() as cur:
            cur.execute("DELETE FROM consultations WHERE id=%s", (int(cid),))
            conn.commit()
            deleted = cur.rowcount
        conn.close()
        return jsonify({"success": True, "deleted": deleted})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/admin/patient/delete", methods=["POST"])
@admin_required_api
def admin_delete_patient():
    """管理端 - 删除患者记录（仅管理员）"""
    try:
        data = request.get_json()
        pid = data.get("patient_id", "")
        if not pid:
            return jsonify({"success": False, "error": "缺少患者ID"})
        import pymysql
        conn = pymysql.connect(host="localhost", port=3306, user="root",
                               password="123456", database="患者病历库", charset="utf8mb4")
        with conn.cursor() as cur:
            cur.execute("DELETE FROM consultations WHERE patient_id=%s", (pid,))
            cur.execute("DELETE FROM patients WHERE patient_id=%s", (pid,))
            conn.commit()
            deleted = cur.rowcount
        conn.close()
        return jsonify({"success": True, "deleted": deleted})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/admin/stats")
@admin_required_api
def admin_api_stats():
    """管理端统计数据API"""
    try:
        import pymysql
        conn = pymysql.connect(host="localhost", port=3306, user="root",
                               password="123456", database="患者病历库", charset="utf8mb4")
        stats = {}
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM learned_cases")
            stats["cases"] = cur.fetchone()[0] or 0
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM consultations")
            stats["consultations"] = cur.fetchone()[0] or 0
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM patients")
            stats["patients"] = cur.fetchone()[0] or 0
        conn.close()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500



def get_agent() -> MedicalConsultationAgent:
    """获取或创建当前会话的agent"""
    sid = session.get('session_id')
    if not sid:
        sid = str(uuid.uuid4())[:8]
        session['session_id'] = sid
    if sid not in _agents:
        _agents[sid] = MedicalConsultationAgent()
    return _agents[sid]


@app.route('/home')
@login_required
def index():
    """首页"""
    return render_template("index_template.html")


@app.route('/mobile')
def mobile():
    """移动端PWA页面"""
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'mobile.html'),
                     mimetype='text/html')


@app.route('/api/cases')
def api_cases():
    """获取病例数据（供前端调用）"""
    try:
        import pymysql
        conn = pymysql.connect(host="localhost", port=3306, user="root",
                               password="123456", database="患者病历库", charset="utf8mb4")
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("""
                SELECT id, case_text AS symptom, diagnosis, department AS dept,
                       severity, source, source_url,
                       symptoms_keywords AS keywords
                FROM learned_cases
                ORDER BY id DESC
            """)
            rows = cur.fetchall()
            for r in rows:
                r['id'] = r['id'] if r['id'] else 0
                r['symptom'] = (r['symptom'] or '')[:200]
                r['diagnosis'] = r['diagnosis'] or ''
                r['dept'] = r['dept'] or '未知'
                r['severity'] = r['severity'] or 'green'
                r['source'] = r['source'] or 'AI生成'
            conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/cities')
def api_cities():
    """API: 获取某省份的城市列表"""
    province = request.args.get('province', '')
    cities = get_cities(province)
    return jsonify(cities)


@app.route('/api/districts')
def api_districts():
    """API: 获取某城市的区县列表"""
    city = request.args.get('city', '')
    districts = get_districts(city)
    return jsonify(districts)


@app.route('/register', methods=['POST'])
def register():
    """提交患者信息，开始问诊"""
    surname = request.form.get('surname', '').strip()
    year = request.form.get('year', '')
    month = request.form.get('month', '')
    day = request.form.get('day', '')
    gender = request.form.get('gender', '')
    province = request.form.get('province', '')
    city = request.form.get('city', '')
    district = request.form.get('district', '')
    email = request.form.get('email', '').strip()

    # 验证
    if not all([surname, year, month, day, gender, province]):
        return redirect(url_for('index'))

    # 计算年龄
    y, m, d = int(year), int(month), int(day)
    today = datetime.now()
    age = today.year - y - ((today.month, today.day) < (m, d))

    location = format_location(province, city, district)
    dob_raw = f"{y}年{m}月{d}日"

    patient = {
        'surname': surname, 'age': age, 'gender': gender,
        'location': location, 'birth_date': dob_raw, 'email': email,
    }

    # 初始化问诊
    agent = get_agent()
    thread_id = session.get('thread_id')
    if not thread_id:
        thread_id = str(uuid.uuid4())[:8]
        session['thread_id'] = thread_id

    step1_out = agent.start_consultation(thread_id, patient)

    # 保存状态到session
    session['patient'] = patient
    session['step'] = agent.workflow.tracker.get_step(thread_id)

    return redirect(url_for('consult'))


@app.route('/chat')
@login_required
def chat_page():
    """对话式问诊页面"""
    session.pop('chat_history', None)
    session.pop('chat_report', None)
    return render_template('chat.html')


@app.route('/api/chat', methods=['POST'])
def chat_api():
    """对话式问诊API"""
    try:
        data = request.get_json()
        messages = data.get('messages', [])

        from chat_agent import chat, check_ready_for_report, clean_response
        reply = chat(messages)
        ready = check_ready_for_report(reply)
        clean = clean_response(reply)

        # 后端强制要求至少3轮用户输入后才允许出报告
        user_turns = sum(1 for m in messages if m.get("role") == "user")
        if user_turns < 3:
            ready = False

        # 保存对话历史到session
        session['chat_history'] = messages + [{"role": "assistant", "content": clean}]
        if ready:
            session['chat_ready'] = True

        return jsonify({"reply": clean, "ready": ready})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/chat/report')
def chat_report():
    """从对话生成诊断报告"""
    messages = session.get('chat_history', [])

    # 获取患者信息（如果有）
    patient = session.get('patient', {})
    if not patient:
        # 尝试从对话中提取
        patient = {"age": "", "gender": "", "location": ""}

    from chat_agent import generate_report_from_chat
    report_text = generate_report_from_chat(messages, patient)

    # 保存到session以便下载PDF
    session['report'] = report_text
    session['patient'] = patient

    return redirect(url_for('report'))


@app.route('/quick', methods=['GET', 'POST'])
@login_required
def quick_consult():
    """快速问诊页 - 填写+症状+一键出报告"""
    if request.method == 'POST':
        surname = request.form.get('surname', '').strip()
        year = request.form.get('year', '')
        month = request.form.get('month', '')
        day = request.form.get('day', '')
        gender = request.form.get('gender', '')
        province = request.form.get('province', '')
        city = request.form.get('city', '')
        district = request.form.get('district', '')
        email = request.form.get('email', '').strip()
        symptom = request.form.get('symptom', '').strip()

        if not all([surname, year, month, day, gender, province, symptom]):
            return redirect(url_for('quick_consult'))

        y, m, d = int(year), int(month), int(day)
        today = datetime.now()
        age = today.year - y - ((today.month, today.day) < (m, d))
        location = format_location(province, city, district)
        dob_raw = f"{y}年{m}月{d}日"

        patient = {
            'surname': surname, 'age': age, 'gender': gender,
            'location': location, 'birth_date': dob_raw, 'email': email,
        }

        agent = get_agent()
        thread_id = str(uuid.uuid4())[:8]
        session['thread_id'] = thread_id

        outputs = agent.full_consultation(patient, symptom)
        # 获取患者编号
        thread_data = agent.workflow.tracker.get_step_data(thread_id)
        patient_id = thread_data.get('patient_id', '001')
        patient['patient_id'] = patient_id
        session['patient'] = patient

        # 保存到MySQL
        try:
            from mysql_store import save_patient, save_consultation
            save_patient(patient_id, surname, gender, birth_date, age,
                         province, city, district,
                         thread_data.get('patient_location', ''),
                         email)
            # 查询报告文本用于保存
            report_text = ""
            for title, content in outputs:
                if '诊断报告' in title or '步骤4' in title:
                    report_text = content
                    break
            dept = thread_data.get('department', '')
            severity = thread_data.get('severity', {}).get('level', '')
            triage = thread_data.get('triage', '')
            keywords = '、'.join(thread_data.get('keywords', []))
            diagnosis = thread_data.get('diagnosis', '')
            disease_probs = thread_data.get('disease_probs', '')
            save_consultation(patient_id, symptom, keywords, dept,
                              severity, triage, diagnosis, disease_probs, report_text)
        except Exception as e:
            print(f"[MySQL] 保存失败: {e}")

        for title, content in outputs:
            if '诊断报告' in title or '步骤4' in title:
                session['report'] = content
                break
        session['step'] = agent.workflow.tracker.get_step(thread_id)
        return redirect(url_for('report'))

    provinces = get_provinces()
    return render_template('quick.html', provinces=provinces,
                           year_range=range(1900, 2026),
                           month_range=range(1, 13),
                           day_range=range(1, 32))


@app.route('/consult', methods=['GET', 'POST'])
@login_required
def consult():
    """问诊页面 - 处理5步流程"""
    agent = get_agent()
    thread_id = session.get('thread_id')
    patient = session.get('patient', {})
    step = agent.workflow.tracker.get_step(thread_id) if thread_id else 1

    if 'step2_complete' not in session:
        session['step2_complete'] = False

    message = session.pop('flash_message', '')

    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'symptom':
            # 步骤2: 提交症状描述
            symptom = request.form.get('symptom_text', '').strip()
            if symptom:
                out = agent.process_symptom(thread_id, symptom)
                step = agent.workflow.tracker.get_step(thread_id)
                session['step'] = step
                # 保存输出到session以便后续AJAX
                session['last_output'] = out
                session['checklist_mode'] = 'questions' if agent.workflow.tracker.get_step_data(thread_id).get('checklist_shown') else ''

        elif action == 'answer':
            # 步骤2: 逐题回答
            answer = request.form.get('answer_text', '').strip()
            if answer:
                out = agent.process_symptom(thread_id, answer)
                step = agent.workflow.tracker.get_step(thread_id)
                session['step'] = step
                session['last_output'] = out
                if step == 3:
                    session['step2_complete'] = True

        elif action == 'proceed_3':
            # 步骤3 → 自动完成步骤4，跳转到报告
            out_knowledge = agent.process_symptom(thread_id, session.get('symptom_text', ''))
            step = agent.workflow.tracker.get_step(thread_id)
            # 直接生成报告并跳转
            out_report = agent.generate_report(thread_id)
            step = agent.workflow.tracker.get_step(thread_id)
            session['step'] = step
            session['report'] = out_report
            session['last_output'] = out_knowledge
            return redirect(url_for('report'))

        elif action == 'proceed_4':
            # 步骤4: 生成报告
            out = agent.generate_report(thread_id)
            session['step'] = agent.workflow.tracker.get_step(thread_id)
            session['report'] = out
            return redirect(url_for('report'))

        # 重新获取step
        step = agent.workflow.tracker.get_step(thread_id) if thread_id else 1
        session['step'] = step

    # 获取当前步骤数据
    step_data = agent.workflow.tracker.get_step_data(thread_id) if thread_id else {}
    questions = step_data.get('questions', [])
    q_index = step_data.get('q_index', 0)
    checklist_shown = step_data.get('checklist_shown', False)
    last_output = session.pop('last_output', '')

    return render_template('consult.html',
                           patient=patient,
                           step=step,
                           step_names={1: '患者信息', 2: '症状问诊', 3: '知识查询', 4: '诊断报告', 5: '后续建议'},
                           progress=agent.workflow.tracker.get_progress(thread_id) if thread_id else '',
                           questions=questions,
                           q_index=q_index,
                           checklist_shown=checklist_shown,
                           step2_complete=session.get('step2_complete', False),
                           last_output=last_output,
                           message=message,
                           agent=agent,
                           thread_id=thread_id)


@app.route('/report')
@login_required
def report():
    """报告页"""
    agent = get_agent()
    thread_id = session.get('thread_id')
    patient = session.get('patient', {})
    report_text = session.get('report', '')

    if not report_text:
        return redirect(url_for('consult'))

    # 获取症状文本用于AI分析
    symptom_text = session.get('symptom_text', '')
    if not symptom_text:
        # 尝试从chat_history提取
        chat_history = session.get('chat_history', [])
        for msg in reversed(chat_history):
            if msg.get('role') == 'user':
                symptom_text = msg['content'][:200]
                break

    return render_template('report.html',
                           patient=patient,
                           report=report_text,
                           thread_id=thread_id,
                           symptom_text=symptom_text,
                           patient_json=patient)


@app.route('/download_pdf')
@login_required
def download_pdf():
    """下载PDF报告"""
    report_text = session.get('report', '')
    patient = session.get('patient', {})
    surname = patient.get('surname', '患者')
    gender = patient.get('gender', '')
    patient_id = patient.get('patient_id', '001')

    display_name = f"{surname}（{gender}）编号：{patient_id}"
    pdf_path = generate_pdf(report_text, display_name)

    return send_file(pdf_path, as_attachment=True,
                     mimetype='application/pdf',
                     download_name=f"report_{surname}_{patient_id}.pdf")


@app.route('/send_email', methods=['POST'])
def send_email():
    """发送报告到邮箱"""
    report_text = session.get('report', '')
    patient = session.get('patient', {})
    email = patient.get('email', '')

    if not email:
        return jsonify({'success': False, 'message': '未填写邮箱地址'})

    surname = patient.get('surname', '患者')
    gender = patient.get('gender', '')
    patient_id = patient.get('patient_id', '001')

    display_name = f"{surname}（{gender}）编号：{patient_id}"
    pdf_path = generate_pdf(report_text, display_name)

    # 获取系统 SMTP 配置
    smtp_config = get_smtp_config()
    sender_email = smtp_config.get('email', '')
    sender_password = smtp_config.get('password', '')

    success, msg = send_report_email(email, pdf_path, sender_email, sender_password)
    return jsonify({'success': success, 'message': msg})


@app.route('/records')
@login_required
def records():
    """病历中心页面（患者咨询记录）"""
    patients = []
    try:
        import pymysql
        from config_loader import get_db_conn_kwargs
        conn = pymysql.connect(**get_db_conn_kwargs())
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("""
                SELECT id, patient_id, symptom_text, department, severity,
                       triage_level, diagnosis, created_at
                FROM consultations
                ORDER BY created_at DESC LIMIT 200
            """)
            rows = cur.fetchall()
            # 按患者分组
            groups = {}
            for r in rows:
                pid = r['patient_id'] or '未知'
                if pid not in groups:
                    groups[pid] = {'patient_id': pid, 'consultations': []}
                groups[pid]['consultations'].append(r)
            for pid, g in groups.items():
                g['consult_count'] = len(g['consultations'])
                g['last_date'] = str(g['consultations'][0]['created_at'] or '')
            patients = list(groups.values())
        conn.close()
    except Exception as e:
        print(f"[病历] 错误: {e}")

    return render_template('records.html', patients=patients)


@app.route('/guide')
def guide():
    """使用说明页（用户端 + 管理端）"""
    return render_template('guide.html')


@app.route('/records/<patient_id>')
def patient_detail(patient_id):
    """患者详细问诊记录"""
    try:
        from mysql_store import get_patient_by_id, get_consultation_history
        patient = get_patient_by_id(patient_id)
        consultations = get_consultation_history(patient_id)
    except Exception:
        patient = {}
        consultations = []
    return render_template('patient_detail.html',
                           patient=patient,
                           consultations=consultations)


@app.route('/learning')
@login_required
def learning_center():
    """学习中心页面"""
    try:
        from self_learning import get_learning_stats
        stats = get_learning_stats()
    except Exception:
        stats = {"total": 0, "by_department": {}, "avg_usage": 0}

    # 获取学习历史记录
    history = []
    try:
        import pymysql, os
        reports_dir = os.path.join(os.path.expanduser("~"), "medical_reports")
        if os.path.exists(reports_dir):
            files = sorted([f for f in os.listdir(reports_dir) if f.startswith('learn_summary')], reverse=True)
            for f in files[:10]:
                with open(os.path.join(reports_dir, f), 'r', encoding='utf-8') as fh:
                    history.append({'file': f, 'content': fh.read()})
    except Exception:
        pass

    flash_msg = session.pop('flash_message', '')
    return render_template('learning.html', stats=stats, history=history, flash_msg=flash_msg)


@app.route('/learning/run', methods=['POST'])
def run_learning():
    """手动触发一次学习"""
    try:
        import subprocess, threading
        def _run():
            result = subprocess.run(
                ['python', 'self_learning.py'],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                capture_output=True, text=True, encoding='utf-8',
                timeout=120)
            # 保存输出到日志
            log_path = os.path.join(os.path.expanduser("~"), "medical_reports",
                                    f"learn_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(result.stdout or '')
                if result.stderr:
                    f.write('\n---STDERR---\n' + result.stderr)
        threading.Thread(target=_run, daemon=True).start()
        session['flash_message'] = "🚀 学习已启动！请等待30秒后点击「查看学习成果」查看结果。"
    except Exception as e:
        session['flash_message'] = f"启动失败: {e}"
    return redirect(url_for('learning_center'))


@app.route('/learning/history')
def learning_history():
    """学习历史记录页面"""
    logs = []
    try:
        import os
        reports_dir = os.path.join(os.path.expanduser("~"), "medical_reports")
        if os.path.exists(reports_dir):
            files = sorted([f for f in os.listdir(reports_dir)
                           if f.startswith('learn_run_') or f.startswith('learn_summary')],
                          reverse=True)
            for f in files[:20]:
                with open(os.path.join(reports_dir, f), 'r', encoding='utf-8') as fh:
                    content = fh.read()
                logs.append({'file': f, 'content': content, 'time': f[11:26]})
    except Exception:
        pass
    return render_template('learning_history.html', logs=logs)


@app.route('/api/consultations', methods=['GET', 'POST'])
def api_consultations():
    """咨询记录API：GET查询 / POST保存"""
    if request.method == 'GET':
        from mysql_store import get_consultations
        records = get_consultations(50)
        return jsonify(records)

    data = request.get_json()
    surname = data.get('surname', '在线')
    symptom = data.get('symptom', '')
    diagnosis = data.get('diagnosis', '')
    dept = data.get('dept', '')
    report = data.get('report', '')
    from mysql_store import save_consultation
    cid = save_consultation(surname, '咨询', symptom, diagnosis, dept, report)
    return jsonify({'success': cid is not None, 'id': cid})



@app.route("/api/report/ai_analysis", methods=["POST"])
def api_report_ai_analysis():
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        data = request.get_json()
        symptom_text = (data.get("symptom", "") or "").strip()
        patient_info = data.get("patient", {})
        if not symptom_text:
            return jsonify({"success": False, "error": "缺少症状描述"})
        info_str = ""
        if patient_info:
            age = patient_info.get("age", "")
            gender = patient_info.get("gender", "")
            location = patient_info.get("location", "")
            if age or gender:
                info_str = f"{age}岁{gender}"
            if location:
                info_str += f"，所在地{location}"
        from ai_glm_agent import ai_analyze_symptoms
        result = ai_analyze_symptoms(symptom_text, info_str)
        if "error" in result:
            return jsonify({"success": False, "error": result["error"]})
        analysis = result.get("analysis", {})
        diseases = result.get("diseases", [])
        knowledge = result.get("knowledge", {})
        return jsonify({
            "success": True,
            "data": {
                "department": analysis.get("department", "内科"),
                "severity": analysis.get("severity", "green"),
                "triage": analysis.get("triage", "二级医院"),
                "diagnosis": analysis.get("diagnosis", "建议进一步检查"),
                "diseases": [{"name": d.get("name", "未知"), "probability": d.get("probability", 0),
                              "department": d.get("department", "")} for d in diseases[:5]],
                "knowledge": {
                    "possible_causes": knowledge.get("possible_causes", [])[:5],
                    "red_flags": knowledge.get("red_flags", [])[:3],
                    "suggested_exams": knowledge.get("suggested_exams", [])[:5],
                    "advice": knowledge.get("advice", "")
                },
                "keywords": analysis.get("keywords", result.get("keywords", []))
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/admin/vector/sync', methods=['POST'])
@admin_required_api
def admin_vector_sync():
    """同步MySQL病例到向量库"""
    from vector_store import sync_from_mysql
    result = sync_from_mysql()
    return jsonify(result)

@app.route('/api/admin/vector/clear', methods=['POST'])
@admin_required_api
def admin_vector_clear():
    """清空向量库"""
    from vector_store import clear_all
    ok = clear_all()
    return jsonify({"success": ok})

@app.route('/api/admin/vector/stats')
@admin_required_api
def admin_vector_stats():
    """向量库统计"""
    from vector_store import count_cases
    return jsonify({"count": count_cases()})


@app.route('/api/admin/vector/search', methods=['POST'])
@admin_required_api
def admin_vector_search():
    """管理端向量语义搜索"""
    try:
        data = request.get_json()
        query = (data or {}).get("query", "").strip()
        if not query:
            return jsonify({"success": False, "error": "请输入查询"})
        from vector_store import search_similar
        results = search_similar(query, limit=5)
        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/vector/search', methods=['POST'])
def public_vector_search():
    """向量语义搜索测试"""
    try:
        data = request.get_json()
        query = data.get("query", "").strip()
        if not query:
            return jsonify({"success": False, "error": "请输入查询"})
        from vector_store import search_similar
        results = search_similar(query, limit=5)
        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/case/<int:case_id>')
@login_required
def case_detail(case_id):
    """向量搜索结果 → 病例详情页（用户端/管理端共用）"""
    case = None
    error = None
    try:
        import json
        from config_loader import get_db_conn_kwargs
        import pymysql
        conn = pymysql.connect(**get_db_conn_kwargs())
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT * FROM learned_cases WHERE id=%s", (case_id,))
            case = cur.fetchone()
        conn.close()
        if not case:
            error = "未找到该病例（可能已被删除）"
        else:
            # 预解析 JSON 字段（模板无需自定义过滤器）
            if case.get("disease_probs"):
                try:
                    case["disease_probs"] = json.loads(case["disease_probs"])
                except Exception:
                    case["disease_probs"] = None
    except Exception as e:
        error = f"查询失败：{str(e)[:80]}"
    return render_template("case_detail.html", case=case, error=error)


@app.route('/api/export/word', methods=['POST'])
@login_required
def export_word():
    """AI 诊断报告导出为 Word (.docx)"""
    try:
        from docx import Document
        from docx.shared import Pt
        from datetime import datetime
        data = request.get_json() or {}
        text = (data.get("report") or "").strip()
        if not text:
            return jsonify({"error": "无报告内容"}), 400

        doc = Document()
        style = doc.styles["Normal"]
        style.font.name = "微软雅黑"
        style.font.size = Pt(11)
        for line in text.splitlines():
            if line.strip().startswith("=") or line.strip().startswith("-"):
                continue  # 跳过装饰线
            p = doc.add_paragraph(line)
            if line.strip().startswith("AI") and "诊断报告" in line:
                for run in p.runs:
                    run.font.size = Pt(16)
                    run.bold = True
        import io
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        fname = f"AI诊断报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        return send_file(buf, as_attachment=True, download_name=fname,
                         mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """SMTP 邮箱配置页"""
    if request.method == 'POST':
        smtp_email = request.form.get('smtp_email', '').strip()
        smtp_password = request.form.get('smtp_password', '').strip()
        if smtp_email:
            save_smtp_config({'email': smtp_email, 'password': smtp_password})
            return render_template('settings.html', saved=True,
                                   smtp_email=smtp_email)
    smtp_config = get_smtp_config()
    return render_template('settings.html', saved=False,
                           smtp_email=smtp_config.get('email', ''))


# ========== SMTP 配置持久化 ==========

def get_smtp_config() -> dict:
    """获取 SMTP 配置"""
    try:
        from memory import get_memory_manager
        config = get_memory_manager().get('system', 'smtp_config')
        return config or {}
    except Exception:
        return {}


def save_smtp_config(config: dict):
    """保存 SMTP 配置"""
    from memory import get_memory_manager
    get_memory_manager().put('system', 'smtp_config', config)


@app.route('/admin/health')
@admin_required
def admin_health():
    """系统健康检查页面"""
    status = {"services": {}, "overall": "ok"}

    # MySQL检查
    try:
        import pymysql
        from config_loader import get_db_conn_kwargs
        conn = pymysql.connect(**get_db_conn_kwargs())
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM learned_cases")
            case_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM consultations")
            consult_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM patients")
            patient_count = cur.fetchone()[0]
        conn.close()
        status["services"]["mysql"] = {"status": "ok", "cases": case_count, "consultations": consult_count, "patients": patient_count}
    except Exception as e:
        status["services"]["mysql"] = {"status": "error", "message": str(e)[:100]}
        status["overall"] = "error"

    # ChromaDB检查
    try:
        from vector_store import count_cases
        vcount = count_cases()
        status["services"]["chromadb"] = {"status": "ok", "vectors": vcount}
    except Exception as e:
        status["services"]["chromadb"] = {"status": "error", "message": str(e)[:100]}

    # DeepSeek API检查
    try:
        from openai import OpenAI
        from config_loader import ZHIPUAI_API_KEY, ZHIPUAI_API_BASE, ZHIPUAI_MODEL
        if ZHIPUAI_API_KEY:
            client = OpenAI(api_key=ZHIPUAI_API_KEY, base_url=ZHIPUAI_API_BASE)
            resp = client.chat.completions.create(
                model=ZHIPUAI_MODEL,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5
            )
            status["services"]["qwen"] = {"status": "ok", "model": ZHIPUAI_MODEL}
        else:
            status["services"]["qwen"] = {"status": "warning", "message": "API Key未配置"}
    except Exception as e:
        status["services"]["qwen"] = {"status": "error", "message": str(e)[:100]}

    # 管理员检查
    from admin_auth import has_admin_users, get_all_admins
    status["services"]["admin"] = {
        "status": "ok",
        "has_users": has_admin_users(),
        "user_count": len(get_all_admins())
    }

    import config_loader
    return render_template("admin_health.html", status=status, config_loader=config_loader)



import csv
import io

@app.route("/api/admin/export/cases")
@admin_required_api
def admin_export_cases_csv():
    """导出病例为CSV"""
    import pymysql
    from config_loader import get_db_conn_kwargs
    try:
        conn = pymysql.connect(**get_db_conn_kwargs())
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT id, case_text, symptoms_keywords, department, severity, diagnosis, disease_probs, source, year, month, project_group, source_url FROM learned_cases ORDER BY id")
            rows = cur.fetchall()
        conn.close()
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(["ID", "症状", "关键词", "科室", "严重度", "诊断", "来源", "年份", "月份", "项目组"])
        for r in rows:
            cw.writerow([r["id"], r["case_text"], r["symptoms_keywords"], r["department"], r["severity"], r["diagnosis"], r["source"], r["year"], r["month"], r["project_group"]])
        output = si.getvalue().encode("utf-8-sig")
        return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=medical_cases.csv"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/export/consultations")
@admin_required_api
def admin_export_consultations_csv():
    """导出咨询记录为CSV"""
    import pymysql
    from config_loader import get_db_conn_kwargs
    try:
        conn = pymysql.connect(**get_db_conn_kwargs())
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT id, patient_id, symptom_text, department, diagnosis, severity, triage_level, created_at FROM consultations ORDER BY created_at DESC")
            rows = cur.fetchall()
        conn.close()
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(["ID", "患者ID", "症状", "科室", "诊断", "严重度", "分诊", "时间"])
        for r in rows:
            cw.writerow([r["id"], r["patient_id"], r["symptom_text"], r["department"], r["diagnosis"], r["severity"], r["triage_level"], str(r["created_at"])[:19]])
        output = si.getvalue().encode("utf-8-sig")
        return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=consultations.csv"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health_tips')
def public_health_tips():
    from datetime import datetime
    from health_tips import get_stats, get_tips
    page = request.args.get('page', 1, type=int)
    per_page = 10
    stats = get_stats()
    all_tips = get_tips(limit=500)
    total = len(all_tips)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    tips = all_tips[start:end]
    for t in tips:
        if isinstance(t.get('created_at'), datetime):
            t['created_at'] = t['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        elif t.get('created_at') is None:
            t['created_at'] = ''
    return render_template('health_tips.html', tips=tips, stats=stats, page=page, total_pages=total_pages, total=total)

@app.route('/api/health_tips/list')
def api_health_tips_list():
    from health_tips import get_tips
    page = request.args.get('page', 1, type=int)
    per_page = 10
    all_tips = get_tips(limit=500)
    total = len(all_tips)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    tips = all_tips[start:start+per_page]
    for t in tips:
        t['created_at'] = str(t['created_at'])[:19] if t.get('created_at') else ''
    return jsonify({'tips': tips, 'page': page, 'total_pages': total_pages, 'total': total})


# ========== 健康养生建议 ==========
import threading

_health_tips_scheduler = None

def start_case_learning_scheduler():
    """启动定时任务：每天12:00爬取350条病例"""
    import schedule
    import time
    from self_learning import run_learning_cycle

    def job():
        with app.app_context():
            try:
                print("[病例学习] 12:00 开始爬取350条病例...")
                result = run_learning_cycle(target_count=350)
                print(f"[病例学习] 完成: {result}")
            except Exception as e:
                print(f"[病例学习] 失败: {e}")

    schedule.every().day.at("12:00").do(job)
    print("[病例学习] 定时任务已注册：每天12:00爬取350条")

    while True:
        schedule.run_pending()
        time.sleep(60)

def init_case_learning_scheduler():
    """初始化病例学习定时器（非阻塞）"""
    try:
        t = threading.Thread(target=start_case_learning_scheduler, daemon=True)
        t.start()
        return True
    except Exception as e:
        print(f"[病例学习] 调度器启动失败: {e}")
        return False

def start_health_tips_scheduler():
    """启动定时任务：每天18:00生成健康建议"""
    import schedule
    from health_tips import run_daily_task
    
    def job():
        with app.app_context():
            from health_tips import run_daily_task
            result = run_daily_task()
    # 启动时立即执行一次（如果是18点后）
    from datetime import datetime
    now = datetime.now()
    if now.hour >= 18:
        threading.Thread(target=job, daemon=True).start()
    
    while True:
        schedule.run_pending()
        time.sleep(60)

def init_health_tips_scheduler():
    """初始化定时器（非阻塞）"""
    try:
        t = threading.Thread(target=start_health_tips_scheduler, daemon=True)
        t.start()
        return True
    except Exception as e:
        print(f"[健康建议] 调度器启动失败: {e}")
        return False


@app.route("/api/admin/health_tips/dedup", methods=["POST"])
@admin_required_api
def admin_dedup_tips():
    from health_tips import dedup_all
    result = dedup_all()
    return jsonify({"success": True, "results": result})

@app.route("/api/admin/health_tips/summarize", methods=["POST"])
@admin_required_api
def admin_summarize_tips():
    from summary_ai import summarize_all
    result = summarize_all()
    return jsonify({"success": True, "results": result})

@app.route("/api/admin/health_tips/run", methods=["POST"])
@admin_required_api
def admin_run_health_tips():
    """手动触发一次健康建议生成"""
    from health_tips import run_daily_task
    result = run_daily_task()
    return jsonify(result)

@app.route("/api/admin/health_tips/stats")
@admin_required_api
def admin_health_tips_stats():
    """健康建议统计"""
    from health_tips import get_stats, get_tips
    stats = get_stats()
    recent = get_tips(limit=10)
    for r in recent:
        r["created_at"] = str(r["created_at"])[:19]
    return jsonify({"stats": stats, "recent": recent})


@app.route('/reset')
def reset():
    """重置会话，重新开始"""
    sid = session.get('session_id')
    if sid and sid in _agents:
        del _agents[sid]
    session.clear()
    return redirect(url_for('index'))



if __name__ == '__main__':
    # 启动健康建议定时器
    try:
        init_health_tips_scheduler()
    except Exception:
        pass
        # ====== 启动病例学习定时器 ======
    try:
        init_case_learning_scheduler()
    except Exception:
        pass
    app.run(debug=True, host='0.0.0.0', port=5000)
