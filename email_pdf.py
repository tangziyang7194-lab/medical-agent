"""
PDF报告生成 & 邮件发送模块
支持国内外主流邮箱：QQ、163、126、Gmail、Outlook、Yahoo、iCloud等
"""

from fpdf import FPDF
import os
import sys
import smtplib
import re
import warnings
from contextlib import redirect_stderr, nullcontext
from io import StringIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

# 屏蔽 PDF 字体警告
warnings.filterwarnings("ignore", message=".*subset.*")


def _quiet_pdf():
    """临时屏蔽 PDF 库的 stderr 输出"""
    return redirect_stderr(StringIO())


# ========== 邮箱域名白名单 ==========

VALID_EMAIL_DOMAINS = [
    # 国内主流
    "qq.com", "foxmail.com", "163.com", "126.com", "yeah.net",
    "sina.com", "sina.cn", "sohu.com", "139.com", "189.com",
    "wo.cn", "tom.com", "21cn.com", "aliyun.com",
    # 企业邮箱
    "corp.qq.com", "exmail.qq.com",
    # 国际主流
    "gmail.com", "outlook.com", "hotmail.com", "live.com",
    "yahoo.com", "yahoo.co.jp", "ymail.com", "rocketmail.com",
    "icloud.com", "me.com", "mac.com",
    "aol.com", "mail.com", "protonmail.com", "proton.me",
    "zoho.com", "yandex.com", "fastmail.com", "tutanota.com",
    # 教育
    "edu.cn", "edu.hk", "edu.tw", "ac.cn",
    # 常见其他国家
    "naver.com", "daum.net", "hanmail.net",
    "rediffmail.com", "disroot.org",
]

# ========== SMTP 配置 ==========

SMTP_CONFIGS = {
    "qq.com":      {"server": "smtp.qq.com",      "port": 465, "ssl": True},
    "foxmail.com": {"server": "smtp.qq.com",      "port": 465, "ssl": True},
    "163.com":     {"server": "smtp.163.com",     "port": 465, "ssl": True},
    "126.com":     {"server": "smtp.126.com",     "port": 465, "ssl": True},
    "gmail.com":   {"server": "smtp.gmail.com",   "port": 587, "ssl": False},
    "outlook.com": {"server": "smtp.office365.com","port": 587, "ssl": False},
    "hotmail.com": {"server": "smtp.office365.com","port": 587, "ssl": False},
    "live.com":    {"server": "smtp.office365.com","port": 587, "ssl": False},
    "yahoo.com":   {"server": "smtp.mail.yahoo.com","port": 587, "ssl": False},
    "icloud.com":  {"server": "smtp.mail.me.com",  "port": 587, "ssl": False},
}


def validate_email(email: str) -> tuple:
    """
    验证邮箱格式和域名
    返回: (是否合法, 提示信息)
    """
    email = email.strip().lower()
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "邮箱格式不正确（示例: name@qq.com）"

    domain = email.split('@')[1]
    # 检查主域名
    main_domain = domain
    for valid in VALID_EMAIL_DOMAINS:
        if domain == valid or domain.endswith('.' + valid):
            main_domain = valid
            break
    else:
        return False, f"暂不支持 {domain} 邮箱，请使用 QQ/163/Gmail/Outlook 等主流邮箱"

    return True, main_domain


def get_email_provider_name(email: str) -> str:
    """获取邮箱提供商名称"""
    domain = email.split('@')[1]
    provider_map = {
        "qq.com": "QQ邮箱", "foxmail.com": "Foxmail",
        "163.com": "163邮箱", "126.com": "126邮箱",
        "gmail.com": "Gmail", "outlook.com": "Outlook",
        "hotmail.com": "Hotmail", "live.com": "Live",
        "yahoo.com": "Yahoo邮箱", "icloud.com": "iCloud",
        "sina.com": "新浪邮箱", "sohu.com": "搜狐邮箱",
        "139.com": "139邮箱", "189.com": "189邮箱",
        "aliyun.com": "阿里云邮箱",
    }
    for key, name in provider_map.items():
        if key in domain:
            return name
    return domain


# ========== PDF 报告生成 ==========

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 注册中文字体（只执行一次）
_CN_FONT_REGISTERED = False
_CN_FONT_NAME = "SimSun"


def _ensure_cn_font():
    """注册中文字体（只执行一次）"""
    global _CN_FONT_REGISTERED, _CN_FONT_NAME
    if _CN_FONT_REGISTERED:
        return True
    paths = [
        r'C:\Windows\Fonts\simsun.ttc',
        r'C:\Windows\Fonts\msyh.ttc',
        r'C:\Windows\Fonts\simhei.ttf',
    ]
    for fp in paths:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont('SimSun', fp))
                _CN_FONT_REGISTERED = True
                return True
            except Exception:
                continue
    _CN_FONT_NAME = "Helvetica"  # fallback
    return False


_ensure_cn_font()


def strip_emojis(text: str) -> str:
    """去除文本中的 emoji 字符，保留中文"""
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F"  # 表情符号
        "\U0001F300-\U0001F5FF"  # 符号和象形文字
        "\U0001F680-\U0001F6FF"  # 交通
        "\U0001F1E0-\U0001F1FF"  # 国旗
        "\U0001F900-\U0001F9FF"  # 补充符号
        "\U0001FA00-\U0001FA6F"  # 象棋
        "\U0001FA70-\U0001FAFF"  # 象形扩展
        "\U00002702-\U000027B0"  # 杂项符号
        "\U0001F7E0-\U0001F7FF"  # 彩色圆形
        "\U00002600-\U000026FF"  # 杂项符号
        "\U00002700-\U000027BF"  # 丁字符
        "\U0000FE00-\U0000FE0F"  # 变体选择符
        "\U0000200D"             # 零宽连接符
        "\U000020E3"             # 键帽
        "\U00002B50-\U00002B55"
        "\U00002300-\U000023FF"
        "\U00002500-\U000025FF"
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub('', text).strip()


def generate_pdf(report_text: str, patient_name: str, output_path: str = "") -> str:
    """生成PDF报告文件（使用reportlab，更快）"""
    if not output_path:
        reports_dir = os.path.join(os.path.expanduser("~"), "medical_reports")
        os.makedirs(reports_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '_', patient_name)
        output_path = os.path.join(reports_dir, f"report_{safe_name}_{timestamp}.pdf")

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()

    cn_style = ParagraphStyle(
        'ChineseStyle',
        parent=styles['Normal'],
        fontName=_CN_FONT_NAME,
        fontSize=10,
        leading=15,
        spaceAfter=2,
    )
    bold_style = ParagraphStyle(
        'BoldStyle',
        parent=cn_style,
        fontSize=11,
        spaceBefore=4,
    )
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=cn_style,
        fontSize=16,
        alignment=1,  # center
        spaceAfter=10,
    )

    elements = []

    # 标题
    clean_name = strip_emojis(patient_name)
    elements.append(Paragraph("AI 医疗诊断报告", title_style))
    elements.append(Paragraph(f"患者: {clean_name}", cn_style))
    elements.append(Spacer(1, 3))

    # 蓝色分隔线
    elements.append(HRFlowable(width="100%", thickness=1,
                                color=HexColor("#1a73e8"), spaceAfter=6))

    # 解析报告文本
    lines = report_text.split('\n')
    for line in lines:
        s = strip_emojis(line.strip())
        if not s:
            elements.append(Spacer(1, 2))
            continue
        if s.startswith('=') or s.startswith('-'):
            elements.append(HRFlowable(width="100%", thickness=0.3,
                                        color=HexColor("#cccccc"), spaceAfter=3))
            continue
        # 关键字段加粗（bold_style已加粗整段，不需要额外替换标签）
        if any(kw in s for kw in ['科室:', '严重度:', '等级:', '主诉:', '诊断:', '建议:', '处理:']):
            elements.append(Paragraph(s, bold_style))
        else:
            elements.append(Paragraph(s, cn_style))

    # 免责声明
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=0.5,
                                color=HexColor("#cc0000"), spaceAfter=4))
    elements.append(Paragraph(
        "免责声明: 本报告由AI导诊系统自动生成, 仅供参考, 不构成医疗诊断。"
        "具体诊疗方案请咨询线下执业医师。如有紧急情况请立即拨打120。",
        ParagraphStyle('Disclaimer', parent=cn_style, fontSize=8, textColor=HexColor("#666666"))
    ))
    gen_time = strip_emojis(f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    elements.append(Paragraph(gen_time, ParagraphStyle('Time', parent=cn_style, fontSize=8)))

    doc.build(elements)
    return output_path


# ========== 邮件发送 ==========

def send_report_email(recipient_email: str, pdf_path: str,
                       sender_email: str = "", sender_password: str = "") -> tuple:
    """
    发送报告到患者邮箱
    返回: (是否成功, 提示信息)
    """
    # 如果未配置发件账户，返回提示
    if not sender_email or not sender_password:
        return False, (
            f"📧 报告已保存至: {pdf_path}\n"
            f"   如需自动发送到 {recipient_email}，请在系统配置SMTP发件账户。\n"
            f"   或手动将PDF文件发送给患者。"
        )

    try:
        domain = recipient_email.split('@')[1]
        smtp_cfg = None
        for key, cfg in SMTP_CONFIGS.items():
            if key in domain:
                smtp_cfg = cfg
                break

        if not smtp_cfg:
            return False, f"暂不支持 {domain} 邮箱的自动发送"

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f'AI医疗导诊报告 - {datetime.now().strftime("%Y-%m-%d")}'

        body = MIMEText(
            '您好，\n\n'
            '附件是您的AI医疗导诊报告，由系统自动生成。\n'
            '本报告仅供参考，不构成医疗诊断。\n'
            '如有紧急情况请立即拨打120。\n\n'
            '祝您健康！\nAI导诊系统',
            'plain', 'utf-8'
        )
        msg.attach(body)

        with open(pdf_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{os.path.basename(pdf_path)}"'
            )
            msg.attach(part)

        if smtp_cfg['ssl']:
            server = smtplib.SMTP_SSL(smtp_cfg['server'], smtp_cfg['port'])
        else:
            server = smtplib.SMTP(smtp_cfg['server'], smtp_cfg['port'])
            server.starttls()

        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()

        return True, f"✅ 报告已成功发送至 {recipient_email}"

    except Exception as e:
        return False, (
            f"⚠️ 邮件发送失败: {str(e)}\n"
            f"📧 报告已保存至: {pdf_path}\n"
            f"   请手动将PDF文件发送给患者。"
        )
