#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全球风险日报自动生成脚本
========================
- 计算时间窗口：上一个中国工作日 12:00 ~ 今日 11:00（北京时间）
- 新闻检索：免费 GDELT Doc 2.0（全球 + 中文权威源域名过滤）+ 中文 RSS 补充
- 调用 OpenAI 兼容的 LLM（推荐 DeepSeek，便宜）整理成结构化 Markdown
- 资料来源以【文内可点击链接】形式标注，方便复查
- 生成后自动推送（微信/邮箱/企业微信/钉钉/飞书/Telegram，见 notify.py）
- 输出到 daily_reports/全球风险日报_YYYY-MM-DD.md

部署：见 README.md。核心依赖：LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 三个环境变量。
"""

import os
import sys
import json
import time
import datetime as dt
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

import requests

BEIJING = ZoneInfo("Asia/Shanghai")
UTC = ZoneInfo("UTC")


def _load_dotenv_local():
    """读取项目根目录 .env（若存在），注入环境变量。无依赖、失败静默。
    便于本会话/本地直接运行；GitHub Actions 走 Secrets，不影响。"""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(p):
        return
    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


_load_dotenv_local()

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
HOLIDAY_API = "https://timor.tech/api/holiday/info/{date}"  # 中国节假日
RSS_FEEDS = [
    # 中文权威 RSS（best-effort，失败自动跳过；无解析时间的条目会被丢弃）
    "http://www.xinhuanet.com/politics/news_politics.xml",   # 新华网·时政
]

# ===== GDELT 检索关键词（中英文混合，覆盖全球来源）=====
SECTIONS = {
    "美西方及盟友涉华动向": (
        "(China Taiwan) OR (Taiwan arms) OR (South China Sea) OR "
        "(China Japan) OR (China Philippines) OR (China India) OR "
        "(China South Korea) OR (China Europe) OR (China sanctions)"
    ),
    "乌克兰危机": (
        "(Ukraine Russia) OR (Russia Ukraine) OR (Zelensky Putin) OR "
        "(Ukraine sanctions) OR (Ukraine aid) OR (Ukraine strike) OR "
        "(Russia statement) OR (Ukraine statement) OR "
        "(Ukraine economy) OR (Russia economy) OR (Russia inflation) OR "
        "(Ukraine grain) OR (Ukraine port) OR (Black Sea shipping) OR "
        "(ruble) OR (hryvnia)"
    ),
    "中东局势": (
        "(Iran nuclear) OR (Israel Gaza) OR (Hormuz) OR (Houthi Red Sea) OR "
        "(Israel Hezbollah) OR (Middle East sanctions)"
    ),
    "朝鲜问题": "(North Korea) OR (Kim Jong Un missile) OR (朝鲜 导弹)",
    "大宗商品原油": "(oil price) OR (crude) OR (Brent) OR (原油)",
}

# 需要重点纳入的中文权威/财经站点（经 GDELT 域名过滤检索）
CHINESE_DOMAINS = [
    "cls.cn",            # 财联社
    "jin10.com",         # 金十数据
    "jiemian.com",       # 界面新闻
    "fmprc.gov.cn",      # 中国外交部
    "xinhuanet.com",     # 新华网
    "news.cn",           # 新华网(主站)
    "cctv.com",          # 央视
    "cankaoxiaoxi.com",  # 参考消息
    "chinanews.com.cn",  # 中国新闻网
]
CHINESE_DOMAIN_FILTER = " OR ".join(f"domain:{d}" for d in CHINESE_DOMAINS)

# 海外权威媒体白名单（定向检索 + 来源校验，保证来源准确性）
FOREIGN_MEDIA_DOMAINS = [
    "reuters.com",          # 路透社
    "apnews.com",           # 美联社
    "bbc.com", "bbc.co.uk", # BBC
    "bloomberg.com",        # 彭博
    "wsj.com",              # 华尔街日报
    "ft.com",               # 金融时报
    "theguardian.com",      # 卫报
    "nytimes.com",          # 纽约时报
    "washingtonpost.com",   # 华盛顿邮报
    "cnn.com",              # CNN
    "economist.com",        # 经济学人
    "aljazeera.com",        # 半岛电视台
    "dw.com",               # 德国之声
    "france24.com",         # 法国24
    "nhk.or.jp",            # 日本NHK
    "kyodonews.net",        # 日本共同社
    "japantimes.co.jp",     # 日本时报
    "yna.co.kr",            # 韩联社
    "koreaherald.com",      # 韩国先驱报
    "scmp.com",             # 南华早报
    "channelnewsasia.com",  # 新加坡CNA
    "straitstimes.com",     # 新加坡海峡时报
    "timesofisrael.com",    # 以色列时报
    "jpost.com",            # 耶路撒冷邮报
]
FOREIGN_MEDIA_FILTER = " OR ".join(f"domain:{d}" for d in FOREIGN_MEDIA_DOMAINS)


# ------------------------- 时间窗口 -------------------------
def beijing_now():
    return dt.datetime.now(BEIJING)


def fmt_utc_iso(d: dt.datetime) -> str:
    return d.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def is_cn_workday(d: dt.date) -> bool:
    """中国工作日判断：周末非工作；再查节假日API（失败则仅按周末判断）。"""
    if d.weekday() >= 5:  # 5=周六 6=周日
        return False
    try:
        r = requests.get(HOLIDAY_API.format(date=d.strftime("%Y-%m-%d")), timeout=8)
        data = r.json()
        t = data.get("type", {}).get("type")
        # timor.tech: 0=工作日 1=周末 2=节假日 3=调休补班
        if t in (1, 2):
            return False
        if t == 3:
            return True
    except Exception:
        pass
    return True


def prev_workday(d: dt.date) -> dt.date:
    cur = d - dt.timedelta(days=1)
    while not is_cn_workday(cur):
        cur -= dt.timedelta(days=1)
    return cur


def compute_window():
    """返回 (start_bj, end_bj)。出报日=今日。非工作日返回 None。
    窗口：上一个工作日 12:00 ~ 今日 11:00（北京时间）。"""
    today_bj = beijing_now().replace(hour=0, minute=0, second=0, microsecond=0)
    if not is_cn_workday(today_bj.date()):
        return None
    pw = prev_workday(today_bj.date())
    start = dt.datetime(pw.year, pw.month, pw.day, 12, 0, 0, tzinfo=BEIJING)
    end = dt.datetime(today_bj.year, today_bj.month, today_bj.day, 11, 0, 0, tzinfo=BEIJING)
    return start, end


# ------------------------- GDELT 检索 -------------------------
def gdelt_query(query: str, start: dt.datetime, end: dt.datetime, maxrecords=30):
    params = {
        "query": f"{query} (mode:ArtList)",
        "mode": "ArtList",
        "format": "json",
        "maxrecords": maxrecords,
        "sort": "DateDesc",
        "startdatetime": fmt_utc_iso(start),
        "enddatetime": fmt_utc_iso(end),
    }
    last_err = None
    for attempt in range(4):  # 限频重试：GDELT 要求 5 秒一次
        try:
            r = requests.get(GDELT_URL, params=params, timeout=30)
            if "limit requests" in r.text or "5 seconds" in r.text:
                last_err = "rate-limited"
                time.sleep(10)
                continue
            r.raise_for_status()
            data = r.json()
            return data.get("articles", []) or []
        except Exception as e:
            last_err = e
            time.sleep(8)
    print(f"[WARN] GDELT 检索失败 ({query[:30]}...): {last_err}", file=sys.stderr)
    return []


def parse_seendate(s: str):
    """GDELT seendate 形如 20260813T133500Z（UTC），解析失败返回 None。"""
    try:
        return dt.datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except Exception:
        return None


def _main_domain(url: str) -> str:
    """提取 url 主域名（去 www./m./amp. 前缀），失败返回空串。"""
    try:
        from urllib.parse import urlparse
        netloc = urlparse(url).netloc.lower()
    except Exception:
        return ""
    for pre in ("www.", "m.", "amp."):
        if netloc.startswith(pre):
            netloc = netloc[len(pre):]
    return netloc


def _is_allowed_domain(url: str, allowed: list) -> bool:
    """来源准确性校验：url 主域名必须命中白名单（含子域匹配）。"""
    d = _main_domain(url)
    if not d:
        return False
    return any(d == x or d.endswith("." + x) for x in allowed)


def _within(u, start, end):
    """按发布时间严格剔除窗口外（仅当能解析时间时）。"""
    sd = parse_seendate(u.get("seendate", ""))
    if sd is None:
        return True
    sd_bj = sd.astimezone(BEIJING)
    return start <= sd_bj <= end


def collect_gdelt(start, end):
    """三遍检索：①全球 ②中文权威域（白名单校验）③海外权威媒体域（白名单校验）。"""
    all_articles = {}

    def absorb(arts, section, must_match=None):
        for a in arts:
            url = a.get("url")
            if not url or url in all_articles:
                continue
            # 定向检索必须通过域名白名单校验，保证来源准确性
            if must_match is not None and not _is_allowed_domain(url, must_match):
                continue
            if not _within(a, start, end):
                continue
            all_articles[url] = {
                "section": section,
                "title": a.get("title", ""),
                "domain": a.get("domain", "") or _main_domain(url),
                "seendate": a.get("seendate", ""),
                "url": url,
                "sourcecountry": a.get("sourcecountry", ""),
            }

    # 1) 全球来源（原始板块，不做域名限制）
    for name, q in SECTIONS.items():
        absorb(gdelt_query(q, start, end), name)
        time.sleep(7)  # GDELT 限 5 秒一次，礼貌限速

    # 2) 中文权威/财经源（域名过滤 + 白名单校验，覆盖外交部/财联社/金十/界面等）
    for name, q in SECTIONS.items():
        q_cn = f"({q}) ({CHINESE_DOMAIN_FILTER})"
        absorb(gdelt_query(q_cn, start, end, maxrecords=25),
               name + "（中文源）", must_match=CHINESE_DOMAINS)
        time.sleep(7)

    # 3) 海外权威媒体（定向检索 + 白名单校验，如 Reuters/AP/BBC/Bloomberg 等）
    for name, q in SECTIONS.items():
        q_fm = f"({q}) ({FOREIGN_MEDIA_FILTER})"
        absorb(gdelt_query(q_fm, start, end, maxrecords=25),
               name + "（海外权威媒体）", must_match=FOREIGN_MEDIA_DOMAINS)
        time.sleep(7)

    return list(all_articles.values())


# ------------------------- 中文 RSS 补充 -------------------------
def _parse_rss_date(s: str):
    s = (s or "").strip()
    if not s:
        return None
    # 兼容逗号后无空格、GMT 时区、连字符日期等变体
    variants = [
        s,
        s.replace(", ", ",").replace("  ", " "),
        s.replace("GMT", "+0000"),
    ]
    fmts = (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a,%d-%b-%Y %H:%M:%S %Z",     # 新华：Wed,14-Dec-2022 11:37:37 GMT
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%d %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S GMT",
    )
    for v in variants:
        for fmt in fmts:
            try:
                return dt.datetime.strptime(v, fmt)
            except Exception:
                continue
    return None


def collect_rss(start, end, per_feed=10):
    out = []
    for feed in RSS_FEEDS:
        try:
            r = requests.get(feed, headers={"User-Agent": "Mozilla/5.0"},
                             timeout=15)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            items = root.findall(".//item") or root.findall(".//entry")
            count = 0
            for it in items:
                if count >= per_feed:
                    break
                title = (it.findtext("title") or it.findtext("title", default="")).strip()
                link = it.findtext("link") or ""
                if not link:
                    l = it.find("link")
                    if l is not None:
                        link = l.get("href", "")
                pub = it.findtext("pubDate") or it.findtext("updated") or ""
                pdate = _parse_rss_date(pub)
                # 严格时间窗：解析不出时间的条目直接丢弃，避免旧闻混入
                if pdate is None:
                    continue
                pdate_bj = pdate.astimezone(BEIJING) if pdate.tzinfo else pdate.replace(tzinfo=BEIJING)
                if not (start <= pdate_bj <= end):
                    continue
                if not title or not link:
                    continue
                out.append({
                    "section": "RSS补充（中文权威）",
                    "title": title,
                    "domain": feed.split("/")[2],
                    "seendate": pub,
                    "url": link,
                    "sourcecountry": "CN",
                })
                count += 1
        except Exception as e:
            print(f"[WARN] RSS 抓取失败 ({feed}): {e}", file=sys.stderr)
    return out


def collect_news(start, end):
    arts = collect_gdelt(start, end)
    arts += collect_rss(start, end)
    return arts


# ------------------------- LLM 整理 -------------------------
SYSTEM_PROMPT = """你是一名资深国际风险分析师，负责编制《全球风险日报》。
任务：基于提供的原始新闻条目，按以下固定结构整理成中文 Markdown 报告。

【结构要求】
# 全球风险日报
- 日期、覆盖窗口、编制说明

## 一、今日风险研判（要点）
用表格列出优先级（🔴高/🟠中/🟡低）、事件、风险指向。仅列最关键的 3-6 条。

## 二、美西方及盟友涉华动向（含正负面）
分节记录，务必覆盖：
- 2.1 美国涉华表态与动作（含对台军售/涉台立法等）
- 2.2 盟友（日韩菲印等）涉华表态与动作
- 2.3 中国台湾地区相关方面的表态、行动与动向
- 2.4 美西方及其盟友企业对华不利动态（如制裁、断供、审查、撤资、限制中国业务等）
客观记录，并给出"研判（正面）"与"研判（风险）"。

## 三、乌克兰危机动态
要求覆盖以下层面（无信息的子项写"本窗口内未见重大新增（保留监测）"）：
- 3.1 各方表态：美、俄、乌三方**及其他有关各方**（欧盟、北约、联合国、相关国家等）的最新表态、互动与进展（含和谈/停火进展、制裁与援助动向）。
- 3.2 战场态势：具体被打击的城市/设施、所用武器、造成影响与伤亡。
- 3.3 经济影响数据（重点）：俄乌两国最新经济数据，尤其是**受战争影响的部分**——如乌克兰港口出口量变化（粮食、金属等）、黑海航运量、乌克兰通胀与货币（格里夫纳）走势；俄罗斯经济指标（卢布汇率、通胀、利率、财政收支）等。窗口内有数据务必给出**具体数字**并标注来源；没有则如实说明。

## 四、中东局势动态
分 4.1 伊朗核与霍尔木兹、4.2 巴以冲突、4.3 涉及金融机构的制裁。若某子项无重大信息，写"本窗口未见重大新增记录。（保留监测）"。

## 五、其他重大信息
5.1 朝鲜问题；5.2 大宗商品（原油）；5.3 各国重大政治经济事件。

【硬规则】
0. 你收到的新闻条目已按时间窗口过滤；只基于这些条目撰写。若某板块无条目，则写"本窗口内未见重大新增动态（保留监测）"，严禁引用任何窗口外信息或自行补充背景。
1. 仅基于提供的新闻条目撰写，不得编造未提供的事实或来源。
2. 【资料来源内联·来源准确性】每一条事实/事件后，必须用 Markdown 链接标注其来源，格式如：
   `……（据xx报道）[来源：Reuters](https://...)` 或 `[来源：财联社](https://...)`
   链接必须直接使用对应条目中给出的 url 字段，确保点击可跳转复查；不得改写、不得替换为条目之外的链接。
   同一事件有多来源时，优先标注更权威的媒体（如 Reuters/AP/BBC/新华社等）。
   不要用脚注编号，也不要在文末另列"资料来源"汇总表。
3. 涉及中国台湾地区的事项，遵循一个中国原则表述（用"中国台湾地区""对台军售"等）。
4. 用风险视角提炼影响，区分"事实"与"研判"。
5. 输出纯 Markdown，不要代码块包裹。"""

USER_TEMPLATE = """覆盖窗口：{start} ~ {end}（北京时间）
以下是该窗口内检索到的原始新闻条目（JSON，每条含 title/domain/url/section）：
{news_json}

请据此编制《全球风险日报》，并将来源作为可点击链接内联到正文对应事实之后。"""


def call_llm(news_json: str, start: str, end: str) -> str:
    api_key = os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
    model = os.environ.get("LLM_MODEL", "deepseek-chat")
    if not api_key:
        raise RuntimeError("缺少环境变量 LLM_API_KEY")

    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(
                start=start, end=end, news_json=news_json)},
        ],
        temperature=0.3,
        max_tokens=4000,
    )
    return resp.choices[0].message.content


# ------------------------- 主流程 -------------------------
def main():
    window = compute_window()
    if window is None:
        print("今日非中国工作日，跳过出报。")
        return
    start, end = window
    start_s = start.strftime("%Y-%m-%d %H:%M")
    end_s = end.strftime("%Y-%m-%d %H:%M")

    print(f"窗口：{start_s} ~ {end_s}（北京时间），开始检索…")
    articles = collect_news(start, end)
    print(f"检索到 {len(articles)} 条新闻。")

    if not articles:
        print("未检索到新闻，仍生成空框架报告。")
    news_json = json.dumps(articles, ensure_ascii=False, indent=1)

    print("调用 LLM 整理报告…")
    report = call_llm(news_json, start_s, end_s)

    out_dir = "daily_reports"
    os.makedirs(out_dir, exist_ok=True)
    date_str = end.strftime("%Y-%m-%d")
    out_path = os.path.join(out_dir, f"全球风险日报_{date_str}.md")
    header = (
        f"<!-- 自动生成：窗口 {start_s} ~ {end_s} 北京时间；"
        f"检索 {len(articles)} 条 -->\n\n"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header + report)
    print(f"报告已写入：{out_path}")

    # 生成后推送
    title = f"全球风险日报 {date_str}（窗口 {start_s} ~ {end_s}）"
    summary = f"本期检索 {len(articles)} 条，覆盖美西方涉华、乌克兰、中东、朝鲜、大宗商品等板块。"
    try:
        import notify
        notify.send_report(out_path, title, summary, header + report)
    except Exception as e:
        print(f"[WARN] 推送环节异常（不影响报告生成）: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
