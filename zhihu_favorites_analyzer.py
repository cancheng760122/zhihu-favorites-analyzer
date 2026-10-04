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
    "x-requested-with": "fetch",
    "x-zse-93": "101_3_3.0",
}

# 全局Cookie和d_c0
ZHIHU_COOKIE = ""
ZHIHU_DC0 = ""

# DeepSeek API配置
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"


def markdown_to_html(text):
    """简单的Markdown转HTML"""
    if not text:
        return ""
    lines = text.split("\n")
    html_lines = []
    in_list = False
    in_ol = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list: html_lines.append("</ul>"); in_list = False
            if in_ol: html_lines.append("</ol>"); in_ol = False
            continue
        if stripped.startswith("#### "):
            if in_list: html_lines.append("</ul>"); in_list = False
            if in_ol: html_lines.append("</ol>"); in_ol = False
            html_lines.append(f"<h5>{stripped[5:]}</h5>"); continue
        if stripped.startswith("### "):
            if in_list: html_lines.append("</ul>"); in_list = False
            if in_ol: html_lines.append("</ol>"); in_ol = False
            html_lines.append(f"<h4>{stripped[4:]}</h4>"); continue
        if stripped.startswith("## "):
            if in_list: html_lines.append("</ul>"); in_list = False
            if in_ol: html_lines.append("</ol>"); in_ol = False
            html_lines.append(f"<h4>{stripped[3:]}</h4>"); continue
        if stripped.startswith("# "):
            if in_list: html_lines.append("</ul>"); in_list = False
            if in_ol: html_lines.append("</ol>"); in_ol = False
            html_lines.append(f"<h3>{stripped[2:]}</h3>"); continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                if in_ol: html_lines.append("</ol>"); in_ol = False
                html_lines.append("<ul>"); in_list = True
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped[2:])
            html_lines.append(f"<li>{content}</li>"); continue
        ol_match = re.match(r'^(\d+)\.\s+(.+)$', stripped)
        if ol_match:
            if not in_ol:
                if in_list: html_lines.append("</ul>"); in_list = False
                html_lines.append("<ol>"); in_ol = True
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', ol_match.group(2))
            html_lines.append(f"<li>{content}</li>"); continue
        if in_list: html_lines.append("</ul>"); in_list = False
        if in_ol: html_lines.append("</ol>"); in_ol = False
        content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
        html_lines.append(f"<p>{content}</p>")
    if in_list: html_lines.append("</ul>")
    if in_ol: html_lines.append("</ol>")
    return "\n".join(html_lines)


def deepseek_summary(api_key, user_info, collections, all_items):
    """调用DeepSeek生成收藏夹内容深度总结"""
    if not api_key:
        return None
    print("\n🤖 调用DeepSeek生成收藏夹深度总结...")

    # 准备收藏夹概览
    coll_text = ""
    for c in collections:
        coll_text += f"- {c.get('title','')}（{c.get('item_count',0)}条）\n"

    # 准备高质量内容（取评分最高的30条）
    sorted_items = sorted(all_items, key=lambda x: x.get("quality_score", {}).get("total", 0), reverse=True)[:30]
    items_text = ""
    for i, item in enumerate(sorted_items, 1):
        title = item.get("title", "")
        author = item.get("author", "")
        content = clean_html(item.get("content", ""))[:300]
        vote = item.get("voteup_count", 0)
        items_text += f"\n【收藏{i}】{title} - {author}（{vote}赞同）\n{content}\n"

    # 词频
    all_texts = [clean_html(item.get("content", "")) for item in all_items[:100]]
    word_freq = get_word_frequency(all_texts, top_n=20)
    words_text = ", ".join([f"{w}({c}次)" for w, c in word_freq])

    prompt = f"""你是一个专业的知识管理专家。请根据以下知乎用户的收藏夹数据，生成一份深度分析报告。

【用户信息】
用户名：{user_info.get('name','')}
收藏夹数量：{len(collections)}
收藏总内容数：{len(all_items)}

【收藏夹列表】
{coll_text}

【高频关键词TOP20】
{words_text}

【高质量收藏内容TOP30】{items_text}

请按以下格式生成深度分析报告（用中文，分点清晰，重点突出）：

## 一、收藏画像分析
- 这个用户的收藏内容主要集中在哪些领域？
- 反映了用户怎样的兴趣偏好和学习方向？
- 收藏内容的整体质量如何？

## 二、知识体系梳理
- 从收藏内容中可以梳理出怎样的知识体系？
- 有哪些核心主题和分支？
- 哪些领域收藏较多，哪些较少？

## 三、精华内容推荐
从收藏中挑选出5-8条最有价值的内容，说明为什么推荐。

## 四、收藏习惯分析
- 用户的收藏习惯是怎样的？（收藏时间分布、收藏夹分类等）
- 有哪些收藏了但可能没看的内容？
- 收藏夹的分类是否合理？有什么优化建议？

## 五、学习建议
- 基于用户的收藏内容，给出3-5条具体的学习建议
- 哪些内容应该优先阅读？
- 如何更好地利用这些收藏的知识？

## 六、总结
用一段话总结这个用户的收藏特点和成长方向。

要求：
1. 基于提供的信息，不要编造
2. 重点突出，不要空泛的套话
3. 给出具体可操作的建议
4. 总字数控制在1500-2500字
5. 重要信息用加粗标注"""

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 4000
        }
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=180)
        resp.raise_for_status()
        result = resp.json()
        summary = result["choices"][0]["message"]["content"]
        print(f"✅ 深度总结生成完成（约{len(summary)}字）")
        return summary
    except Exception as e:
        print(f"⚠️  DeepSeek API调用失败: {e}")
        return None


def set_zhihu_cookie(cookie):
    """设置知乎Cookie并提取d_c0"""
    global ZHIHU_COOKIE, ZHIHU_DC0
    ZHIHU_COOKIE = cookie
    HEADERS["Cookie"] = cookie
    import re
    match = re.search(r'd_c0=([^;]+)', cookie)
    if match:
        ZHIHU_DC0 = match.group(1)


def sign_zhihu_request(url_path, body=""):
    """生成知乎x-zse-96签名"""
    import hashlib
    x_zse_93 = "101_3_3.0"
    raw = f"{x_zse_93}{url_path}{body}{ZHIHU_DC0}"
    md5 = hashlib.md5(raw.encode()).hexdigest()
    return f"{x_zse_93}+{md5}"

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


def parse_time(value, fmt="%Y-%m-%d"):
    """通用时间解析：支持时间戳和ISO格式字符串"""
    if not value:
        return ""
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value).strftime(fmt)
        if isinstance(value, str):
            # 尝试数字时间戳
            try:
                return datetime.fromtimestamp(int(value)).strftime(fmt)
            except (ValueError, OSError):
                pass
            # 尝试ISO格式
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00')).strftime(fmt)
            except ValueError:
                pass
            return value
    except Exception:
        return str(value) if value else ""
    return str(value) if value else ""


def safe_get(url, params=None, cookies=None, retries=3, delay=2):
    """带重试的GET请求，自动加x-zse-96签名"""
    from urllib.parse import urlparse, urlencode
    parsed = urlparse(url)
    url_path = parsed.path
    if params:
        url_path = f"{url_path}?{urlencode(params)}"
    
    headers = dict(HEADERS)
    if ZHIHU_DC0:
        headers["x-zse-96"] = sign_zhihu_request(url_path)
    
    for i in range(retries):
        try:
            resp = requests.get(url, params=params, headers=headers,
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
    url = f"https://www.zhihu.com/api/v4/members/{url_token}"
    resp = safe_get(url, cookies=cookies)
    if not resp:
        return None
    data = resp.json()
    print(f"   调试 - 用户信息所有字段: {list(data.keys())}")
    print(f"   调试 - id: {data.get('id')}, url_token: {data.get('url_token')}")
    print(f"   调试 - 完整数据: {str(data)[:500]}")
    return {
        "id": data.get("id", ""),
        "url_token": data.get("url_token", url_token),
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
    """获取用户收藏夹列表（用playwright渲染动态页面）"""
    all_collections = []
    
    # 方法1：用playwright打开收藏夹页面，等待动态加载
    print(f"   用playwright打开收藏夹页面...")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="zh-CN",
            )
            # 设置Cookie
            if cookies:
                cookie_list = []
                for name, value in cookies.items():
                    cookie_list.append({
                        "name": name,
                        "value": value,
                        "domain": ".zhihu.com",
                        "path": "/",
                    })
                context.add_cookies(cookie_list)
            
            page = context.new_page()
            page.goto(f"https://www.zhihu.com/people/{url_token}/collections", wait_until="networkidle", timeout=30000)
            time.sleep(3)
            
            content = page.content()
            print(f"   页面长度: {len(content)}")
            
            # 从页面脚本中提取initialData
            import re
            import json
            match = re.search(r'initialData\s*=\s*({.*?})\s*;?\s*</script>', content, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    print(f"   从initialData提取到数据，keys: {list(data.keys())[:10]}")
                    if "collections" in data:
                        collections_data = data["collections"]
                        if isinstance(collections_data, dict) and "data" in collections_data:
                            collections_data = collections_data["data"]
                        for c in collections_data:
                            all_collections.append({
                                "id": c.get("id", ""),
                                "title": c.get("title", ""),
                                "description": c.get("description", ""),
                                "item_count": c.get("item_count", 0),
                                "follower_count": c.get("follower_count", 0),
                                "created_time": parse_time(c.get("created_time")),
                                "updated_time": parse_time(c.get("updated_time")),
                            })
                        print(f"   从initialData找到 {len(all_collections)} 个收藏夹")
                except Exception as e:
                    print(f"   initialData解析失败: {e}")
            
            # 从页面元素中提取
            if not all_collections:
                items = page.query_selector_all(".CollectionItem, .collection-item, [data-za-detail-view-element_name='Collection']")
                print(f"   从页面元素找到 {len(items)} 个收藏夹")
                for item in items:
                    try:
                        title = item.query_selector(".CollectionItem-title, .title, a").inner_text()
                        link = item.query_selector("a").get_attribute("href")
                        collection_id = re.search(r'collection/(\d+)', link or "").group(1) if link else ""
                        all_collections.append({
                            "id": collection_id,
                            "title": title or "",
                            "description": "",
                            "item_count": 0,
                            "follower_count": 0,
                            "created_time": "",
                            "updated_time": "",
                        })
                    except:
                        pass
            
            browser.close()
    except ImportError:
        print("   playwright未安装，跳过")
    except Exception as e:
        print(f"   playwright失败: {e}")
    
    # 方法2：尝试各种API
    if not all_collections:
        api_urls = [
            f"https://www.zhihu.com/api/v4/people/{url_token}/collections",
            f"https://www.zhihu.com/api/v4/members/{url_token}/collections",
        ]
        for api_url in api_urls:
            print(f"   尝试API: {api_url}")
            try:
                resp = requests.get(api_url, headers=HEADERS, params={"offset": 0, "limit": 20}, timeout=15)
                print(f"   状态码: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    collections = data.get("data", [])
                    if collections:
                        for c in collections:
                            all_collections.append({
                                "id": c["id"],
                                "title": c.get("title", ""),
                                "description": c.get("description", ""),
                                "item_count": c.get("item_count", 0),
                                "follower_count": c.get("follower_count", 0),
                                "created_time": parse_time(c.get("created_time")),
                                "updated_time": parse_time(c.get("updated_time")),
                            })
                        break
            except Exception as e:
                print(f"   API失败: {e}")
    
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
                    "created_time": parse_time(content.get("created_time")),
                    "updated_time": parse_time(content.get("updated_time")),
                    "url": f"https://www.zhihu.com/question/{question.get('id', '')}/answer/{content.get('id', '')}",
                    "collection_time": parse_time(item.get("created"), "%Y-%m-%d %H:%M"),
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
                    "created_time": parse_time(content.get("created")),
                    "updated_time": parse_time(content.get("updated")),
                    "url": f"https://zhuanlan.zhihu.com/p/{content.get('id', '')}",
                    "collection_time": parse_time(item.get("created"), "%Y-%m-%d %H:%M"),
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

def generate_html_report(user_info, collections, all_items, analysis, output_path, ai_summary=None):
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

    # 生成纯HTML条形图
    def make_bar_chart(data, color_start, color_end, max_width=100):
        if not data:
            return "<p style='color:#999;padding:20px;'>暂无数据</p>"
        max_val = max(v for _, v in data) if data else 1
        if max_val == 0:
            max_val = 1
        html = '<div class="bar-chart">'
        for label, value in data:
            width = (value / max_val) * max_width
            html += f'''
            <div class="bar-row">
                <div class="bar-label" title="{label}">{label}</div>
                <div class="bar-track">
                    <div class="bar-fill" style="width:{width}%;background:linear-gradient(90deg,{color_start},{color_end});"></div>
                </div>
                <div class="bar-value">{value}</div>
            </div>'''
        html += '</div>'
        return html

    wordfreq_html = make_bar_chart(word_freq[:30], '#0066ff', '#00a6ff')
    titlefreq_html = make_bar_chart(title_word_freq[:20], '#ff6b6b', '#ffa502')
    authors_html = make_bar_chart(top_authors, '#52c41a', '#95de64')

    # 收藏时间用纵向柱状图（简单HTML）
    month_html = '<div class="bar-chart" style="display:flex;align-items:flex-end;gap:8px;height:400px;padding:20px 0;">'
    max_month = max(month_dist.values()) if month_dist else 1
    for month, count in month_dist.items():
        height = (count / max_month) * 350 if max_month > 0 else 0
        month_html += f'''
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:8px;">
            <span style="font-size:13px;font-weight:600;">{count}</span>
            <div style="width:100%;height:{height}px;background:linear-gradient(180deg,#0066ff,#00a6ff);border-radius:4px 4px 0 0;min-height:4px;"></div>
            <span style="font-size:11px;color:#666;transform:rotate(-30deg);white-space:nowrap;">{month}</span>
        </div>'''
    month_html += '</div>'

    # 类型分布用简单百分比展示
    type_total = sum(type_dist.values()) if type_dist else 1
    type_html = '<div style="padding:20px;">'
    colors = ['#0066ff', '#52c41a', '#ffa502', '#ff6b6b']
    for i, (t, count) in enumerate(type_dist.items()):
        pct = (count / type_total) * 100 if type_total > 0 else 0
        type_html += f'''
        <div style="margin-bottom:16px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <span style="font-size:15px;font-weight:500;">{t}</span>
                <span style="font-size:14px;color:#666;">{count}篇 ({pct:.1f}%)</span>
            </div>
            <div style="height:24px;background:#f0f2f5;border-radius:4px;overflow:hidden;">
                <div style="width:{pct}%;height:100%;background:{colors[i % 4]};border-radius:4px;"></div>
            </div>
        </div>'''
    type_html += '</div>'

    # 赞同分布用纵向柱状图
    vote_html = '<div class="bar-chart" style="display:flex;align-items:flex-end;gap:12px;height:400px;padding:20px 0;">'
    max_vote = max(vote_bins.values()) if vote_bins else 1
    for vrange, count in vote_bins.items():
        height = (count / max_vote) * 350 if max_vote > 0 else 0
        vote_html += f'''
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:8px;">
            <span style="font-size:13px;font-weight:600;">{count}</span>
            <div style="width:100%;height:{height}px;background:linear-gradient(180deg,#ffa502,#ff6b6b);border-radius:4px 4px 0 0;min-height:4px;"></div>
            <span style="font-size:11px;color:#666;white-space:nowrap;">{vrange}</span>
        </div>'''
    vote_html += '</div>'

    # 高赞内容条形图
    top_voted_data = [(item['title'][:25], item['voteup_count']) for item in top_voted]
    topvoted_html = make_bar_chart(top_voted_data, '#722ed1', '#b37feb')

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>知乎收藏分析 - {user_info['name']}</title>
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
        .container {{ max-width: 100%; margin: 0 auto; padding: 20px 32px; }}
        /* AI深度总结样式 */
        .ai-summary {{
            background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
            border-radius: 12px;
            padding: 28px;
            margin-bottom: 24px;
            border-left: 4px solid #8b5cf6;
        }}
        .ai-summary h3 {{ font-size: 20px; margin-bottom: 16px; color: #6d28d9; display: flex; align-items: center; gap: 8px; }}
        .ai-summary h4 {{ font-size: 17px; margin: 20px 0 12px 0; color: #7c3aed; border-bottom: 2px solid #ddd6fe; padding-bottom: 6px; }}
        .ai-summary p {{ font-size: 15px; line-height: 1.9; color: #333; margin-bottom: 10px; }}
        .ai-summary ul {{ padding-left: 24px; margin-bottom: 12px; }}
        .ai-summary li {{ font-size: 15px; line-height: 1.9; color: #333; margin-bottom: 8px; }}
        .ai-summary strong {{ color: #6d28d9; }}
        .ai-badge {{ display: inline-block; background: linear-gradient(135deg, #8b5cf6, #ec4899); color: white; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 500; }}
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
        .chart {{ width: 100%; height: 650px; }}
        /* 纯HTML条形图样式 */
        .bar-chart {{ width: 100%; }}
        .bar-row {{
            display: flex;
            align-items: center;
            margin-bottom: 8px;
            gap: 12px;
        }}
        .bar-label {{
            width: 140px;
            flex-shrink: 0;
            text-align: right;
            font-size: 14px;
            color: #333;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .bar-track {{
            flex: 1;
            height: 28px;
            background: #f0f2f5;
            border-radius: 4px;
            overflow: hidden;
            position: relative;
        }}
        .bar-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }}
        .bar-value {{
            width: 60px;
            flex-shrink: 0;
            font-size: 14px;
            font-weight: 600;
            color: #333;
        }}
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

        <!-- AI深度总结 -->
        {f'''
        <div class="ai-summary">
            <h3>🤖 AI深度总结 <span class="ai-badge">DeepSeek生成</span></h3>
            {markdown_to_html(ai_summary)}
        </div>
        ''' if ai_summary else ''}

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
            {wordfreq_html}
        </div>

        <div class="chart-container hidden" id="panel-titlefreq">
            <h3>收藏标题关键词TOP20</h3>
            {titlefreq_html}
        </div>

        <div class="chart-container hidden" id="panel-authors">
            <h3>收藏最多的作者TOP15</h3>
            {authors_html}
        </div>

        <div class="chart-container hidden" id="panel-month">
            <h3>收藏时间分布（按月）</h3>
            {month_html}
        </div>

        <div class="chart-container hidden" id="panel-type">
            <h3>内容类型分布</h3>
            {type_html}
        </div>

        <div class="chart-container hidden" id="panel-vote">
            <h3>赞同数分布</h3>
            {vote_html}
        </div>

        <div class="chart-container hidden" id="panel-collections">
            <h3>我的收藏夹列表</h3>
            {collections_html}
        </div>

        <div class="chart-container hidden" id="panel-topvoted">
            <h3>高赞收藏TOP10</h3>
            {topvoted_html}
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
    parser.add_argument("--deepseek-api-key", default="", help="DeepSeek API Key（用于AI深度总结）")
    args = parser.parse_args()

    url_token = extract_user_token(args.user)
    print(f"🔍 用户ID: {url_token}")

    cookies = load_cookie(args.cookie, args.cookie_file)
    if not cookies.get("z_c0"):
        print("\n⚠️  未检测到有效的 z_c0 Cookie，可能无法获取完整数据")
        print("   获取方法：浏览器登录知乎 → F12 → Application → Cookies → 复制 z_c0 的值")
        print()
    
    # 设置完整Cookie用于x-zse-96签名
    full_cookie = args.cookie or ""
    if not full_cookie and args.cookie_file and os.path.exists(args.cookie_file):
        with open(args.cookie_file, "r", encoding="utf-8") as f:
            full_cookie = f.read().strip()
    if full_cookie:
        set_zhihu_cookie(full_cookie)
        print("✅ Cookie已设置（含x-zse-96签名）")

    # 1. 获取用户信息
    print("\n👤 获取用户信息...")
    user_info = get_user_info(url_token, cookies)
    if not user_info:
        print("❌ 无法获取用户信息，请检查用户ID和Cookie")
        sys.exit(1)
    print(f"✅ 用户: {user_info['name']}")
    print(f"✅ 粉丝: {user_info['follower_count']:,} | 回答: {user_info['answer_count']:,} | 收藏夹: {user_info['favorite_count']:,}")

    # 2. 获取收藏夹列表（用用户信息返回的真实url_token）
    print("\n📁 获取收藏夹列表...")
    real_url_token = user_info.get("url_token", url_token)
    print(f"   使用url_token: {real_url_token}")
    collections = get_collections(real_url_token, cookies)
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

    # 5.5 DeepSeek AI深度总结
    ai_summary = None
    if args.deepseek_api_key:
        ai_summary = deepseek_summary(args.deepseek_api_key, user_info, collections, all_items)

    # 6. 生成报告
    date_str = datetime.now().strftime("%Y-%m-%d")
    user_name = user_info.get("name", url_token)
    task_dir = f"output/{date_str}_favorites_{user_name}"
    os.makedirs(task_dir, exist_ok=True)
    output_path = args.output or f"{task_dir}/report.html"
    print(f"\n📝 生成HTML报告...")
    generate_html_report(user_info, collections, all_items, analysis, output_path, ai_summary=ai_summary)

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
