"""
MySQL 患者咨询记录 API
"""
import pymysql
from datetime import datetime

DB_CFG = {"host":"localhost","port":3306,"user":"root","password":"123456",
          "database":"患者病历库","charset":"utf8mb4"}


def save_consultation(surname, gender, symptom, diagnosis, dept, report):
    """保存咨询记录到MySQL patients表"""
    try:
        conn = pymysql.connect(**DB_CFG)
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO consultations
                   (patient_id, symptom_text, keywords, department, severity, triage_level, diagnosis, report)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (f"W{datetime.now().strftime('%Y%m%d%H%M%S')}", symptom, "",
                 dept, "green", "二级医院", diagnosis, report)
            )
            conn.commit()
            last_id = cur.lastrowid
        conn.close()
        return last_id
    except Exception as e:
        print(f"[MySQL] 保存咨询失败: {e}")
        return None


def get_consultations(limit=50):
    """获取咨询记录列表"""
    try:
        conn = pymysql.connect(**DB_CFG)
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT id, patient_id, symptom_text, department, diagnosis, report, created_at "
                "FROM consultations ORDER BY created_at DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
            for r in rows:
                r['created_at'] = str(r['created_at']) if r['created_at'] else ''
                r['symptom_text'] = (r['symptom_text'] or '')[:100]
                r['diagnosis'] = r['diagnosis'] or ''
                r['department'] = r['department'] or ''
                r['report'] = (r['report'] or '')[:200]
        conn.close()
        return rows
    except Exception as e:
        print(f"[MySQL] 查询咨询失败: {e}")
        return []
