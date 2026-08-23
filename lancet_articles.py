"""
PubMed医学文献采集模块
每天18:10自动采集1篇最新中文医学文献，用DeepSeek AI生成总结和翻译
"""
import sys, json, re, pymysql, requests, time
from datetime import datetime
from openai import OpenAI
sys.stdout.reconfigure(encoding="utf-8")

HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 10

def ensure_table():
    """创建文献表"""
    conn = pymysql.connect(host="localhost",port=3306,user="root",password="123456",database="患者病历库",charset="utf8mb4")
    with conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS lancet_articles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(500),
            source_url VARCHAR(1000),
            published VARCHAR(50),
            abstract TEXT,
            summary TEXT,
            translation TEXT,
            source VARCHAR(100),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.commit()
    conn.close()

def fetch_pubmed_articles(max_results=3):
    """从PubMed搜索中国相关医学文献"""
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    # Search for Chinese medical topics
    queries = [
        "China[Affiliation] AND 2025[pdat] AND hasabstract[text]",
        "Chinese[Affiliation] AND Medicine[Journal] AND 2025[pdat]",
    ]
    all_ids = []
    for q in queries:
        try:
            r = requests.get(f"{base}/esearch.fcgi", params={
                "db": "pubmed", "term": q, "retmax": max_results,
                "retmode": "json", "sort": "pub+date"
            }, headers=HEADERS, timeout=8)
            if r.status_code == 200:
                ids = r.json().get("esearchresult", {}).get("idlist", [])
                all_ids.extend(ids[:3])
        except Exception as e:
            print(f"  PubMed search failed: {e}")
    
    if not all_ids:
        return []
    
    # Fetch abstracts for found IDs
    r = requests.get(f"{base}/efetch.fcgi", params={
        "db": "pubmed", "id": ",".join(all_ids[:5]), "retmode": "xml",
        "rettype": "abstract"
    }, headers=HEADERS, timeout=10)
    
    articles = []
    if r.status_code == 200:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.text)
        for art in root.findall(".//PubmedArticle"):
            try:
                title = art.find(".//ArticleTitle")
                title = title.text if title is not None else ""
                abst = art.find(".//AbstractText")
                abstract = abst.text if abst is not None else ""
                # Source URL
                pmid = art.find(".//PMID")
                pmid = pmid.text if pmid is not None else ""
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                # Published date
                pub_date = art.find(".//PubDate")
                year = pub_date.find("Year").text if pub_date is not None and pub_date.find("Year") is not None else ""
                articles.append({
                    "title": title, "source_url": url, "published": year,
                    "abstract": abstract[:1000], "source": "PubMed"
                })
            except Exception:
                pass
    return articles

def ai_translate_lancet(title, abstract):
    """翻译为中文"""
    from config_loader import ZHIPUAI_API_KEY, ZHIPUAI_API_BASE, ZHIPUAI_MODEL
    client = OpenAI(api_key=ZHIPUAI_API_KEY, base_url=ZHIPUAI_API_BASE)
    prompt = f"请将以下医学文献翻译成专业流畅的中文：\n标题：{title}\n摘要：{abstract[:1500]}\n\n要求：专业术语准确，语句通顺"
    resp = client.chat.completions.create(model=ZHIPUAI_MODEL, messages=[{"role":"user","content":prompt}], temperature=0.2, max_tokens=2000)
    return resp.choices[0].message.content.strip()

def ai_summarize_lancet(title, abstract, source_url):
    """AI总结"""
    from config_loader import ZHIPUAI_API_KEY, ZHIPUAI_API_BASE, ZHIPUAI_MODEL
    client = OpenAI(api_key=ZHIPUAI_API_KEY, base_url=ZHIPUAI_API_BASE)
    prompt = f"请对此医学文献进行约800字的分段总结：\n标题：{title}\n摘要：{abstract[:1500]}\n链接：{source_url}\n\n分为3-4段（研究背景/方法/发现/意义），直接输出总结"
    resp = client.chat.completions.create(model=ZHIPUAI_MODEL, messages=[{"role":"user","content":prompt}], temperature=0.3, max_tokens=2500)
    return resp.choices[0].message.content.strip()

def save_articles(articles):
    """保存到数据库"""
    conn = pymysql.connect(host="localhost",port=3306,user="root",password="123456",database="患者病历库",charset="utf8mb4")
    saved = 0
    with conn.cursor() as cur:
        for a in articles:
            cur.execute("SELECT id FROM lancet_articles WHERE source_url=%s", (a["source_url"],))
            if cur.fetchone(): continue
            cur.execute("INSERT INTO lancet_articles (title,source_url,published,abstract,summary,source) VALUES (%s,%s,%s,%s,%s,%s)",
                       (a["title"][:500], a["source_url"][:1000], a["published"][:50], a["abstract"][:1000], a.get("summary",""), a.get("source","")))
            saved += 1
    conn.commit(); conn.close()
    return saved

def run_lancet_task():
    """采集1篇"""
    print(f"[文献] {datetime.now():%H:%M:%S} 开始采集...")
    ensure_table()
    articles = fetch_pubmed_articles(3)
    print(f"  获取 {len(articles)} 篇")
    if not articles: return {"success": False}
    # Take first 1
    unique = articles[:1]
    saved = save_articles(unique)
    print(f"  保存 {saved} 篇（后台总结中...）")
    return {"success": True, "fetched": len(articles), "saved": saved}

def get_lancet_articles(limit=50):
    conn = pymysql.connect(host="localhost",port=3306,user="root",password="123456",database="患者病历库",charset="utf8mb4")
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("SELECT * FROM lancet_articles ORDER BY created_at DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
    conn.close()
    for r in rows:
        if r.get("created_at"): r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M:%S")
    return rows

def get_lancet_stats():
    conn = pymysql.connect(host="localhost",port=3306,user="root",password="123456",database="患者病历库",charset="utf8mb4")
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM lancet_articles")
        total = cur.fetchone()[0]
    conn.close()
    return {"total": total}
