"""
健康养生建议自动生成模块
每天18:00自动生成10条健康建议，每100条为一组存入数据库
"""
import sys
import os
import json
import time
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

# ========== 数据库操作 ==========

def ensure_table():
    """确保健康建议表存在"""
    import pymysql
    from config_loader import get_db_conn_kwargs
    conn = pymysql.connect(**get_db_conn_kwargs())
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS health_tips (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                content TEXT NOT NULL,
                category VARCHAR(50) DEFAULT '养生',
                source VARCHAR(100) DEFAULT 'AI生成',
                batch_id INT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
    conn.close()

def get_current_batch():
    """获取当前批次号"""
    import pymysql
    from config_loader import get_db_conn_kwargs
    conn = pymysql.connect(**get_db_conn_kwargs())
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(batch_id), 0) FROM health_tips")
        max_batch = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM health_tips WHERE batch_id=%s", (max_batch,))
        count = cur.fetchone()[0] or 0
    conn.close()
    if count >= 100:
        return max_batch + 1
    return max_batch if max_batch > 0 else 1

# ========== AI生成健康建议 ==========

HEALTH_TOPICS = [
    "饮食养生", "运动健身", "睡眠健康", "心理健康",
    "季节养生", "中医调理", "办公室健康", "老年保健",
    "儿童健康", "女性养生", "男性健康", "亚健康调理",
    "免疫力提升", "心血管保养", "肠胃养护", "颈椎腰椎保健"
]

def generate_tips(count=10):
    """使用GLM生成健康养生建议"""
    try:
        from openai import OpenAI
        from config_loader import ZHIPUAI_API_KEY, ZHIPUAI_API_BASE, ZHIPUAI_MODEL
        
        if not ZHIPUAI_API_KEY or ZHIPUAI_API_KEY == "":
            return generate_fallback_tips(count)
        
        client = OpenAI(api_key=ZHIPUAI_API_KEY, base_url=ZHIPUAI_API_BASE)
        
        import random
        topic = random.choice(HEALTH_TOPICS)
        
        prompt = f"""你是一位资深中医养生专家。请生成{count}条关于"{topic}"的实用健康建议。
要求：
1. 每条建议包含标题和内容
2. 内容简短实用，50-100字
3. 基于中医养生理论和现代医学常识
4. 语言通俗易懂
5. 严格以JSON格式返回，格式为：{{"tips": [{{"title": "标题", "content": "内容", "category": "养生"}}]}}"""

        resp = client.chat.completions.create(
            model=ZHIPUAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=4096
        )
        raw = resp.choices[0].message.content
        
        # 解析JSON
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        raw = raw.strip()
        
        data = json.loads(raw)
        tips = data.get("tips", [])
        
        if len(tips) >= count:
            return tips[:count]
        return tips
    except Exception as e:
        print(f"[健康建议] AI生成失败: {e}")
        return generate_fallback_tips(count)

def generate_fallback_tips(count=10):
    """备用健康建议（AI不可用时）"""
    fallback = [
        {"title": "晨起一杯温水", "content": "每天早晨起床后喝一杯温开水，可以促进肠胃蠕动，帮助排毒，补充夜间流失的水分。", "category": "饮食养生"},
        {"title": "饭后百步走", "content": "饭后适当散步15-30分钟，有助于消化吸收，促进血液循环，但避免剧烈运动。", "category": "运动健身"},
        {"title": "规律作息", "content": "保持固定的作息时间，晚上11点前入睡，保证7-8小时睡眠，有助于提高免疫力。", "category": "睡眠健康"},
        {"title": "保持心情愉悦", "content": "积极乐观的心态是健康的基石，学会调节情绪，适当放松，避免长期焦虑和压力。", "category": "心理健康"},
        {"title": "饮食多样化", "content": "每天摄入12种以上食物，包括谷薯类、蔬菜水果、畜禽鱼蛋奶、大豆坚果等，营养均衡。", "category": "饮食养生"},
        {"title": "适量晒太阳", "content": "每天适度晒太阳15-20分钟，有助于维生素D的合成，促进钙吸收，增强骨骼健康。", "category": "季节养生"},
        {"title": "坐姿要正确", "content": "保持正确的坐姿，腰背挺直，双脚平放，每坐45分钟站起来活动5分钟，预防颈椎腰椎病。", "category": "办公室健康"},
        {"title": "按摩足三里", "content": "每天按压足三里穴位3-5分钟，可以调理脾胃、增强免疫力、缓解疲劳。", "category": "中医调理"},
        {"title": "深呼吸放松", "content": "每天做3次深呼吸练习：吸气4秒-屏息4秒-呼气6秒，有助于缓解压力、改善心肺功能。", "category": "心理健康"},
        {"title": "少吃生冷食物", "content": "过量食用生冷食物会损伤脾胃阳气，导致消化不良、腹痛腹泻，建议适量食用温热食物。", "category": "饮食养生"},
    ]
    # 随机选取count条
    import random
    random.shuffle(fallback)
    return fallback[:count]

# ========== 保存到数据库 ==========

def load_all_titles():
    try:
        import pymysql
        from config_loader import get_db_conn_kwargs
        conn = pymysql.connect(**get_db_conn_kwargs())
        with conn.cursor() as cur:
            cur.execute("SELECT title FROM health_tips")
            return [r[0] for r in cur.fetchall()]
        conn.close()
    except:
        return []



def dedup_all():
    """扫描全部tips，删除重复条目（保留最早的）"""
    import pymysql
    from config_loader import get_db_conn_kwargs
    conn = pymysql.connect(**get_db_conn_kwargs())
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("SELECT id, title FROM health_tips ORDER BY id ASC")
        tips = cur.fetchall()
    
    deleted = []
    kept = set()
    for tip in tips:
        s1 = set(tip["title"].replace(" ", ""))
        if len(s1) < 3:
            continue
        is_dup = False
        for k_title in list(kept):
            s2 = set(k_title.replace(" ", ""))
            if not s2: continue
            o = len(s1 & s2)
            u = len(s1 | s2)
            if u > 0 and (o/u) >= 0.5:
                is_dup = True
                break
        if is_dup:
            deleted.append(tip["id"])
        else:
            kept.add(tip["title"])
    
    if deleted:
        placeholders = ",".join(["%s"] * len(deleted))
        with conn.cursor() as cur:
            cur.execute("DELETE FROM health_tips WHERE id IN (" + placeholders + ")", deleted)
            conn.commit()
        print(f"[去重] 删除 {len(deleted)} 条重复")
    else:
        print("[去重] 无重复")
    conn.close()
    return {"deleted": len(deleted), "total": len(tips)}

def is_duplicate(new_title, existing_titles, threshold=0.5):
    prefix=new_title[:15];
    for t in existing_titles:
        if len(t)>5 and (prefix in t or t[:15] in new_title):
            return True
    return False

def save_tips(tips, batch_id):
    """保存健康建议到数据库"""
    import pymysql
    from config_loader import get_db_conn_kwargs
    saved = 0
    skipped = 0
    try:
        existing = load_all_titles()
        conn = pymysql.connect(**get_db_conn_kwargs())
        with conn.cursor() as cur:
            for tip in tips:
                title = tip.get("title", "")[:200]
                content = tip.get("content", "")
                category = tip.get("category", "养生")
                source_field = tip.get("source", "AI养生建议")
                source_url = tip.get("source_url", "")
                if is_duplicate(title, existing):
                    skipped += 1
                    continue
                cur.execute(
                    "INSERT INTO health_tips (title, content, category, source, source_url, batch_id) VALUES (%s, %s, %s, %s, %s, %s)",
                    (title, content, category, source_field, source_url, batch_id)
                )
                saved += 1
                existing.append(title)
        conn.commit()
        conn.close()
        if skipped > 0:
            print(f"  去重跳过 {skipped} 条")
    except Exception as e:
        print(f"[健康建议] 保存失败: {e}")
    return saved

# ========== 主执行函数 ==========

def run_daily_task(count=50):
    """每天18:00执行的任务 - 多源采集"""
    print(f"[健康建议] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 开始采集健康建议...")
    ensure_table()
    batch_id = get_current_batch()
    from health_scraper import collect_tips
    tips = collect_tips(count=count)
    if tips:
        saved = save_tips(tips, batch_id)
        print(f"[健康建议] 成功保存 {saved} 条建议到批次 {batch_id}")
        sources = {}
        for t in tips:
            src = t.get("source", "未知")
            sources[src] = sources.get(src, 0) + 1
        print(f"[健康建议] 来源分布: {sources}")
        return {"success": True, "saved": saved, "batch": batch_id, "sources": sources}
    else:
        print(f"[健康建议] 采集失败")
        return {"success": False, "saved": 0}

def get_stats():
    """获取健康建议统计"""
    import pymysql
    from config_loader import get_db_conn_kwargs
    try:
        conn = pymysql.connect(**get_db_conn_kwargs())
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS total, COALESCE(MAX(batch_id), 0) AS max_batch FROM health_tips")
            row = cur.fetchone()
            cur.execute("SELECT batch_id, COUNT(*) AS cnt, MIN(created_at) AS start_time FROM health_tips GROUP BY batch_id ORDER BY batch_id")
            batches = cur.fetchall()
        conn.close()
        return {"total": row["total"], "max_batch": row["max_batch"], "batches": batches}
    except Exception:
        return {"total": 0, "max_batch": 0, "batches": []}

def get_tips(limit=20, batch_id=None):
    """获取健康建议列表"""
    import pymysql
    from config_loader import get_db_conn_kwargs
    try:
        conn = pymysql.connect(**get_db_conn_kwargs())
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            if batch_id:
                cur.execute("SELECT id, title, content, summary, category, source, source_url, batch_id, created_at FROM health_tips WHERE batch_id=%s ORDER BY id DESC LIMIT %s", (batch_id, limit))
            else:
                cur.execute("SELECT id, title, content, summary, category, source, source_url, batch_id, created_at FROM health_tips ORDER BY id DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []
