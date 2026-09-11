#!/usr/bin/env python3
"""
知乎收藏夹爬取分析工具
爬取用户所有收藏的回答/文章，智能评分筛选精华，生成HTML报告

使用方法:
    python zhihu_favorites_analyzer.py https://www.zhihu.com/people/xxx --cookie "你的z_c0值"
    python zhihu_favorites_analyzer.py xxx --cookie-file cookie.txt

依赖:
    pip install requests jieba beautifulsoup4
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime

import requests

# ============================================================
# 配置
# ============================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.zhihu.com",
    "Accept": "application/json, text/plain, */*",
}

# 停用词（精简版）
STOP_WORDS = {
    "的", "了", "是", "在", "和", "有", "就", "都", "而", "及", "与", "之", "也",
    "不", "很", "还", "这", "那", "我", "你", "他", "她", "它", "什么", "怎么",
    "一个", "一点", "全部", "看看", "我们", "你们", "他们", "这个", "那个",
    "可以", "已经", "还是", "就是", "不是", "没有", "自己", "一下", "一些",
    "一种", "一样", "真的", "太", "最", "更", "非常", "特别", "比较", "其实",
    "然后", "因为", "所以", "如果", "但是", "而且", "或者", "虽然", "不过",
    "以及", "等等", "之类", "这么", "那么", "怎样", "咋样", "啥", "呗", "呀",
    "啊", "吧", "呢", "嘛", "哦", "哈", "嘿", "哎", "嗯", "说", "做", "要",
    "会", "能", "对", "去", "来", "给", "从", "到", "被", "把", "让", "用",
    "想", "看", "听", "知道", "觉得", "感觉", "应该", "可能", "大概", "也许",
    "似乎", "好像", "比如", "例如", "关于", "对于", "通过", "根据", "为了",
    "由于", "随着", "按照", "经过", "除了", "只有", "只要", "不仅", "不但",
    "既", "又", "与其", "不如", "宁可", "即使", "无论", "不管", "总是", "从来",
    "一直", "曾经", "刚刚", "正在", "将要", "马上", "立刻", "顿时", "忽然",
    "渐渐", "逐渐", "慢慢", "悄悄", "明明", "偏偏", "简直", "几乎", "差不多",
    "或许", "恐怕", "难道", "究竟", "到底", "毕竟", "居然", "竟然", "果然",
    "幸亏", "难怪", "原来", "事实上", "实际上", "当然", "自然", "显然", "明显",
    "确实", "的确", "实在", "根本", "完全", "所有", "一切", "整个", "每", "各",
    "某", "另", "其他", "另外", "其余", "剩下", "以上", "以下", "以内", "以外",
    "之前", "之后", "以前", "以后", "上面", "下面", "里面", "外面", "前面", "后面",
    "左边", "右边", "中间", "旁边", "附近", "周围", "到处", "处处", "哪里", "这儿",
    "那儿", "这里", "那里", "此时", "此刻", "当时", "那时", "今天", "明天", "昨天",
    "现在", "过去", "将来", "未来", "刚才", "终于", "最终", "最后", "结果", "总之",
    "因此", "因而", "从而", "以致", "以至", "于是", "接着", "随后", "首先", "其次",
    "再次", "第一", "第二", "第三", "一方面", "另一方面", "知乎", "zhihu", "问题",
    "回答", "答案", "评论", "用户", "作者", "编辑", "发布", "更新", "赞同", "喜欢",
    "收藏", "分享", "举报", "折叠", "删除", "修改", "建议", "感谢", "关注", "粉丝",
    "文章", "想法", "专栏", "话题", "圈子", "直播", "视频", "图片", "文字", "链接",
    "引用", "回复", "点赞", "点踩", "反对", "没有帮助", "本人", "个人",
    "认为", "觉得", "表示", "指出", "说明", "提到", "讲", "问", "答", "写", "读",
    "学", "教", "买", "卖", "吃", "喝", "玩", "睡", "走", "跑", "飞", "开", "关",
    "上", "下", "左", "右", "前", "后", "里", "外", "中", "内", "旁", "间", "底",
    "顶", "边", "面", "头", "尾", "始", "终", "初", "末", "早", "晚", "先", "后",
    "新", "旧", "好", "坏", "大", "小", "多", "少", "高", "低", "长", "短", "远",
    "近", "快", "慢", "强", "弱", "厚", "薄", "重", "轻", "难", "易", "真", "假",
    "对", "错", "是", "非", "正", "反", "男", "女", "老", "少", "胖", "瘦", "美",
    "丑", "善", "恶", "穷", "富", "贵", "贱", "忙", "闲", "累", "饿", "饱",
    "渴", "困", "醒", "病", "健", "死", "活", "生", "灭", "成", "败", "胜", "负",
    "赢", "输", "得", "失", "增", "减", "升", "降", "涨", "跌", "进", "出", "入",
    "存", "取", "借", "贷", "租", "售", "赚", "赔", "花", "省", "费", "用", "废",
    "弃", "留", "扔", "丢", "找", "寻", "追", "赶", "等", "待", "停", "行", "坐",
    "站", "躺", "趴", "蹲", "跪", "爬", "跳", "游", "骑", "驾", "乘", "搬", "运",
    "送", "拿", "提", "扛", "背", "抱", "推", "拉", "拽", "拖", "抬", "举", "放",
    "摆", "挂", "贴", "装", "拆", "拼", "凑", "组", "建", "造", "制", "作", "画",
    "涂", "抹", "剪", "切", "割", "砍", "劈", "砸", "敲", "打", "击", "拍", "摸",
    "抓", "握", "捏", "掐", "揉", "搓", "洗", "擦", "扫", "拖", "刷", "冲", "泡",
    "煮", "炒", "烤", "炸", "蒸", "炖", "焖", "煲", "拌", "腌", "酱", "醋", "盐",
    "糖", "油", "酒", "茶", "水", "饭", "菜", "肉", "鱼", "鸡", "鸭", "鹅", "猪",
    "牛", "羊", "狗", "猫", "鸟", "虫", "花", "草", "树", "林", "山", "河", "湖",
    "海", "江", "洋", "云", "雨", "雪", "风", "雷", "电", "日", "月", "星", "天",
    "地", "人", "口", "手", "脚", "眼", "耳", "鼻", "舌", "牙", "心", "肝", "脾",
    "肺", "肾", "胃", "肠", "脑", "骨", "肉", "皮", "毛", "血", "汗", "泪", "精",
    "气", "神", "魂", "魄", "梦", "想", "思", "念", "意", "志", "情", "感", "爱",
    "恨", "喜", "怒", "哀", "乐", "忧", "愁", "烦", "闷", "慌", "急", "躁",
    "平静", "安静", "热闹", "吵", "乱", "整齐", "干净", "脏", "臭", "香", "甜",
    "酸", "苦", "辣", "咸", "淡", "浓", "稀", "干", "湿", "软", "硬", "滑", "涩",
    "亮", "暗", "明", "黑", "白", "红", "黄", "蓝", "绿", "紫", "灰", "粉", "橙",
    "色", "彩", "光", "影", "声", "音", "响", "味", "觉", "感", "知", "识", "理",
    "法", "道", "术", "器", "具", "物", "事", "情", "景", "象", "现", "状", "态",
    "势", "形", "式", "样", "种", "类", "别", "级", "等", "层", "次", "批", "群",
    "堆", "束", "串", "排", "列", "行", "队", "伍", "组", "班", "团", "社", "会",
    "国", "家", "市", "区", "县", "镇", "乡", "村", "街", "路", "巷", "楼", "房",
    "屋", "室", "厅", "厨", "卫", "门", "窗", "墙", "顶", "板", "桌", "椅", "床",
    "柜", "架", "箱", "包", "袋", "瓶", "罐", "盒", "盘", "碗", "筷", "勺", "刀",
    "叉", "杯", "壶", "锅", "盆", "桶", "篮", "网", "绳", "线", "带", "链", "环",
    "圈", "钉", "螺丝", "胶", "漆", "墨", "笔", "纸", "书", "本", "册", "页", "张",
    "片", "块", "条", "根", "支", "枝", "棵", "株", "朵", "颗", "粒", "滴",
}

# 精华关键词
QUALITY_KEYWORDS = {
    "首先", "其次", "最后", "总结", "综上", "因此", "所以", "因为", "原因",
    "分析", "研究", "数据", "实验", "证明", "证据", "例子", "案例", "经验",
    "建议", "方法", "步骤", "流程", "技巧", "攻略", "指南", "教程", "原理",
    "本质", "核心", "关键", "重点", "注意", "提醒", "警告", "对比", "比较",
    "区别", "相同", "不同", "优势", "劣势", "优点", "缺点", "好处", "坏处",
    "影响", "作用", "功能", "效果", "结果", "结论", "观点", "看法", "态度",
    "立场", "角度", "层面", "维度", "层次", "深度", "广度", "高度", "程度",
    "专业", "深入", "详细", "全面", "系统", "完整", "清晰", "明确", "具体",
    "实际", "实用", "有效", "靠谱", "真实", "客观", "理性", "逻辑", "严谨",
    "干货", "精华", "重点", "核心", "本质", "底层", "底层逻辑", "底层思维",
}


# ============================================================
# 工具函数
# ============================================================

def print_progress(current, total, prefix=""):
    percent = current / total * 100 if total > 0 else 0
    bar_len = 30
    filled = int(bar_len * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r{prefix} [{bar}] {current}/{total} ({percent:.1f}%)", end="", flush=True)
    if current >= total:
        print()


def safe_get(url, params=None, cookies=None, retries=3, delay=2):
    for i in range(retries):
        try:
            resp = requests.get(url, params=params, headers=HEADERS,
                                cookies=cookies, timeout=15)
            if resp.status_code == 401:
                print("\n❌ 401未授权，请检查Cookie是否正确")
                return None
            if resp.status_code == 429:
                print(f"\n⚠️  请求过于频繁，等待{delay*2}秒后重试...")
                time.sleep(delay * 2)
                continue
            resp.raise_for_status()
            return resp
        except Exception as e:
            if i < retries - 1:
                time.sleep(delay)
            else:
                print(f"\n⚠️  请求失败: {e}")
                return None


def extract_user_token(input_str):
    """从用户主页链接提取url_token"""
    match = re.search(r"people/([^/]+)", input_str)
    if match:
        return match.group(1)
    return input_str.strip()


def clean_html(html_text):
    if not html_text:
        return ""
    text = re.sub(r"<[^>]+>", "", html_text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_cookie(cookie_str=None, cookie_file=None):
    cookies = {}
    if cookie_file and os.path.exists(cookie_file):
        with open(cookie_file, "r", encoding="utf-8") as f:
            cookie_str = f.read().strip()
    if cookie_str:
        if "=" in cookie_str:
            for pair in cookie_str.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    cookies[k.strip()] = v.strip()
        else:
            cookies["z_c0"] = cookie_str.strip()
    return cookies


# ============================================================
# 知乎API
# ============================================================

def get_user_info(url_token, cookies=None):
    """获取用户信息"""
    url = f"https://www.zhihu.com/api/v4/people/{url_token}"
    resp = safe_get(url, cookies=cookies)
    if not resp:
        return None
    data = resp.json()
    return {
        "id": data.get("id", ""),
        "url_token": data.get("url_token", ""),
        "name": data.get("name", ""),
        "headline": data.get("headline", ""),
        "follower_count": data.get("follower_count", 0),
        "following_count": data.get("following_count", 0),
        "answer_count": data.get("answer_count", 0),
        "articles_count": data.get("articles_count", 0),
        "favorite_count": data.get("favorite_count", 0),
        "voteup_count": data.get("voteup_count", 0),
    }


def get_collections(url_token, cookies=None):
    """获取用户收藏夹列表"""
    all_collections = []
    url = f"https://www.zhihu.com/api/v4/people/{url_token}/collections"
    offset = 0
    limit = 20

    while True:
        params = {"limit": limit, "offset": offset}
        resp = safe_get(url, params=params, cookies=cookies)
        if not resp:
            break
        data = resp.json()
        collections = data.get("data", [])
        if not collections:
            break

        for c in collections:
            all_collections.append({
                "id": c["id"],
                "title": c.get("title", ""),
                "description": c.get("description", ""),
                "item_count": c.get("item_count", 0),
                "follower_count": c.get("follower_count", 0),
                "created_time": datetime.fromtimestamp(c.get("created_time", 0)).strftime("%Y-%m-%d"),
                "updated_time": datetime.fromtimestamp(c.get("updated_time", 0)).strftime("%Y-%m-%d"),
            })

        if data.get("paging", {}).get("is_end", True):
            break
        offset += limit
        time.sleep(0.5)

    return all_collections


def get_collection_items(collection_id, cookies=None, max_items=500):
    """获取收藏夹内容"""
    items = []
    url = f"https://www.zhihu.com/api/v4/collections/{collection_id}/items"
    offset = 0
    limit = 20

    while len(items) < max_items:
        params = {"limit": limit, "offset": offset}
        resp = safe_get(url, params=params, cookies=cookies)
        if not resp:
            break
        data = resp.json()
        batch = data.get("data", [])
        if not batch:
            break

        for item in batch:
            content = item.get("content", {})
            item_type = content.get("type", "unknown")

            if item_type == "answer":
                author = content.get("author", {})
                question = content.get("question", {})
                items.append({
                    "type": "回答",
                    "id": content.get("id", ""),
                    "title": question.get("title", ""),
                    "author": author.get("name", "匿名用户"),
                    "author_followers": author.get("follower_count", 0),
                    "content": clean_html(content.get("content", "")),
                    "excerpt": content.get("excerpt", ""),
                    "voteup_count": content.get("voteup_count", 0),
                    "comment_count": content.get("comment_count", 0),
                    "created_time": datetime.fromtimestamp(content.get("created_time", 0)).strftime("%Y-%m-%d"),
                    "updated_time": datetime.fromtimestamp(content.get("updated_time", 0)).strftime("%Y-%m-%d"),
                    "url": f"https://www.zhihu.com/question/{question.get('id', '')}/answer/{content.get('id', '')}",
                    "collection_time": datetime.fromtimestamp(item.get("created", 0)).strftime("%Y-%m-%d %H:%M"),
                })
            elif item_type == "article":
                author = content.get("author", {})
                items.append({
                    "type": "文章",
                    "id": content.get("id", ""),
                    "title": content.get("title", ""),
                    "author": author.get("name", "匿名用户"),
                    "author_followers": author.get("follower_count", 0),
                    "content": clean_html(content.get("content", "")),
                    "excerpt": content.get("excerpt", ""),
                    "voteup_count": content.get("voteup_count", 0),
                    "comment_count": content.get("comment_count", 0),
                    "created_time": datetime.fromtimestamp(content.get("created", 0)).strftime("%Y-%m-%d"),
                    "updated_time": datetime.fromtimestamp(content.get("updated", 0)).strftime("%Y-%m-%d"),
                    "url": f"https://zhuanlan.zhihu.com/p/{content.get('id', '')}",
                    "collection_time": datetime.fromtimestamp(item.get("created", 0)).strftime("%Y-%m-%d %H:%M"),
                })

        if data.get("paging", {}).get("is_end", True):
            break
        offset += limit
        time.sleep(0.5)

    return items


# ============================================================
# 智能评分
# ============================================================

def calculate_quality_score(item, all_items):
    import math

    max_votes = max(i["voteup_count"] for i in all_items) if all_items else 1
    max_comments = max(i["comment_count"] for i in all_items) if all_items else 1
    max_followers = max(i["author_followers"] for i in all_items) if all_items else 1

    # 赞同数
    vote_score = min(math.log1p(item["voteup_count"]) / math.log1p(max_votes) * 100, 100) if max_votes > 0 else 0

    # 评论数
    comment_score = min(math.log1p(item["comment_count"]) / math.log1p(max_comments) * 100, 100) if max_comments > 0 else 0

    # 内容长度
    length = len(item["content"])
    if length < 100:
        length_score = length / 100 * 40
    elif length < 500:
        length_score = 40 + (length - 100) / 400 * 30
    elif length <= 5000:
        length_score = 70 + (length - 500) / 4500 * 30
    elif length <= 15000:
        length_score = 100 - (length - 5000) / 10000 * 20
    else:
        length_score = max(80 - (length - 15000) / 10000 * 10, 50)

    # 关键词密度
    content = item["content"]
    keyword_hits = sum(1 for kw in QUALITY_KEYWORDS if kw in content)
    keyword_density = keyword_hits / max(length / 100, 1)
    keyword_score = min(keyword_density * 15, 100)

    # 作者影响力
    author_score = min(math.log1p(item["author_followers"]) / math.log1p(max_followers) * 100, 100) if max_followers > 0 else 0

    # 时效性（收藏时间越新越好）
    try:
        coll_date = datetime.strptime(item["collection_time"].split(" ")[0], "%Y-%m-%d")
        days_ago = (datetime.now() - coll_date).days
        if days_ago < 30:
            time_score = 100
        elif days_ago < 180:
            time_score = 100 - (days_ago - 30) / 150 * 30
        else:
            time_score = max(70 - (days_ago - 180) / 365 * 20, 30)
    except Exception:
        time_score = 60

    total_score = (
        vote_score * 0.35 +
        comment_score * 0.15 +
        length_score * 0.15 +
        keyword_score * 0.15 +
        author_score * 0.10 +
        time_score * 0.10
    )

    return {
        "total": round(total_score, 1),
        "vote_score": round(vote_score, 1),
        "comment_score": round(comment_score, 1),
        "length_score": round(length_score, 1),
        "keyword_score": round(keyword_score, 1),
        "author_score": round(author_score, 1),
        "time_score": round(time_score, 1),
    }


# ============================================================
# 数据分析
# ============================================================

def get_word_frequency(texts, top_n=30):
    try:
        import jieba
        all_words = []
        for text in texts:
            if not text:
                continue
            text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", " ", text)
            words = jieba.lcut(text)
            for w in words:
                w = w.strip()
                if len(w) > 1 and w not in STOP_WORDS and not w.isdigit():
                    all_words.append(w)
        counter = Counter(all_words)
        return counter.most_common(top_n)
    except ImportError:
        print("⚠️  未安装jieba，词频分析已跳过")
        return []


def analyze_items(items):
    if not items:
        return {}

    all_texts = [i["content"] for i in items]
    all_titles = [i["title"] for i in items]

    word_freq = get_word_frequency(all_texts)
    title_word_freq = get_word_frequency(all_titles, top_n=20)

    # 类型分布
    type_dist = Counter(i["type"] for i in items)

    # 作者分布
    author_dist = Counter(i["author"] for i in items)
    top_authors = author_dist.most_common(15)

    # 收藏时间分布（按月）
    month_dist = Counter()
    for i in items:
        try:
            month = i["collection_time"][:7]
            month_dist[month] += 1
        except Exception:
            pass
    month_dist = dict(sorted(month_dist.items()))

    # 赞同数分布
    vote_bins = {"0-10": 0, "10-100": 0, "100-1000": 0, "1000-10000": 0, ">10000": 0}
    for i in items:
        v = i["voteup_count"]
        if v < 10:
            vote_bins["0-10"] += 1
        elif v < 100:
            vote_bins["10-100"] += 1
        elif v < 1000:
            vote_bins["100-1000"] += 1
        elif v < 10000:
            vote_bins["1000-10000"] += 1
        else:
            vote_bins[">10000"] += 1

    return {
        "total": len(items),
        "word_freq": word_freq,
        "title_word_freq": title_word_freq,
        "type_dist": dict(type_dist),
        "top_authors": top_authors,
        "month_dist": month_dist,
        "vote_bins": vote_bins,
    }


# ============================================================
# HTML报告生成
# ============================================================

def generate_html_report(user_info, collections, all_items, analysis, output_path):
    # 精华内容TOP15
    top_items = sorted(all_items, key=lambda x: x["quality_score"]["total"], reverse=True)[:15]
    # 高赞内容
    top_voted = sorted(all_items, key=lambda x: x["voteup_count"], reverse=True)[:10]

    # 精华内容HTML
    top_items_html = ""
    for i, item in enumerate(top_items, 1):
        score = item["quality_score"]
        excerpt = item["content"][:400] + "..." if len(item["content"]) > 400 else item["content"]
        type_color = "#0066ff" if item["type"] == "回答" else "#52c41a"
        top_items_html += f"""
        <div class="item-card">
            <div class="item-rank">#{i}</div>
            <div class="item-body">
                <div class="item-header">
                    <span class="item-type" style="background:{type_color}">{item['type']}</span>
                    <span class="item-title">{item['title']}</span>
                    <span class="item-score">精华评分: {score['total']}</span>
                </div>
                <div class="item-meta">
                    <span>👤 {item['author']}</span>
                    <span>👍 {item['voteup_count']:,}</span>
                    <span>💬 {item['comment_count']}</span>
                    <span>📝 {len(item['content'])}字</span>
                    <span>📅 收藏于 {item['collection_time']}</span>
                    <a href="{item['url']}" target="_blank">🔗 原文链接</a>
                </div>
                <div class="item-score-bar">
                    <span title="赞同数">👍{score['vote_score']}</span>
                    <span title="评论数">💬{score['comment_score']}</span>
                    <span title="内容长度">📏{score['length_score']}</span>
                    <span title="关键词密度">🔑{score['keyword_score']}</span>
                    <span title="作者影响力">👤{score['author_score']}</span>
                    <span title="收藏时效">⏰{score['time_score']}</span>
                </div>
                <div class="item-content">{excerpt}</div>
            </div>
        </div>
        """

    # 收藏夹列表HTML
    collections_html = ""
    for c in collections:
        collections_html += f"""
        <div class="collection-card">
            <div class="collection-title">📁 {c['title']}</div>
            <div class="collection-meta">
                <span>📝 {c['item_count']} 条内容</span>
                <span>👥 {c['follower_count']} 关注者</span>
                <span>📅 创建于 {c['created_time']}</span>
            </div>
            <div class="collection-desc">{c['description'] or '暂无描述'}</div>
        </div>
        """

    word_freq = analysis.get("word_freq", [])
    title_word_freq = analysis.get("title_word_freq", [])
    type_dist = analysis.get("type_dist", {})
    top_authors = analysis.get("top_authors", [])
    month_dist = analysis.get("month_dist", {})
    vote_bins = analysis.get("vote_bins", {})

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>知乎收藏分析 - {user_info['name']}</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
            background: #f0f2f5;
            color: #333;
        }}
        .header {{
            background: linear-gradient(135deg, #0066ff 0%, #0084ff 50%, #00a6ff 100%);
            color: white;
            padding: 30px 40px;
        }}
        .header h1 {{ font-size: 24px; margin-bottom: 8px; }}
        .header .headline {{ font-size: 14px; opacity: 0.9; margin-bottom: 12px; }}
        .user-meta {{ display: flex; gap: 24px; flex-wrap: wrap; font-size: 14px; opacity: 0.95; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .stat-card {{
            background: white;
            border-radius: 10px;
            padding: 18px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
            text-align: center;
        }}
        .stat-card .label {{ font-size: 13px; color: #999; margin-bottom: 6px; }}
        .stat-card .value {{ font-size: 24px; font-weight: 600; color: #0066ff; }}
        .stat-card .sub {{ font-size: 12px; color: #bbb; margin-top: 4px; }}
        .tabs {{
            display: flex;
            gap: 4px;
            background: white;
            padding: 8px;
            border-radius: 10px;
            margin-bottom: 16px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
            flex-wrap: wrap;
        }}
        .tab {{
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
            color: #666;
        }}
        .tab:hover {{ background: #f5f5f5; }}
        .tab.active {{ background: #0066ff; color: white; font-weight: 500; }}
        .chart-container {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
            margin-bottom: 24px;
        }}
        .chart-container h3 {{
            font-size: 16px;
            margin-bottom: 16px;
            padding-left: 10px;
            border-left: 3px solid #0066ff;
        }}
        .chart {{ width: 100%; height: 400px; }}
        .hidden {{ display: none; }}
        .item-card {{
            display: flex;
            gap: 16px;
            padding: 20px;
            border-bottom: 1px solid #f0f0f0;
        }}
        .item-rank {{
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #0066ff, #00a6ff);
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 14px;
            flex-shrink: 0;
        }}
        .item-body {{ flex: 1; min-width: 0; }}
        .item-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;
            flex-wrap: wrap;
        }}
        .item-type {{
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }}
        .item-title {{ font-weight: 600; font-size: 15px; color: #333; flex: 1; }}
        .item-score {{
            background: linear-gradient(135deg, #ff6b6b, #ffa502);
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 13px;
            font-weight: 600;
        }}
        .item-meta {{
            display: flex;
            gap: 16px;
            font-size: 13px;
            color: #888;
            margin-bottom: 8px;
            flex-wrap: wrap;
        }}
        .item-meta a {{ color: #0066ff; text-decoration: none; }}
        .item-score-bar {{
            display: flex;
            gap: 8px;
            margin-bottom: 10px;
            flex-wrap: wrap;
        }}
        .item-score-bar span {{
            background: #f0f7ff;
            color: #0066ff;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
        }}
        .item-content {{
            font-size: 14px;
            line-height: 1.8;
            color: #555;
            display: -webkit-box;
            -webkit-line-clamp: 4;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}
        .collection-card {{
            padding: 16px;
            border-bottom: 1px solid #f0f0f0;
        }}
        .collection-title {{ font-size: 16px; font-weight: 600; margin-bottom: 8px; color: #333; }}
        .collection-meta {{ display: flex; gap: 16px; font-size: 13px; color: #888; margin-bottom: 6px; flex-wrap: wrap; }}
        .collection-desc {{ font-size: 13px; color: #999; }}
        .insight-box {{
            background: linear-gradient(135deg, #e6f4ff 0%, #f0f5ff 100%);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 24px;
            border-left: 4px solid #0066ff;
        }}
        .insight-box h4 {{ font-size: 15px; margin-bottom: 12px; color: #0066ff; }}
        .insight-box ul {{ padding-left: 20px; }}
        .insight-box li {{ margin-bottom: 8px; font-size: 14px; line-height: 1.6; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📚 {user_info['name']} 的知乎收藏分析</h1>
        <div class="headline">{user_info['headline']}</div>
        <div class="user-meta">
            <span>👥 {user_info['follower_count']:,} 粉丝</span>
            <span>✅ {user_info['following_count']:,} 关注</span>
            <span>📝 {user_info['answer_count']:,} 回答</span>
            <span>📄 {user_info['articles_count']:,} 文章</span>
            <span>📁 {user_info['favorite_count']:,} 收藏夹</span>
            <span>👍 {user_info['voteup_count']:,} 获赞</span>
        </div>
    </div>

    <div class="container">
        <div class="stats-grid">
            <div class="stat-card"><div class="label">收藏夹数量</div><div class="value">{len(collections)}</div><div class="sub">个收藏夹</div></div>
            <div class="stat-card"><div class="label">收藏内容</div><div class="value">{analysis['total']}</div><div class="sub">条回答/文章</div></div>
            <div class="stat-card"><div class="label">精华内容</div><div class="value">{len(top_items)}</div><div class="sub">智能筛选TOP15</div></div>
            <div class="stat-card"><div class="label">最高赞</div><div class="value">{top_voted[0]['voteup_count']:,}</div><div class="sub">{top_voted[0]['author']}</div></div>
            <div class="stat-card"><div class="label">最热关键词</div><div class="value" style="font-size:18px;">{word_freq[0][0] if word_freq else '无'}</div><div class="sub">{word_freq[0][1] if word_freq else 0}次</div></div>
        </div>

        <div class="insight-box">
            <h4>🎯 收藏分析洞察</h4>
            <ul>
                <li>📌 收藏内容最热关键词：「<strong>{word_freq[0][0] if word_freq else '无'}</strong>」（{word_freq[0][1] if word_freq else 0}次）</li>
                <li>📝 标题最热词：「<strong>{title_word_freq[0][0] if title_word_freq else '无'}</strong>」（{title_word_freq[0][1] if title_word_freq else 0}次）</li>
                <li>🏆 精华收藏第一名：<strong>{top_items[0]['title']}</strong>（评分 {top_items[0]['quality_score']['total']}，{top_items[0]['voteup_count']:,}赞）</li>
                <li>👤 收藏最多的作者：<strong>{top_authors[0][0] if top_authors else '无'}</strong>（{top_authors[0][1] if top_authors else 0}篇）</li>
                <li>📊 内容类型：{type_dist.get('回答', 0)}篇回答 + {type_dist.get('文章', 0)}篇文章</li>
            </ul>
        </div>

        <div class="tabs">
            <div class="tab active" data-tab="essence">🏆 精华收藏</div>
            <div class="tab" data-tab="wordfreq">🔤 内容词频</div>
            <div class="tab" data-tab="titlefreq">📝 标题词频</div>
            <div class="tab" data-tab="authors">👤 作者分布</div>
            <div class="tab" data-tab="month">📅 收藏时间</div>
            <div class="tab" data-tab="type">📊 类型分布</div>
            <div class="tab" data-tab="vote">👍 赞同分布</div>
            <div class="tab" data-tab="collections">📁 收藏夹列表</div>
            <div class="tab" data-tab="topvoted">📈 高赞内容</div>
        </div>

        <div class="chart-container" id="panel-essence">
            <h3>🏆 智能筛选精华收藏TOP15（多维度评分）</h3>
            {top_items_html}
        </div>

        <div class="chart-container hidden" id="panel-wordfreq">
            <h3>收藏内容关键词TOP30</h3>
            <div class="chart" id="chart-wordfreq"></div>
        </div>

        <div class="chart-container hidden" id="panel-titlefreq">
            <h3>收藏标题关键词TOP20</h3>
            <div class="chart" id="chart-titlefreq"></div>
        </div>

        <div class="chart-container hidden" id="panel-authors">
            <h3>收藏最多的作者TOP15</h3>
            <div class="chart" id="chart-authors"></div>
        </div>

        <div class="chart-container hidden" id="panel-month">
            <h3>收藏时间分布（按月）</h3>
            <div class="chart" id="chart-month"></div>
        </div>

        <div class="chart-container hidden" id="panel-type">
            <h3>内容类型分布</h3>
            <div class="chart" id="chart-type"></div>
        </div>

        <div class="chart-container hidden" id="panel-vote">
            <h3>赞同数分布</h3>
            <div class="chart" id="chart-vote"></div>
        </div>

        <div class="chart-container hidden" id="panel-collections">
            <h3>我的收藏夹列表</h3>
            {collections_html}
        </div>

        <div class="chart-container hidden" id="panel-topvoted">
            <h3>高赞收藏TOP10</h3>
            <div class="chart" id="chart-topvoted"></div>
        </div>
    </div>

    <script>
        document.querySelectorAll('.tab').forEach(tab => {{
            tab.addEventListener('click', () => {{
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                const name = tab.dataset.tab;
                ['essence','wordfreq','titlefreq','authors','month','type','vote','collections','topvoted'].forEach(n => {{
                    document.getElementById('panel-' + n).classList.toggle('hidden', n !== name);
                }});
                setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
            }});
        }});

        const wordFreqData = {json.dumps([[w,c] for w,c in word_freq], ensure_ascii=False)};
        if (wordFreqData.length > 0) {{
            const chart1 = echarts.init(document.getElementById('chart-wordfreq'));
            chart1.setOption({{
                tooltip: {{ trigger: 'axis', formatter: '{{b}}: {{c}}次' }},
                grid: {{ left: 100, right: 40, top: 20, bottom: 30 }},
                xAxis: {{ type: 'value', name: '出现次数' }},
                yAxis: {{ type: 'category', data: wordFreqData.map(w=>w[0]).reverse(), axisLabel: {{fontSize:11}} }},
                series: [{{
                    data: wordFreqData.map(w=>w[1]).reverse(),
                    type: 'bar',
                    itemStyle: {{
                        color: new echarts.graphic.LinearGradient(0,0,1,0,[
                            {{offset:0,color:'#0066ff'}},{{offset:1,color:'#00a6ff'}}
                        ]),
                        borderRadius: [0,4,4,0]
                    }}
                }}],
                dataZoom: [{{type:'slider',yAxisIndex:0,orient:'vertical',right:10,width:15}}]
            }});
        }}

        const titleFreqData = {json.dumps([[w,c] for w,c in title_word_freq], ensure_ascii=False)};
        if (titleFreqData.length > 0) {{
            const chart2 = echarts.init(document.getElementById('chart-titlefreq'));
            chart2.setOption({{
                tooltip: {{ trigger: 'axis', formatter: '{{b}}: {{c}}次' }},
                grid: {{ left: 100, right: 40, top: 20, bottom: 30 }},
                xAxis: {{ type: 'value', name: '出现次数' }},
                yAxis: {{ type: 'category', data: titleFreqData.map(w=>w[0]).reverse(), axisLabel: {{fontSize:11}} }},
                series: [{{
                    data: titleFreqData.map(w=>w[1]).reverse(),
                    type: 'bar',
                    itemStyle: {{
                        color: new echarts.graphic.LinearGradient(0,0,1,0,[
                            {{offset:0,color:'#ff6b6b'}},{{offset:1,color:'#ffa502'}}
                        ]),
                        borderRadius: [0,4,4,0]
                    }}
                }}]
            }});
        }}

        const authorsData = {json.dumps([[a,c] for a,c in top_authors], ensure_ascii=False)};
        const chart3 = echarts.init(document.getElementById('chart-authors'));
        chart3.setOption({{
            tooltip: {{ trigger: 'axis', formatter: '{{b}}: {{c}}篇' }},
            grid: {{ left: 120, right: 40, top: 20, bottom: 30 }},
            xAxis: {{ type: 'value', name: '收藏篇数' }},
            yAxis: {{ type: 'category', data: authorsData.map(d=>d[0]).reverse(), axisLabel: {{fontSize:11}} }},
            series: [{{
                data: authorsData.map(d=>d[1]).reverse(),
                type: 'bar',
                itemStyle: {{
                    color: new echarts.graphic.LinearGradient(0,0,1,0,[
                        {{offset:0,color:'#52c41a'}},{{offset:1,color:'#95de64'}}
                    ]),
                    borderRadius: [0,4,4,0]
                }}
            }}]
        }});

        const monthData = {json.dumps(month_dist, ensure_ascii=False)};
        const chart4 = echarts.init(document.getElementById('chart-month'));
        chart4.setOption({{
            tooltip: {{ trigger: 'axis', formatter: '{{b}}: {{c}}条' }},
            grid: {{ left: 50, right: 30, top: 30, bottom: 50 }},
            xAxis: {{ type: 'category', data: Object.keys(monthData), axisLabel: {{rotate: 45, fontSize: 11}} }},
            yAxis: {{ type: 'value', name: '收藏数' }},
            series: [{{
                data: Object.values(monthData),
                type: 'line',
                smooth: true,
                symbol: 'circle',
                symbolSize: 6,
                itemStyle: {{ color: '#0066ff' }},
                areaStyle: {{
                    color: new echarts.graphic.LinearGradient(0,0,0,1,[
                        {{offset:0,color:'rgba(0,102,255,0.3)'}},
                        {{offset:1,color:'rgba(0,102,255,0.05)'}}
                    ])
                }}
            }}]
        }});

        const typeData = {json.dumps(type_dist, ensure_ascii=False)};
        const chart5 = echarts.init(document.getElementById('chart-type'));
        chart5.setOption({{
            tooltip: {{ trigger: 'item', formatter: '{{b}}: {{c}}篇 ({{d}}%)' }},
            legend: {{ bottom: 10 }},
            series: [{{
                type: 'pie',
                radius: ['40%','70%'],
                center: ['50%','45%'],
                itemStyle: {{ borderRadius: 8, borderColor: '#fff', borderWidth: 2 }},
                label: {{ formatter: '{{b}}\\n{{d}}%' }},
                data: Object.entries(typeData).map(([k,v],i) => ({{
                    name: k, value: v,
                    itemStyle: {{ color: ['#0066ff','#52c41a','#ffa502','#ff6b6b'][i % 4] }}
                }}))
            }}]
        }});

        const voteData = {json.dumps(vote_bins, ensure_ascii=False)};
        const chart6 = echarts.init(document.getElementById('chart-vote'));
        chart6.setOption({{
            tooltip: {{ trigger: 'axis', formatter: '{{b}}赞同: {{c}}篇' }},
            grid: {{ left: 50, right: 30, top: 30, bottom: 40 }},
            xAxis: {{ type: 'category', data: Object.keys(voteData) }},
            yAxis: {{ type: 'value', name: '篇数' }},
            series: [{{
                data: Object.values(voteData),
                type: 'bar',
                barWidth: '50%',
                itemStyle: {{
                    color: new echarts.graphic.LinearGradient(0,0,0,1,[
                        {{offset:0,color:'#ffa502'}},{{offset:1,color:'#ff6b6b'}}
                    ]),
                    borderRadius: [4,4,0,0]
                }}
            }}]
        }});

        const topVotedData = {json.dumps([[i['title'][:20], i['voteup_count']] for i in top_voted], ensure_ascii=False)};
        const chart7 = echarts.init(document.getElementById('chart-topvoted'));
        chart7.setOption({{
            tooltip: {{ trigger: 'axis', formatter: '{{b}}: {{c}}赞同' }},
            grid: {{ left: 150, right: 40, top: 20, bottom: 30 }},
            xAxis: {{ type: 'value', name: '赞同数' }},
            yAxis: {{ type: 'category', data: topVotedData.map(d=>d[0]).reverse(), axisLabel: {{fontSize:11}} }},
            series: [{{
                data: topVotedData.map(d=>d[1]).reverse(),
                type: 'bar',
                itemStyle: {{
                    color: new echarts.graphic.LinearGradient(0,0,1,0,[
                        {{offset:0,color:'#722ed1'}},{{offset:1,color:'#b37feb'}}
                    ]),
                    borderRadius: [0,4,4,0]
                }}
            }}]
        }});

        window.addEventListener('resize', () => {{
            [chart1,chart2,chart3,chart4,chart5,chart6,chart7].forEach(c => c && c.resize());
        }});
    </script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


# ============================================================
# 主函数
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="知乎收藏夹爬取分析工具")
    parser.add_argument("user", help="知乎用户主页链接或url_token")
    parser.add_argument("--cookie", help="知乎Cookie（z_c0的值）")
    parser.add_argument("--cookie-file", help="Cookie文件路径")
    parser.add_argument("--max-items", type=int, default=500, help="每个收藏夹最多爬取内容数（默认500）")
    parser.add_argument("--output", "-o", default="", help="输出HTML文件路径")
    args = parser.parse_args()

    url_token = extract_user_token(args.user)
    print(f"🔍 用户ID: {url_token}")

    cookies = load_cookie(args.cookie, args.cookie_file)
    if not cookies.get("z_c0"):
        print("\n⚠️  未检测到有效的 z_c0 Cookie，可能无法获取完整数据")
        print("   获取方法：浏览器登录知乎 → F12 → Application → Cookies → 复制 z_c0 的值")
        print()

    # 1. 获取用户信息
    print("\n👤 获取用户信息...")
    user_info = get_user_info(url_token, cookies)
    if not user_info:
        print("❌ 无法获取用户信息，请检查用户ID和Cookie")
        sys.exit(1)
    print(f"✅ 用户: {user_info['name']}")
    print(f"✅ 粉丝: {user_info['follower_count']:,} | 回答: {user_info['answer_count']:,} | 收藏夹: {user_info['favorite_count']:,}")

    # 2. 获取收藏夹列表
    print("\n📁 获取收藏夹列表...")
    collections = get_collections(url_token, cookies)
    print(f"✅ 找到 {len(collections)} 个收藏夹")
    for c in collections:
        print(f"   - {c['title']} ({c['item_count']}条)")

    if not collections:
        print("❌ 未找到任何收藏夹")
        sys.exit(1)

    # 3. 爬取每个收藏夹的内容
    all_items = []
    for i, coll in enumerate(collections):
        print(f"\n📝 爬取收藏夹 [{i+1}/{len(collections)}]: {coll['title']}")
        items = get_collection_items(coll["id"], cookies, max_items=args.max_items)
        for item in items:
            item["collection_name"] = coll["title"]
        all_items.extend(items)
        print(f"   ✅ 爬取到 {len(items)} 条内容")
        time.sleep(1)

    print(f"\n✅ 总共爬取到 {len(all_items)} 条收藏内容")

    if not all_items:
        print("❌ 未爬取到任何内容")
        sys.exit(1)

    # 4. 智能评分
    print("\n🧠 智能评分中...")
    for item in all_items:
        item["quality_score"] = calculate_quality_score(item, all_items)

    # 5. 数据分析
    print("📊 分析数据...")
    analysis = analyze_items(all_items)

    # 6. 生成报告
    output_path = args.output or f"zhihu_favorites_{url_token}.html"
    print(f"\n📝 生成HTML报告...")
    generate_html_report(user_info, collections, all_items, analysis, output_path)

    print(f"\n🎉 分析完成！报告已保存至: {output_path}")
    print(f"   收藏夹: {len(collections)} 个")
    print(f"   收藏内容: {len(all_items)} 条")
    print(f"   用浏览器打开即可查看交互式分析报告")

    # 7. 导出CSV
    try:
        import csv
        csv_path = output_path.replace(".html", "_items.csv")
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["类型", "标题", "作者", "赞同数", "评论数", "字数", "精华评分", "收藏时间", "收藏夹", "链接"])
            for item in sorted(all_items, key=lambda x: x["quality_score"]["total"], reverse=True):
                writer.writerow([
                    item["type"], item["title"], item["author"],
                    item["voteup_count"], item["comment_count"],
                    len(item["content"]), item["quality_score"]["total"],
                    item["collection_time"], item["collection_name"], item["url"]
                ])
        print(f"   收藏数据已导出: {csv_path}")
    except Exception as e:
        print(f"   ⚠️  CSV导出失败: {e}")


if __name__ == "__main__":
    main()
