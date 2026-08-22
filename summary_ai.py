"""
AI文章总结模块 - 对已有内容生成110-180字摘要
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import pymysql
from openai import OpenAI

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TIMEOUT = 8

def ai_summarize(title, content):
    """用质谱AI总结文章，110-180字"""
    from config_loader import ZHIPUAI_API_KEY, ZHIPUAI_API_BASE, ZHIPUAI_MODEL
    client = OpenAI(api_key=ZHIPUAI_API_KEY, base_url=ZHIPUAI_API_BASE)
    
    prompt = f"""请用110-180字概括以下健康文章的核心内容，语言精炼专业：

标题：{title}
正文：{content[:2000]}

要求：
1. 110-180字
2. 突出核心观点和实用要点
3. 不要照搬原文，要提炼概括
4. 直接输出摘要文本，不要加前缀"""

    resp = client.chat.completions.create(
        model=ZHIPUAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3, max_tokens=500
    )
    return resp.choices[0].message.content.strip()

def summarize_all():
    """对所有有链接的tips用AI总结"""
    conn = pymysql.connect(host="localhost", port=3306, user="root", password="123456", database="患者病历库", charset="utf8mb4")
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("SELECT id, title, content, summary FROM health_tips WHERE source_url IS NOT NULL AND source_url != '' AND (summary IS NULL OR summary = '') ORDER BY id DESC LIMIT 50")
        tips = cur.fetchall()
    conn.close()

    results = {"ok": 0, "skip": 0, "fail": 0}
    for tip in tips:
        if tip.get("summary") and len(tip["summary"]) > 20:
            results["skip"] += 1
            continue
        try:
            summary = ai_summarize(tip["title"], tip["content"])
            if summary and len(summary) > 20:
                conn2 = pymysql.connect(host="localhost", port=3306, user="root", password="123456", database="患者病历库", charset="utf8mb4")
                with conn2.cursor() as cur:
                    cur.execute("UPDATE health_tips SET summary=%s WHERE id=%s", (summary, tip["id"]))
                    conn2.commit()
                conn2.close()
                results["ok"] += 1
                print(f"  #{tip['id']}: " + summary[:60] + "...")
            else:
                results["fail"] += 1
        except Exception as e:
            results["fail"] += 1
            print(f"  #{tip['id']} failed: {e}")
    print(f"Results: {results}")
    return results
