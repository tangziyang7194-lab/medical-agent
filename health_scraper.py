"""
超快多源健康养生建议采集器
并发爬取，仅解析列表页，不打开文章页，30秒内完成
"""
import sys, os, json, re, random, warnings
from datetime import datetime
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TIMEOUT = 5

# 可靠的快速源
# 已验证可访问的源（2026-07测试通过）
SOURCES = [
    {"name": "央视健康", "url": "https://jiankang.cctv.com/", "kw": ["健康","养生","饮食","运动","睡眠","保健"]},
    {"name": "人民健康", "url": "http://health.people.com.cn/", "kw": ["健康","养生","医疗","保健","预防","饮食"]},
    {"name": "新华健康", "url": "http://www.xinhuanet.com/health/", "kw": ["健康","养生","保健","医疗","预防"]},
    {"name": "生命时报", "url": "https://www.lifetimes.cn/", "kw": ["健康","养生","长寿","营养","锻炼","心理"]},
    {"name": "健康时报", "url": "https://health.sina.com.cn/", "kw": ["健康","养生","饮食","运动","心理","女性","儿童","老年"]},
    {"name": "寻医问药", "url": "https://www.xywy.com/", "kw": ["健康","养生","食疗","中医","保健","预防","调理"]},
    {"name": "中华养生", "url": "https://www.cnys.com/", "kw": ["养生","健康","饮食","运动","穴位","按摩","食疗","季节"]},
    {"name": "环球健康", "url": "https://health.huanqiu.com/", "kw": ["健康","养生","医疗","保健","饮食","运动","心理"]},
    {"name": "中华网健康", "url": "https://health.china.com/", "kw": ["健康","养生","医疗","预防","饮食","保健"]},
    {"name": "健客网", "url": "https://www.jianke.com/", "kw": ["健康","养生","用药","保健","疾病","预防","调理"]},
    {"name": "大众医药", "url": "https://www.dayi.org.cn/", "kw": ["健康","养生","药品","保健","疾病","预防"]},
    {"name": "医脉通", "url": "https://www.medsci.cn/", "kw": ["健康","医学","养生","预防","治疗","保健"]},
    {"name": "好大夫", "url": "https://www.haodf.com/", "kw": ["健康","养生","疾病","预防","饮食","运动","保健"]},
    {"name": "39健康网", "url": "https://www.39.net/", "kw": ["健康","养生","减肥","饮食","运动","两性","育儿","中医"]},
    {"name": "健康一线", "url": "https://www.vodjk.com/", "kw": ["健康","养生","饮食","运动","中医","保健","预防"]},
    {"name": "丁香园", "url": "https://www.dxy.cn/", "kw": ["健康","医学","科普","养生","预防","饮食"]},
    {"name": "快速问医生", "url": "https://www.120ask.com/", "kw": ["健康","养生","症状","预防","饮食","运动"]},
    {"name": "飞华健康", "url": "https://www.fh21.com.cn/", "kw": ["健康","养生","减肥","饮食","心理","中医"]},
    {"name": "健康之路", "url": "https://www.jkzl.com/", "kw": ["健康","养生","饮食","运动","保健","预防"]},
    {"name": "养生堂", "url": "https://www.yst.hk/", "kw": ["养生","健康","食疗","穴位","中药","调理"]},
]

FALLBACK_TIPS = [
    {"title": "晨起一杯温水", "content": "每天早晨起床后喝一杯温开水，可以促进肠胃蠕动，帮助排毒，补充夜间流失的水分。", "category": "饮食养生"},
    {"title": "饭后百步走", "content": "饭后适当散步15-30分钟，有助于消化吸收，促进血液循环，但避免剧烈运动。", "category": "运动健身"},
    {"title": "规律作息", "content": "保持固定的作息时间，晚上11点前入睡，保证7-8小时睡眠，有助于提高免疫力。", "category": "睡眠健康"},
    {"title": "保持心情愉悦", "content": "积极乐观的心态是健康的基石，学会调节情绪，适当放松，避免长期焦虑和压力。", "category": "心理健康"},
]

def fetch_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        r.encoding = "utf-8"
        return r.text if r.status_code == 200 else None
    except:
        return None

def extract_snippets(html, base_url, keywords):
    """提取健康文章列表（过滤导航等无用内容）"""
    tips = []
    skip_words = ["首页", "网站首页", "登录", "注册", "搜索", "关于我们", "联系我们",
                  "广告", "免责声明", "版权", "新闻中心", "产品中心", "热门推荐",
                  "点击", "更多", "专题", "视频", "图片", "ENGLISH", "English"]
    try:
        soup = BeautifulSoup(html, "lxml")
        # 移除script/style
        for t in soup(["script", "style", "nav", "header", "footer"]):
            t.decompose()

        # 找所有链接文本
        for a in soup.find_all("a", href=True, limit=200):
            text = a.get_text(strip=True)
            href = a.get("href", "")
            if len(text) < 12:
                continue
            # 跳过导航文字
            if any(s in text for s in skip_words):
                continue
            if not any(kw in text for kw in keywords):
                continue

            # 找父级或兄弟元素获取摘要
            parent = a.parent
            summary = text
            if parent:
                # 尝试获取父级附近文本作为摘要
                all_text = parent.get_text(strip=True)
                if len(all_text) > len(text) + 10:
                    summary = all_text
            # 清理过长的摘要
            summary = re.sub(r"\s+", " ", summary).strip()[:150]
            title = text[:35]

            tips.append({
                "title": title,
                "content": summary,
                "category": guess_category(text),
                "source": "网络采集",
                "source_url": urljoin(base_url, href) if href.startswith("http") else urljoin(base_url, href)
            })
            if len(tips) >= 12:
                break
    except:
        pass
    return tips

def scrape_source(source):
    """并发抓取单个源"""
    html = fetch_page(source["url"])
    if not html:
        return []
    tips = extract_snippets(html, source["url"], source["kw"])
    return tips

def guess_category(text):
    cats = {"饮食":["饮食","吃","喝","食物","营养","食疗","食谱","蔬菜","水果","茶","水"],
            "运动":["运动","锻炼","健身","跑步","散步","瑜伽","太极","操"],
            "睡眠":["睡眠","睡觉","失眠","熬夜","入睡","作息"],
            "心理":["心理","心情","情绪","压力","焦虑","抑郁","放松","心态"],
            "中医":["中医","穴位","按摩","针灸","经络","气血","阴阳","调理"],
            "季节":["季节","春季","夏季","秋季","冬季","换季","节气"],
            "老年":["老年","老人","长寿","抗衰老","骨质疏松"]}
    for cat, kws in cats.items():
        if any(k in text for k in kws):
            return cat + "养生"
    return "综合养生"

def collect_tips(count=10):
    """30秒内采集10条健康建议"""
    print(f"[采集] 开始并发采集 {count} 条...")
    all_tips = []

    # 并发抓取所有源
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(scrape_source, s): s["name"] for s in SOURCES}
        for f in as_completed(futures, timeout=25):
            try:
                all_tips.extend(f.result(timeout=5))
            except:
                pass

    # 过滤2025年以前的旧内容
    filtered = []
    for t in all_tips:
        title = t.get("title", "")
        content = t.get("content", "")
        # 跳过含旧年份的内容
        old_years = ["2020","2021","2022","2023","2024"]
        if any(f"{y}年" in title or f"{y}年" in content for y in old_years):
            continue
        filtered.append(t)
    all_tips = filtered
    print(f"  网站采集到 {len(all_tips)} 条")

    # 去重（基于前25字）
    seen = set()
    uniq = []
    for t in all_tips:
        k = t.get("title", "")[:25].replace(" ", "")
        if k not in seen:
            seen.add(k)
            uniq.append(t)

    random.shuffle(uniq)
    result = uniq[:count]
    result = uniq[:min(count, len(uniq))]
    print(f"  最终 {len(result)} 条")
    return result
