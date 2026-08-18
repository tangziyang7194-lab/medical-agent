"""
模拟医学知识库
提供症状检查清单、医学知识查询、危险信号列表
"""

from typing import List, Dict

# ========== 临床科室症状映射 ==========

DEPT_SYMPTOMS = {
    "急诊科": ["突发", "昏迷", "大出血", "严重外伤", "中毒", "剧烈疼痛",
               "呼吸困难", "心脏骤停", "休克", "高烧不退", "急症", "意识不清",
               "胸痛", "窒息", "严重过敏"],
    "内科": ["发热", "咳嗽", "胸闷", "气短", "乏力", "头晕", "头痛", "心悸",
             "消化不良", "腹痛", "腹泻", "便秘", "恶心", "呕吐"],
    "外科": ["肿块", "外伤", "骨折", "关节痛", "颈部肿块", "乳腺肿块",
             "疝气", "胆囊炎", "阑尾炎", "肠梗阻", "静脉曲张"],
    "妇产科": ["月经不调", "痛经", "白带异常", "阴道出血", "不孕",
               "子宫肌瘤", "卵巢囊肿", "怀孕", "产检", "更年期"],
    "儿科": ["儿童发热", "小儿咳嗽", "小儿腹泻", "厌食", "发育迟缓",
             "手足口病", "小儿湿疹", "新生儿黄疸"],
    "中医科": ["调理", "亚健康", "气虚", "血虚", "失眠", "慢性病调理"],
    "耳鼻喉科": ["耳聋", "耳鸣", "鼻炎", "鼻窦炎", "咽喉炎", "眩晕", "打鼾"],
    "口腔科": ["牙痛", "牙龈出血", "口腔溃疡", "蛀牙", "智齿"],
    "眼科": ["视力下降", "眼干", "眼红", "白内障", "青光眼", "飞蚊症"],
    "皮肤科": ["皮疹", "湿疹", "荨麻疹", "痤疮", "脱发", "皮肤瘙痒"],
    "康复科": ["中风后遗症", "骨折术后", "运动损伤", "偏瘫"],
    "预防保健科": ["体检", "疫苗接种", "健康咨询"],
    "肛肠科": ["便血", "便秘", "肛裂", "肛瘘", "肛周脓肿"],
}

# ========== 危险信号 ==========

RED_FLAGS = [
    ("昏迷/意识不清", "立即拨打120！可能是脑卒中或严重代谢异常"),
    ("呼吸困难", "立即就医！可能是心衰、哮喘急性发作或肺栓塞"),
    ("剧烈胸痛", "立即就医！高度怀疑急性心肌梗死"),
    ("大出血", "立即压迫止血并拨打120！"),
    ("高烧不退(>39°C持续3天)", "尽快就医！警惕严重感染"),
    ("突发剧烈头痛", "尽快就医！警惕蛛网膜下腔出血"),
    ("抽搐/惊厥", "立即就医！可能是癫痫或颅内感染"),
    ("严重过敏/喉头水肿", "立即注射肾上腺素并拨打120！"),
    ("咳血/咯血", "尽快就医！需排除肺结核或肺部肿瘤"),
    ("不明原因体重下降", "1个月内下降>5%需就医检查"),
]

YELLOW_FLAGS = [
    ("反复发作的腹痛", "建议消化内科就诊，可能需胃镜/肠镜检查"),
    ("长期咳嗽(>2周)", "建议呼吸内科就诊，拍胸片检查"),
    ("便血", "建议肛肠科或消化内科就诊，需做肠镜检查"),
    ("头晕伴行走不稳", "建议神经内科就诊，需做头颅CT/MRI"),
    ("心悸伴气短", "建议心内科就诊，需做心电图和心脏超声"),
    ("关节肿痛", "建议风湿免疫科就诊，需查风湿三项"),
    ("持续低烧", "建议内科就诊，需查血常规和炎症指标"),
]

# ========== 症状检查清单 ==========

SYMPTOM_CHECKLISTS = {
    "头痛": {
        "tags": ["duration", "location", "pain_type", "severity", "accompanying", "frequency", "trigger", "history"],
        "questions": {
            "duration": "什么时候开始头痛的？持续了多久？",
            "location": "具体哪个部位痛？前额/太阳穴/后脑/还是整个头？",
            "pain_type": "是哪种痛法？胀痛/跳痛/刺痛/还是压迫感？",
            "severity": "疼痛程度如何？1-10分的话大概几分？",
            "accompanying": "有没有伴随恶心呕吐、怕光怕声或者发热？",
            "frequency": "是持续性的还是一阵一阵的？多久发作一次？",
            "trigger": "有没有什么诱因？比如熬夜、压力大、或者吃了什么东西？",
            "history": "以前有过类似情况吗？",
        }
    },
    "咳嗽": {
        "tags": ["duration", "type", "fever", "breath", "smoke", "pattern", "allergy"],
        "questions": {
            "duration": "咳嗽多久了？",
            "type": "是干咳还是有痰？痰是什么颜色和性状？",
            "fever": "有没有发烧？最高多少度？",
            "breath": "有没有胸闷、气短或喘息？",
            "smoke": "平时抽烟吗？有没有慢性呼吸系统疾病？",
            "pattern": "白天咳嗽厉害还是晚上厉害？",
            "allergy": "有没有过敏史或家族哮喘史？",
        }
    },
    "腹痛": {
        "tags": ["location", "nature", "meal", "digestive", "fever", "duration", "bleeding", "menstrual"],
        "questions": {
            "location": "具体哪个位置痛？上腹/下腹/肚脐周围/还是整个肚子？",
            "nature": "是哪种痛？绞痛/隐痛/胀痛/还是刺痛？",
            "meal": "和吃饭有关系吗？饭前痛/饭后痛/还是空腹的时候痛？",
            "digestive": "有没有恶心、呕吐、腹泻或者便秘？",
            "fever": "有没有发烧或发冷？",
            "duration": "痛了多久了？是持续性的还是一阵一阵的？",
            "bleeding": "有没有便血或黑便？",
            "menstrual": "和月经周期有关系吗？（女性）",
        }
    },
    "发热": {
        "tags": ["temp", "pattern", "chills", "accompanying", "contact", "travel"],
        "questions": {
            "temp": "最高烧到多少度？烧了几天了？",
            "pattern": "是一直发烧还是烧一阵好一阵？",
            "chills": "有没有发冷或出汗？",
            "accompanying": "有没有咳嗽、喉咙痛、头痛、关节痛或出疹子？",
            "contact": "最近有没有接触过发热的人？",
            "travel": "最近去过外地吗？",
        }
    },
    "胸痛": {
        "tags": ["location", "nature", "radiate", "trigger", "duration", "relief", "accompanying", "history"],
        "questions": {
            "location": "具体哪个位置痛？胸口正中间/偏左/偏右？",
            "nature": "是哪种痛法？压榨感/刺痛/还是烧灼感？",
            "radiate": "疼痛会放射到其他地方吗？比如左肩、后背或下巴？",
            "trigger": "什么情况下容易发作？劳累后/情绪激动时/深呼吸时？",
            "duration": "每次痛多久？几秒/几分钟/还是持续不断？",
            "relief": "做什么能缓解？休息/含药/还是改变姿势？",
            "accompanying": "有没有出汗、气短、恶心或心慌？",
            "history": "有没有高血压、糖尿病或心脏病史？",
        }
    },
    "头晕": {
        "tags": ["type", "duration", "trigger", "ent", "nerve", "history"],
        "questions": {
            "type": "是哪种晕法？天旋地转/头重脚轻/还是走路不稳？",
            "duration": "晕多久了？几秒/几分钟/几小时/还是一整天？",
            "trigger": "什么情况下会晕？改变姿势/转头/还是劳累后？",
            "ent": "有没有耳鸣、听力下降或恶心呕吐？",
            "nerve": "有没有手脚麻木、说话不清或看东西重影？",
            "history": "有没有高血压、糖尿病或颈椎病？",
        }
    },
    "便血": {
        "tags": ["color", "amount", "stool", "accompanying", "duration", "pain", "family"],
        "questions": {
            "color": "血是什么颜色？鲜红色/暗红色/还是柏油样的黑便？",
            "amount": "出血量大概多少？纸上带血/滴血/还是大量出血？",
            "stool": "大便是什么性状？成型/稀便/还是带粘液？",
            "accompanying": "有没有腹痛、肛门坠胀感、体重下降或贫血？",
            "duration": "这种情况多久了？第一次出现还是反复发作？",
            "pain": "肛门周围有没有疼痛或瘙痒？",
            "family": "家人有没有得过结直肠癌或肠息肉？",
        }
    },
    "皮疹": {
        "tags": ["type", "itch", "location", "duration", "trigger", "relief", "history"],
        "questions": {
            "type": "皮疹是什么样的？红斑/丘疹/水疱/还是风团？",
            "itch": "痒得厉害吗？轻微/中等/还是难以忍受？",
            "location": "长在哪些部位？全身都有还是局部？",
            "duration": "出现多久了？几小时/几天/还是反复发作？",
            "trigger": "有没有什么诱因？吃了什么东西/接触了什么/还是季节变化？",
            "relief": "什么情况下会加重或缓解？",
            "history": "以前有过过敏史或湿疹吗？",
        }
    },
}

# ========== 关键词解析：从患者描述中提取已有信息 ==========

SYMPTOM_INFO_PATTERNS = {
    "duration": [
        r"(\d+)年", r"(\d+)个月", r"(\d+)周", r"(\d+)天", r"(\d+)小时",
        r"(\d+)月", r"(\d+)日",
        "很久", "好久", "这几天", "最近", "刚刚", "刚才", "多年", "多月",
    ],
    "location": [
        "前额", "太阳穴", "后脑", "头顶", "偏左", "偏右", "左侧", "右侧",
        "左边", "右边", "上腹", "下腹", "肚脐", "周围", "胸口", "后背",
        "腰部", "左下腹", "右下腹", "左上腹", "右上腹",
    ],
    "pain_type": [
        "跳痛", "胀痛", "刺痛", "绞痛", "隐痛", "灼烧", "压榨",
        "钝痛", "放射痛", "酸痛", "剧痛",
    ],
    "severity": [
        "轻微", "轻度", "中等", "中度", "严重", "剧烈", "有点",
        "很痛", "疼死", "难忍", "(\d+)分", "(\d+)级",
    ],
    "accompanying": [
        "恶心", "呕吐", "发热", "发烧", "头晕", "心慌", "气短",
        "麻木", "出汗", "腹泻", "便秘",
    ],
    "fever_temp": [
        r"(\d+)[\.度]?[度]?", r"发烧", r"发热",
    ],
    "trigger": [
        "熬夜", "压力", "劳累", "饮食", "吃了", "情绪", "激动",
        "运动", "受凉", "感冒",
    ],
}

# 额外关键词映射（简化版）
EXTRA_INFO_RULES = {
    "duration": lambda t: any(w in t for w in ["天", "周", "月", "年", "小时", "分钟", "刚刚", "最近", "很久"]),
    "severity": lambda t: any(w in t for w in ["轻微", "轻度", "中等", "中度", "严重", "剧烈", "有点", "很痛", "难忍", "分", "级"]),
    "accompanying": lambda t: any(w in t for w in ["恶心", "呕吐", "发烧", "发热", "头晕", "心慌", "气短", "麻木", "出汗", "腹泻", "体重", "贫血"]),
    "trigger": lambda t: any(w in t for w in ["熬夜", "压力", "劳累", "饮食", "吃了", "情绪", "激动", "运动", "受凉"]),
    "location": lambda t: any(w in t for w in ["前额", "太阳穴", "后脑", "头顶", "左侧", "右侧", "上腹", "下腹", "胸口", "左边", "右边", "腰部"]),
    "pain_type": lambda t: any(w in t for w in ["跳痛", "胀痛", "刺痛", "绞痛", "隐痛", "灼烧", "压榨", "钝痛"]),
    "color": lambda t: any(w in t for w in ["鲜红", "暗红", "黑便", "柏油", "红色", "血色"]),
    "stool": lambda t: any(w in t for w in ["大便", "便血", "拉肚子", "粘液", "稀便", "成型"]),
    "pain": lambda t: any(w in t for w in ["疼痛", "痛", "肛门", "坠胀"]),
    "itch": lambda t: any(w in t for w in ["痒", "瘙痒"]),
    "type": lambda t: any(w in t for w in ["干咳", "有痰", "痰"]),
    "breath": lambda t: any(w in t for w in ["胸闷", "气短", "喘息", "喘"]),
    "smoke": lambda t: any(w in t for w in ["抽烟", "吸烟", "烟"]),
    "allergy": lambda t: any(w in t for w in ["过敏", "哮喘"]),
    "nature": lambda t: any(w in t for w in ["绞痛", "隐痛", "胀痛", "刺痛", "灼烧"]),
    "temp": lambda t: any(w in t for w in ["度", "发烧", "发热", "体温"]),
    "contact": lambda t: any(w in t for w in ["接触", "传染", "家人"]),
    "frequency": lambda t: any(w in t for w in ["一阵", "持续", "反复", "间歇", "经常"]),
    "history": lambda t: any(w in t for w in ["以前", "去年", "慢性", "史", "复发"]),
    "family": lambda t: any(w in t for w in ["家人", "家族", "遗传"]),
    "nerve": lambda t: any(w in t for w in ["麻木", "无力", "言语", "复视", "走路不稳"]),
    "ent": lambda t: any(w in t for w in ["耳鸣", "听力", "耳聋"]),
}


def analyze_existing_info(text: str, main_symptom: str) -> dict:
    """
    分析患者描述中已经提供了哪些信息
    返回：{"duration": True, "location": True, ...}
    """
    provided = {}
    # 用正则匹配
    import re
    for key, patterns in SYMPTOM_INFO_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text):
                provided[key] = True
                break

    # 补充规则
    for key, rule_fn in EXTRA_INFO_RULES.items():
        if key not in provided and rule_fn(text):
            provided[key] = True

    # 如果提到具体日期数字，也算有duration信息
    if re.search(r'\d+', text) and 'duration' not in provided:
        if any(w in text for w in ['前', '前几', '过去']):
            provided['duration'] = True

    return provided


def get_dynamic_questions(symptom_name: str, existing_text: str) -> list:
    """
    根据患者已描述的内容，动态生成需要追问的问题列表
    只问缺失的信息，避免重复
    """
    synonym_map = {
        "肚子痛": "腹痛", "肚子疼": "腹痛", "胃痛": "腹痛", "胃疼": "腹痛",
        "头疼": "头痛", "发烧": "发热", "拉肚子": "腹泻",
        "胸口疼": "胸痛", "心口疼": "胸痛",
    }
    resolved = synonym_map.get(symptom_name, symptom_name)

    # 找到匹配的检查清单
    checklist = None
    for key, cl in SYMPTOM_CHECKLISTS.items():
        if key in resolved or resolved in key:
            checklist = cl
            break

    if not checklist:
        return []

    # 分析已有信息
    provided = analyze_existing_info(existing_text, resolved)

    # 生成需要追问的问题
    questions_to_ask = []
    for tag in checklist["tags"]:
        if not provided.get(tag):
            q = checklist["questions"].get(tag)
            if q:
                questions_to_ask.append(q)

    # 如果所有信息都有了，返回一个确认问题
    if not questions_to_ask:
        questions_to_ask.append(f"关于{resolved}还有其他需要补充的吗？")

    return questions_to_ask


def get_symptom_checklist(symptom_name: str) -> List[str]:
    """获取症状检查清单（保留旧接口兼容）"""
    return get_dynamic_questions(symptom_name, "")


def query_medical_knowledge(symptom_names: List[str]) -> Dict:
    """
    查询与症状相关的医学知识
    返回：{ "possible_causes": [...], "red_flags": [...], "suggested_exams": [...] }
    """
    possible_causes = set()
    red_flags = []
    suggested_exams = set()

    for symptom in symptom_names:
        # 匹配可能病因
        causes_map = {
            "头痛": ["紧张性头痛", "偏头痛", "丛集性头痛", "高血压", "颅内病变"],
            "咳嗽": ["上呼吸道感染", "支气管炎", "肺炎", "哮喘", "胃食管反流"],
            "腹痛": ["急性胃肠炎", "胃溃疡", "胆囊炎", "阑尾炎", "肠梗阻"],
            "发热": ["上呼吸道感染", "流感", "肺炎", "尿路感染", "败血症"],
            "胸痛": ["心绞痛", "心肌梗死", "肋间神经痛", "气胸", "胃食管反流"],
            "头晕": ["体位性低血压", "耳石症", "颈椎病", "贫血", "脑供血不足"],
            "便血": ["痔疮", "肛裂", "结直肠息肉", "溃疡性结肠炎", "结直肠癌"],
            "皮疹": ["过敏性皮炎", "湿疹", "荨麻疹", "真菌感染", "银屑病"],
            "乏力": ["贫血", "甲状腺功能减退", "慢性疲劳", "糖尿病", "肝病"],
            "水肿": ["肾病", "心力衰竭", "肝病", "甲状腺功能减退", "营养不良"],
        }
        for key, causes in causes_map.items():
            if key in symptom or symptom in key:
                possible_causes.update(causes)

        # 匹配危险信号
        for flag, advice in RED_FLAGS:
            for word in [f.split('/')[0] for f in flag.split('！')[0].split('，')[0].split('，')[0].split('？')[0].split('）')[0].split('（')[0].split('）')[0].split('）')[0]]:
                pass
            # 简单匹配
            flag_words = flag.replace('(', '（').replace(')', '）').split('）')[0].split('（')[0]
            if len(flag_words) > 2 and flag_words in symptom:
                red_flags.append((flag, advice))

    # 建议检查项目
    exam_map = {
        "头痛": ["头颅CT", "血压测量", "眼底检查"],
        "咳嗽": ["血常规", "胸部X光", "肺功能检查"],
        "腹痛": ["腹部B超", "血常规", "胃镜/肠镜"],
        "发热": ["血常规", "CRP", "血培养", "胸部X光"],
        "胸痛": ["心电图", "心肌酶谱", "心脏超声", "冠脉CTA"],
        "头晕": ["血压测量", "颈椎X光", "头颅CT", "耳科检查"],
        "便血": ["肛门指检", "肠镜", "粪便隐血试验"],
        "皮疹": ["皮肤镜检查", "过敏原检测", "真菌镜检"],
        "乏力": ["血常规", "甲状腺功能", "血糖", "肝肾功能"],
    }
    for symptom in symptom_names:
        for key, exams in exam_map.items():
            if key in symptom or symptom in key:
                suggested_exams.update(exams)

    return {
        "possible_causes": list(possible_causes)[:5],
        "red_flags": red_flags,
        "suggested_exams": list(suggested_exams)[:5],
    }


# ========== 疾病概率评估 ==========

DISEASE_DB = {
    "上呼吸道感染": {
        "symptoms": ["咳嗽","流鼻涕","打喷嚏","喉咙痛","发烧","头痛","鼻塞","乏力","喷嚏"],
        "weight": 0.85, "department": "内科"
    },
    "流行性感冒": {
        "symptoms": ["高烧","寒战","全身酸痛","乏力","头痛","咳嗽","喉咙痛","鼻塞"],
        "weight": 0.80, "department": "内科"
    },
    "高血压": {
        "symptoms": ["头晕","头痛","心慌","耳鸣","面红","乏力","失眠","颈项强直"],
        "weight": 0.70, "department": "内科"
    },
    "糖尿病": {
        "symptoms": ["多饮","多食","多尿","消瘦","乏力","视力模糊","手脚麻木","伤口不愈"],
        "weight": 0.75, "department": "内科"
    },
    "甲状腺功能亢进": {
        "symptoms": ["心悸","心慌","手抖","消瘦","多食","怕热","多汗","突眼","焦虑","失眠","乏力","甲状腺肿大"],
        "weight": 0.80, "department": "内科"
    },
    "甲状腺功能减退": {
        "symptoms": ["乏力","怕冷","体重增加","记忆力减退","便秘","皮肤干燥","脱发","嗜睡","浮肿"],
        "weight": 0.75, "department": "内科"
    },
    "胃炎": {
        "symptoms": ["胃痛","胃胀","反酸","烧心","恶心","食欲不振","饭后饱胀","嗳气"],
        "weight": 0.80, "department": "内科"
    },
    "胃食管反流病": {
        "symptoms": ["反酸","烧心","胸痛","吞咽困难","咳嗽","喉咙异物感","嗳气"],
        "weight": 0.75, "department": "内科"
    },
    "消化性溃疡": {
        "symptoms": ["上腹痛","空腹痛","饭后痛","黑便","恶心","呕吐","反酸","烧心"],
        "weight": 0.75, "department": "内科"
    },
    "肠易激综合征": {
        "symptoms": ["腹痛","腹泻","便秘","腹胀","排便不尽","粘液便","里急后重"],
        "weight": 0.65, "department": "内科"
    },
    "冠心病": {
        "symptoms": ["胸痛","胸闷","心悸","气短","乏力","左肩放射痛","出汗","恶心"],
        "weight": 0.80, "department": "内科"
    },
    "偏头痛": {
        "symptoms": ["头痛","恶心","呕吐","怕光","怕声","视力模糊","搏动性头痛","单侧头痛"],
        "weight": 0.75, "department": "内科"
    },
    "紧张性头痛": {
        "symptoms": ["头痛","颈肩僵硬","压迫性头痛","双侧头痛","精神紧张","疲劳"],
        "weight": 0.70, "department": "内科"
    },
    "颈椎病": {
        "symptoms": ["颈肩痛","头晕","手麻","肩背痛","头痛","恶心","上肢无力"],
        "weight": 0.70, "department": "外科"
    },
    "腰椎间盘突出": {
        "symptoms": ["腰痛","腿麻","下肢放射痛","腰部活动受限","坐骨神经痛"],
        "weight": 0.75, "department": "外科"
    },
    "脑卒中": {
        "symptoms": ["偏瘫","言语不清","口角歪斜","意识障碍","头痛","呕吐","眩晕"],
        "weight": 0.80, "department": "神经内科"
    },
    "肺炎": {
        "symptoms": ["发烧","咳嗽","咳痰","胸痛","呼吸急促","乏力","寒战"],
        "weight": 0.80, "department": "内科"
    },
    "支气管炎": {
        "symptoms": ["咳嗽","咳痰","气短","喘息","胸闷","发烧","喉咙痛"],
        "weight": 0.75, "department": "内科"
    },
    "过敏性鼻炎": {
        "symptoms": ["打喷嚏","流鼻涕","鼻塞","鼻痒","眼痒","季节性发作","清涕"],
        "weight": 0.80, "department": "耳鼻喉科"
    },
    "结膜炎": {
        "symptoms": ["眼红","眼痒","流泪","分泌物多","眼痛","畏光","异物感"],
        "weight": 0.85, "department": "眼科"
    },
    "焦虑症": {
        "symptoms": ["焦虑","失眠","心慌","手抖","出汗","呼吸困难","心悸","紧张"],
        "weight": 0.70, "department": "心理科"
    },
    "贫血": {
        "symptoms": ["乏力","头晕","面色苍白","心慌","气短","食欲不振","注意力不集中","怕冷"],
        "weight": 0.75, "department": "内科"
    },
    "阑尾炎": {
        "symptoms": ["右下腹痛","转移性腹痛","发烧","恶心","呕吐","食欲不振","反跳痛"],
        "weight": 0.85, "department": "外科"
    },
    "胆囊炎": {
        "symptoms": ["右上腹痛","饭后痛","恶心","呕吐","发烧","厌油腻","肩背放射痛"],
        "weight": 0.80, "department": "外科"
    },
    "痛风": {
        "symptoms": ["关节红肿","剧痛","足趾痛","夜间发作","尿酸高","反复发作"],
        "weight": 0.85, "department": "内科"
    },
}


def calculate_disease_probability(symptom_text: str) -> list:
    """
    根据患者描述的症状，计算各疾病概率
    返回按概率降序排列的列表: [(病名, 概率, 科室), ...]
    """
    import jieba.posseg as pseg
    words = pseg.cut(symptom_text.lower().strip())
    tokens = set(w.word for w in words)

    # 额外加入关键症状词
    symptom_keywords = []
    # 按长度降序排序，优先匹配长词
    disease_symptoms = {}
    for disease, info in DISEASE_DB.items():
        disease_symptoms[disease] = info["symptoms"]

    results = []
    for disease, info in DISEASE_DB.items():
        matched = 0
        total = len(info["symptoms"])
        for sym in info["symptoms"]:
            if sym in symptom_text:
                matched += 1
        if matched == 0:
            continue
        # 概率计算：匹配比例 × 疾病权重
        ratio = matched / total
        probability = round(ratio * info["weight"] * 100, 1)
        results.append((disease, probability, info["department"]))

    # 按概率降序排列
    results.sort(key=lambda x: -x[1])
    return results[:8]  # 最多返回8条
