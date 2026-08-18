"""
柳叶刀文章翻译模块 - 后台异步翻译
采集完成后对新文章进行质谱AI中文翻译
"""
import sys, pymysql
from zhipuai import ZhipuAI
sys.stdout.reconfigure(encoding="utf-8")

def translate_pending():
    """翻译所有未翻译的文章"""
    conn = pymysql.connect(host="localhost",port=3306,user="root",password="123456",database="患者病历库",charset="utf8mb4")
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(
            "SELECT id, title, abstract FROM lancet_articles WHERE (translation IS NULL OR translation='') AND abstract IS NOT NULL AND abstract!='' LIMIT 20"
        )
        tips = cur.fetchall()
    conn.close()
    
    if not tips:
        print("  无待翻译文章")
        return {"translated": 0}
    
    from config_loader import ZHIPUAI_API_KEY, ZHIPUAI_API_BASE, ZHIPUAI_MODEL
    client = ZhipuAI(api_key=ZHIPUAI_API_KEY, base_url=ZHIPUAI_API_BASE)
    
    translated = 0
    for tip in tips:
        try:
            prompt = f"请将以下医学文章翻译成专业流畅的中文：\n标题：{tip['title']}\n摘要：{(tip['abstract'] or '')[:1500]}\n\n要求：专业医学术语准确，语句通顺自然"
            resp = client.chat.completions.create(
                model=ZHIPUAI_MODEL,
                messages=[{"role":"user","content":prompt}],
                temperature=0.2, max_tokens=2000
            )
            text = resp.choices[0].message.content.strip()
            conn2 = pymysql.connect(host="localhost",port=3306,user="root",password="123456",database="患者病历库",charset="utf8mb4")
            with conn2.cursor() as cur2:
                cur2.execute("UPDATE lancet_articles SET translation=%s WHERE id=%s", (text, tip["id"]))
                conn2.commit()
            conn2.close()
            translated += 1
            print(f"  翻译 #{tip['id']}: {text[:40]}...")
        except Exception as e:
            print(f"  翻译 #{tip['id']} 失败: {e}")
    print(f"  完成: {translated}/{len(tips)}")
    return {"translated": translated, "total": len(tips)}
