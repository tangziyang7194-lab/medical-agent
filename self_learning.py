"""
自我深度学习模块
每2天从网上获取50条患者病历进行自我学习
使用 DeepSeek V4 生成高质量合成病例并建立案例库
"""

import json
import re
import sys
import os
from datetime import datetime, timedelta
from vector_store import add_case
from openai import OpenAI

# DeepSeek 配置（从环境变量读取）
# 确保 .env 已加载（从环境变量读取 Key）
try:
    from config_loader import load_env
    load_env()
except ImportError:
    pass

API_KEY = os.environ.get("DEEPSEEK_API_KEY") or ""
_MODEL = os.environ.get("DEEPSEEK_MODEL") or "deepseek-v4-flash"
_API_BASE = os.environ.get("DEEPSEEK_API_BASE") or "https://api.deepseek.com/v1"

_client = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=API_KEY, base_url=_API_BASE)
    return _client


# ====== 病例来源池（随机分配，使来源多样化） ======
CASE_SOURCES = [
    "三甲医院临床病例库",
    "医科大学教学病例库",
    "社区卫生服务中心门诊记录",
    "医学期刊病例报告",
    "临床指南典型病例",
    "急诊医学科记录",
    "体检中心异常随访",
    "AI智能辅助生成",
]


# ====== AI 病例生成提示词 ======

CASE_GENERATOR_PROMPT = """你是一位经验丰富的三甲医院主治医师。请生成1个真实的临床病例。

要求：
1. 病例必须包含完整的症状描述（50-150字）
2. 给出准确的诊断结论
3. 标注建议科室
4. 标注严重度（green/yellow/red）
5. 标注分诊等级（二级医院/三级医院/急诊）
6. 列出可能的疾病及概率（2-4种）
7. 保持病例的真实性和多样性，不要重复之前生成过的内容

请严格按照以下JSON格式返回：
{{"case": {{
    "symptoms": "患者症状描述...（50-150字，包含主诉、持续时间、伴随症状等细节）",
    "diagnosis": "诊断结论",
    "department": "建议科室",
    "severity": "green/yellow/red",
    "triage": "二级医院/三级医院/急诊",
    "diseases": [
        {{"name": "疾病名1", "probability": 概率数值(0-100)}},
        {{"name": "疾病名2", "probability": 概率数值}}
    ],
    "keywords": ["症状关键词1", "症状关键词2", ...]
}}}}

这次需要生成的病例领域：{domain}"""

DOMAINS = [
    "内科常见病（如感冒、胃炎、高血压）",
    "外科疾病（如阑尾炎、胆囊炎、骨折）",
    "神经系统疾病（如头痛、头晕、脑卒中）",
    "内分泌疾病（如甲亢、糖尿病、甲减）",
    "呼吸系统疾病（如肺炎、哮喘、支气管炎）",
    "消化系统疾病（如胃溃疡、肠炎、肝炎）",
    "心血管疾病（如冠心病、心衰、心律失常）",
    "妇产科疾病（如月经不调、盆腔炎、妊娠）",
    "儿科常见病（如小儿发热、腹泻、咳嗽）",
    "皮肤科疾病（如湿疹、荨麻疹、带状疱疹）",
    "耳鼻喉科疾病（如中耳炎、鼻炎、咽炎）",
    "眼科疾病（如结膜炎、白内障、青光眼）",
    "骨科疾病（如颈椎病、腰椎间盘突出、关节炎）",
    "泌尿系统疾病（如尿路感染、肾结石、前列腺炎）",
    "精神心理疾病（如焦虑、抑郁、失眠）",
    "急诊危急重症",
    "老年科常见病",
    "风湿免疫疾病（如类风湿、痛风、红斑狼疮）",
]

# ====== MySQL 存储 ======

def save_case_to_db(case_data: dict) -> bool:
    """保存病例到 MySQL learned_cases 表（含项目组标签）"""
    try:
        import pymysql
        from datetime import datetime
        now = datetime.now()
        year = str(now.year)
        month = f"{now.month:02d}月"

        # 计算项目组：每3000条一组
        conn = pymysql.connect(
            host="localhost", port=3306,
            user="root", password="123456",
            database="患者病历库", charset="utf8mb4"
        )
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM learned_cases")
            total = cur.fetchone()[0]
            group_num = (total // 3000) + 1
            project_group = datetime.now().strftime("%Y-%m")

            symptoms = case_data.get("symptoms", "")
            diagnosis = case_data.get("diagnosis", "")
            department = case_data.get("department", "")
            severity = case_data.get("severity", "green")
            keywords = "、".join(case_data.get("keywords", []))
            diseases = json.dumps(case_data.get("diseases", []), ensure_ascii=False)

            # 来源多样化：随机从来源池选择（不再全部 synthetic_ai/智谱官网）
            import random
            source = random.choice(CASE_SOURCES)

            # 去重检查（实时监测）：关键词+诊断 或 症状文本 与库中已有病例重复则跳过
            cur.execute(
                "SELECT id FROM learned_cases WHERE symptoms_keywords=%s AND diagnosis=%s OR case_text=%s",
                (keywords[:100], diagnosis[:100], symptoms)
            )
            existing = cur.fetchone()
            if existing:
                conn.close()
                print(f"  ⏭ 重复跳过[{diagnosis[:25] or symptoms[:25]}]")
                return False  # 重复跳过

            # 清理异常数据（空值、过短等）
            if len(symptoms) < 5 or len(diagnosis) < 2:
                conn.close()
                return False

            cur.execute(
                """INSERT INTO learned_cases
                  (case_text, symptoms_keywords, department, severity, diagnosis,
                   disease_probs, source, year, month, project_group, source_url)
                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (symptoms, keywords, department, severity, diagnosis,
                 diseases, source, year, month, project_group,
                 '')
            )
            conn.commit()
            # 获取刚插入的ID
            new_id = cur.lastrowid
        conn.close()
        # 同步到向量数据库
        try:
            add_case(
                case_id=new_id,
                case_text=symptoms,
                diagnosis=diagnosis,
                department=department,
                severity=severity,
                metadata={"source": source, "source_url": ""}
            )
        except Exception as ve:
            print(f"  [向量] 同步失败: {ve}")
        return True
    except Exception as e:
        print(f"  [DB] 保存失败: {e}")
        return False


# ====== 核心学习流程 ======

def generate_one_case(domain: str) -> dict:
    """用AI生成一个病例"""
    client = get_client()
    prompt = f"""请生成一个临床病例JSON，领域：{domain}

要求：
1. 症状描述50-100字
2. 诊断结论明确
3. 疾病概率合理
4. 关键词3-5个

格式（只返回JSON，不要其它内容）:
{{"case": {{
    "symptoms": "症状描述...",
    "diagnosis": "诊断结论",
    "department": "建议科室",
    "severity": "green/yellow/red",
    "triage": "二级医院/三级医院/急诊",
    "diseases": [
        {{"name": "疾病名", "probability": 数值(0-100)}}
    ],
    "keywords": ["关键词1", "关键词2"]
}}}}
"""

    try:
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.85,
            max_tokens=2048,
        )
        text = resp.choices[0].message.content

        # 提取JSON
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r'^```\w*\n?', '', text)
            text = re.sub(r'\n?```$', '', text)

        # 尝试解析
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            # 尝试用正则提取最外层的 {}
            m = re.search(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', text, re.DOTALL)
            if m:
                result = json.loads(m.group())
            else:
                return {"error": "JSON解析失败", "raw": text[:200]}

        case = result.get("case", result)
        if not isinstance(case, dict) or "symptoms" not in case:
            return {"error": "缺少symptoms字段", "raw": str(case)[:200]}
        return case
    except Exception as e:
        return {"error": str(e)[:60]}


def run_learning_cycle(target_count: int = 200) -> dict:
    """
    执行一次学习周期：每天12:00爬取200条
    """
    print(f"\n{'='*60}")
    print(f"  🤖 DeepSeek V4 自我深度学习开始")
    print(f"  目标: 并行生成 {target_count} 条高质量病例")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    # 检查当前总数，每3000条为一组自动分组
    before_stats = get_learning_stats()
    current_total = before_stats.get("total", 0)
    print(f"  当前案例库: {current_total} 条 (每3000条为一组)")
    print()

    stats = {"total": 0, "saved": 0, "skipped": 0, "errors": 0}

    # 并行生成（同时8个请求，加速大数据收集）
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def generate_and_save(domain):
        case = generate_one_case(domain)
        if "error" in case:
            return ("error", case["error"][:40])
        if save_case_to_db(case):
            dept = case.get("department", "?")
            diag = case.get("diagnosis", "?")[:20]
            return ("saved", f"[{dept}] {diag}")
        return ("skipped", "已存在")

    while stats["saved"] < target_count:
        # 每次并行处理4个领域
        batch_domains = DOMAINS * 3  # 重复循环直到够数
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(generate_and_save, d): d for d in batch_domains}
            for future in as_completed(futures):
                if stats["saved"] >= target_count:
                    break
                stats["total"] += 1
                result_type, msg = future.result()
                if result_type == "saved":
                    stats["saved"] += 1
                    print(f"  ✅ [{stats['total']:3d}] {msg}")
                elif result_type == "error":
                    stats["errors"] += 1
                    print(f"  ❌ [{stats['total']:3d}] {msg}")
                else:
                    stats["skipped"] += 1
                    # 跳过的不打印，只计数

        if stats["saved"] < target_count and stats["total"] >= target_count * 3:
            # 如果尝试了太多仍然不够，跳出循环
            break
    summary = (
        f"\n{'='*60}\n"
        f"  📊 学习完成统计\n"
        f"  {'='*60}\n"
        f"  总尝试: {stats['total']} 条\n"
        f"  成功保存: {stats['saved']} 条\n"
        f"  跳过重复: {stats['skipped']} 条\n"
        f"  生成失败: {stats['errors']} 条\n"
        f"  用时: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'='*60}\n"
    )
    print(summary)

    # 生成学习报告并保存
    report_path = os.path.join(os.path.expanduser("~"), "medical_reports",
                               f"learn_summary_{datetime.now().strftime('%Y%m%d_%H%M')}.txt")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(summary)
    print(f"  学习报告已保存: {report_path}")

    return stats


# ====== 案例检索 ======

def find_similar_cases(symptom_text: str, limit: int = 5) -> list:
    """
    根据症状描述检索相似的历史病例（RAG检索）
    用于增强AI智能体的诊断能力
    """
    try:
        import pymysql
        conn = pymysql.connect(
            host="localhost", port=3306,
            user="root", password="123456",
            database="患者病历库", charset="utf8mb4"
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            # 关键词匹配检索
            # 使用 LIKE 匹配任何包含症状关键字的病例
            like_clauses = []
            keywords = [k.strip() for k in re.split(r'[，,。.、\s]', symptom_text) if len(k.strip()) >= 2]
            for kw in keywords[:5]:  # 最多用5个关键词
                like_clauses.append(f"symptoms_keywords LIKE '%{kw}%'")

            if like_clauses:
                sql = f"SELECT * FROM learned_cases WHERE {' OR '.join(like_clauses)} ORDER BY used_count ASC, created_at DESC LIMIT {limit}"
            else:
                sql = f"SELECT * FROM learned_cases ORDER BY used_count ASC, created_at DESC LIMIT {limit}"

            cur.execute(sql)
            rows = cur.fetchall()

            # 更新使用次数
            for row in rows:
                cur.execute("UPDATE learned_cases SET used_count = used_count + 1 WHERE id=%s", (row['id'],))
            conn.commit()

        conn.close()
        return [{
            "symptoms": r["case_text"],
            "diagnosis": r["diagnosis"],
            "department": r["department"],
            "severity": r["severity"],
            "diseases": json.loads(r["disease_probs"]) if r["disease_probs"] else [],
        } for r in rows]
    except Exception as e:
        print(f"[检索] 错误: {e}")
        return []


def get_learning_stats() -> dict:
    """获取学习数据统计"""
    try:
        import pymysql
        conn = pymysql.connect(
            host="localhost", port=3306,
            user="root", password="123456",
            database="患者病历库", charset="utf8mb4"
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS total FROM learned_cases")
            total = cur.fetchone()["total"]

            cur.execute("""
                SELECT department, COUNT(*) AS cnt 
                FROM learned_cases 
                GROUP BY department 
                ORDER BY cnt DESC
            """)
            dept_stats = {r["department"]: r["cnt"] for r in cur.fetchall()}

            cur.execute("""
                SELECT DATE(created_at) AS d, COUNT(*) AS cnt
                FROM learned_cases
                GROUP BY DATE(created_at)
                ORDER BY d DESC
                LIMIT 7
            """)
            daily = {str(r["d"]): r["cnt"] for r in cur.fetchall()}

            cur.execute("SELECT AVG(used_count) AS avg_used FROM learned_cases")
            avg = round(cur.fetchone()["avg_used"] or 0, 1)

        conn.close()
        return {
            "total": total,
            "by_department": dept_stats,
            "daily": daily,
            "avg_usage": avg,
        }
    except Exception as e:
        return {"error": str(e)}


# ====== 主入口 ======

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════╗
    ║   🤖 DeepSeek V4 自我深度学习系统        ║
    ║   使用AI生成病例 → 建立案例库 → 持续学习 ║
    ╚══════════════════════════════════════╝
    """)

    # 学习前统计
    before = get_learning_stats()
    print(f"现有病例数: {before.get('total', 0)}")

    # 执行学习
    stats = run_learning_cycle(50)

    # 学习后统计
    after = get_learning_stats()
    print(f"学习后病例数: {after.get('total', 0)}")

    # 输出给 cron 的结果
    print(f"\nRESULT: saved={stats['saved']}, total_learned={after.get('total', 0)}")
