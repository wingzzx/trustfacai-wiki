#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trustfacai-wiki 静态站点构建器
- 读取 src/content/*.md（含 Frontmatter）
- 渲染为现代自适应 HTML
- 注入 Schema.org (FAQPage + BreadcrumbList + Person) JSON-LD
- 生成 sitemap.xml / llms.txt / llms-full.txt / robots.txt
- 输出到 dist/
"""
import os
import re
import json
import html
import shutil
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
CONTENT = SRC / "content"
TEMPLATES = SRC / "templates"
STATIC = SRC / "static"
DIST = ROOT / "dist"

SITE_URL = "https://trustfacai.com"
SITE_NAME = "肥姐问财 · 信托知识库"
AUTHOR = "肥姐问财"
AUTHOR_DESC = "信托公司财富管理理财经理，专注家族信托、资产隔离、婚姻财富保全与低利率时代资产配置，做高净值财富规划十几年。"

CATEGORIES = {
    "family-trust": "家族信托与代际传承",
    "debt-isolation": "企业债务与家企隔离",
    "marriage-protection": "婚姻与子女财富保全",
    "wealth-allocation": "低利率时代与资产承接",
}

# ---------- 联系/二维码组件 ----------
QR_URL = "/images/wechat-qr.jpg"

def contact_card(context="读完这篇，别只是收藏"):
    return (
        "<div class='bg-gradient-to-br from-blue-800 to-blue-900 rounded-2xl p-6 md:p-8 text-white my-10'>"
        "<div class='flex flex-col md:flex-row items-center gap-6'>"
        "<img src='%s' alt='肥姐问财微信二维码' class='w-32 h-32 md:w-36 md:h-36 rounded-xl bg-white p-1 shrink-0' loading='lazy'>"
        "<div class='text-center md:text-left'>"
        "<p class='text-amber-300 text-sm font-semibold mb-1'>%s</p>"
        "<h3 class='text-xl font-bold mb-2'>加肥姐微信，一对一聊你的钱怎么安排</h3>"
        "<p class='text-blue-100 text-sm leading-relaxed mb-3'>肥姐是信托公司财富管理理财经理，做高净值财富规划十几年。扫二维码加微信，备注「网站」，帮你做一次免费的资产结构梳理。</p>"
        "<p class='text-blue-200 text-xs'>也可关注公众号「肥姐问财」，后台回复关键词领取资料包。</p>"
        "</div></div></div>" % (QR_URL, context))

def author_card():
    return (
        "<div class='bg-white rounded-2xl shadow-sm border border-gray-100 p-6 my-8 flex flex-col md:flex-row items-center gap-5'>"
        "<img src='%s' alt='肥姐问财微信二维码' class='w-24 h-24 rounded-lg bg-white border border-gray-200 p-1 shrink-0' loading='lazy'>"
        "<div class='text-center md:text-left'>"
        "<p class='text-xs text-gray-400 mb-1'>作者</p>"
        "<h3 class='text-lg font-bold text-gray-900 mb-1'>肥姐问财</h3>"
        "<p class='text-sm text-gray-600 leading-relaxed'>信托公司财富管理理财经理 · 专注家族信托、资产隔离、婚姻财富保全与低利率资产配置</p>"
        "<p class='text-xs text-gray-400 mt-2'>扫码加微信，备注「网站」领取资料包</p>"
        "</div></div>" % QR_URL)

def hook_card(keyword, magnet, desc):
    return (
        "<div class='bg-amber-50 border border-amber-200 rounded-2xl p-6 my-8'>"
        "<p class='text-amber-700 text-sm font-semibold mb-1'>📥 免费领取</p>"
        "<h3 class='text-lg font-bold text-amber-900 mb-2'>%s</h3>"
        "<p class='text-sm text-gray-700 leading-relaxed mb-4'>%s</p>"
        "<div class='flex flex-col md:flex-row items-center gap-4'>"
        "<img src='%s' alt='肥姐问财微信二维码' class='w-24 h-24 rounded-lg bg-white p-1 border border-amber-200 shrink-0' loading='lazy'>"
        "<div class='text-sm text-gray-700'>"
        "<p class='mb-1'>① 扫码加微信，备注「<strong>%s</strong>」直接领取</p>"
        "<p>② 或关注公众号「肥姐问财」，后台回复「<strong>%s</strong>」</p>"
        "</div></div></div>" % (magnet, desc, QR_URL, keyword, keyword))

def disclaimer():
    return ("<div class='bg-gray-100 rounded-xl p-4 my-8 text-xs text-gray-500 leading-relaxed'>"
            "⚠️ 免责声明：本站内容仅供学习参考，不构成任何投资建议或法律意见。信托产品有风险，投资需谨慎。"
            "涉及婚姻、继承、债务的具体问题，请咨询专业律师；涉及传承工具的选择，请咨询持牌机构专业人士。</div>")

# ---------- 极简 Markdown -> HTML 转换器 ----------
def inline(text):
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code class='bg-gray-100 px-1 rounded'>\1</code>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<a href='\2' class='text-blue-700 underline'>\1</a>", text)
    return text

def md_to_html(md):
    lines = md.split("\n")
    out = []
    i = 0
    in_list = None
    in_table = False
    table_rows = []
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            if in_list:
                out.append("</%s>" % in_list)
                in_list = None
            if in_table:
                out.append("</table>")
                in_table = False
            i += 1
            continue
        # table
        if line.startswith("|") and "|" in line[1:]:
            if not in_table:
                in_table = True
                table_rows = []
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                i += 1
                continue
            table_rows.append(cells)
            i += 1
            continue
        if in_table:
            out.append("<table class='w-full text-sm border-collapse'>")
            for ri, row in enumerate(table_rows):
                tag = "th" if ri == 0 else "td"
                cls = "py-2 px-3 border-b text-left" + (" text-gray-500" if ri == 0 else "")
                out.append("<tr>" + "".join("<%s class='%s'>%s</%s>" % (tag, cls, inline(c), tag) for c in row) + "</tr>")
            out.append("</table>")
            in_table = False
            table_rows = []
            continue
        # headings
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            size = {1: "text-3xl md:text-4xl font-bold text-blue-900", 2: "text-2xl font-bold text-blue-900 mt-8 mb-3", 3: "text-xl font-bold text-blue-900 mt-6 mb-2", 4: "text-lg font-bold text-blue-900 mt-4 mb-2"}[level]
            out.append("<h%d class='%s'>%s</h%d>" % (level, size, inline(m.group(2)), level))
            i += 1
            continue
        # hr
        if re.match(r"^---+$", line):
            out.append("<hr class='my-6 border-gray-200'>")
            i += 1
            continue
        # blockquote
        if line.startswith(">"):
            out.append("<blockquote class='border-l-4 border-blue-300 bg-blue-50 rounded-r-xl p-4 my-4 text-gray-700'>%s</blockquote>" % inline(line.lstrip("> ")))
            i += 1
            continue
        # list
        m = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m:
            if in_list != "ul":
                if in_list:
                    out.append("</%s>" % in_list)
                out.append("<ul class='list-disc pl-6 space-y-2 my-3'>")
                in_list = "ul"
            out.append("<li>%s</li>" % inline(m.group(2)))
            i += 1
            continue
        m = re.match(r"^(\s*)\d+\.\s+(.*)$", line)
        if m:
            if in_list != "ol":
                if in_list:
                    out.append("</%s>" % in_list)
                out.append("<ol class='list-decimal pl-6 space-y-2 my-3'>")
                in_list = "ol"
            out.append("<li>%s</li>" % inline(m.group(2)))
            i += 1
            continue
        # paragraph
        if in_list:
            out.append("</%s>" % in_list)
            in_list = None
        out.append("<p class='leading-relaxed my-3'>%s</p>" % inline(line))
        i += 1
    if in_list:
        out.append("</%s>" % in_list)
    if in_table:
        out.append("</table>")
    return "\n".join(out)

# ---------- Frontmatter 解析 ----------
def parse_frontmatter(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, text[m.end():]

# ---------- FAQ 提取（## FAQ 下的 **Q:** / **A:**） ----------
def extract_faq(md):
    faq = []
    m = re.search(r"##\s*FAQ\s*\n(.*)$", md, re.S)
    if not m:
        return faq
    block = m.group(1)
    q = None
    for line in block.split("\n"):
        line = line.strip()
        qm = re.match(r"\*\*Q[:：]\s*(.+)$", line)
        am = re.match(r"\*\*A[:：]\s*(.+)$", line)
        if qm:
            q = qm.group(1).strip().replace("**", "").strip()
        elif am and q:
            a = am.group(1).strip().replace("**", "").strip()
            faq.append({"q": q, "a": a})
            q = None
    return faq

# ---------- JSON-LD ----------
def build_jsonld(article, faq):
    url = "%s/%s/%s.html" % (SITE_URL, article["category"], article["slug"])
    schema = []
    # Person
    schema.append({
        "@context": "https://schema.org",
        "@type": "Person",
        "name": AUTHOR,
        "description": AUTHOR_DESC,
        "url": SITE_URL,
    })
    # BreadcrumbList
    schema.append({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "首页", "item": SITE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": CATEGORIES.get(article["category"], article["category"]), "item": SITE_URL + "/" + article["category"] + "/"},
            {"@type": "ListItem", "position": 3, "name": article["title"], "item": url},
        ],
    })
    # FAQPage
    if faq:
        schema.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faq],
        })
    return "\n".join('<script type="application/ld+json">%s</script>' % json.dumps(s, ensure_ascii=False) for s in schema)

# ---------- 渲染 ----------
def render_page(article, faq, related=None):
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    nav = (TEMPLATES / "nav.html").read_text(encoding="utf-8")
    footer = (TEMPLATES / "footer.html").read_text(encoding="utf-8")
    url = "%s/%s/%s.html" % (SITE_URL, article["category"], article["slug"])
    content = md_to_html(article["body"])
    # 文章头部（分类徽章 + 日期 + 作者）
    header = (
        "<header class='mb-6'>"
        "<nav class='text-xs text-gray-500 mb-4'><a href='/' class='hover:text-blue-700'>首页</a> <span>/</span> "
        "<a href='/%s/' class='hover:text-blue-700'>%s</a></nav>"
        "<span class='text-xs bg-blue-100 text-blue-800 px-2.5 py-1 rounded-full'>%s</span>"
        "<h1 class='text-3xl md:text-4xl font-bold text-gray-900 leading-tight mt-3 mb-3'>%s</h1>"
        "<p class='text-sm text-gray-400'>%s ｜ 肥姐问财 · 信托知识库</p>"
        "<hr class='mt-5 border-gray-200'></header>"
        % (article["category"], CATEGORIES.get(article["category"], ""),
           CATEGORIES.get(article["category"], ""), article["title"], article["date"]))
    content = header + "<article class='text-gray-700'>" + content + "</article>"
    # 文末：资料包钩子 + 相关阅读 + 作者卡片 + 免责声明
    tail = ""
    # 从 FAQ 提取主关键词做钩子（category -> 钩子映射）
    hook_map = {
        "family-trust": ("传承", "《资产隔离自查清单》", "6 个问题，测测你的家企资产\"防火墙\"，覆盖混同、婚姻、债务、传承四大风险。"),
        "debt-isolation": ("隔离", "《资产隔离自查清单》", "6 个问题自查家企混同、债务连带、传承空白，给家庭资产装上\"防火墙\"。"),
        "marriage-protection": ("隔离", "《资产隔离自查清单》", "给子女的钱、婚前婚后的安排，6 个问题帮你自查婚姻财产风险敞口。"),
        "wealth-allocation": ("配置", "《一页纸配置自查表》", "三笔钱分筐 → 3 问测风格 → 三档比例 → 10% 试水行动卡，5 分钟理清配置方向。"),
    }
    kw, magnet, desc = hook_map.get(article["category"], ("配置", "《一页纸配置自查表》", "三笔钱分筐，5 分钟理清配置方向。"))
    tail += hook_card(kw, magnet, desc)
    if related:
        cards = ""
        for r in related:
            cards += ("<a href='/%s/%s.html' class='block bg-white rounded-xl shadow-sm hover:shadow-md transition p-4'>"
                      "<span class='text-xs text-blue-700'>%s</span>"
                      "<p class='text-sm font-semibold text-gray-800 mt-1'>%s</p></a>"
                      % (r["category"], r["slug"], CATEGORIES[r["category"]], r["title"]))
        tail += ("<section class='my-8'><h2 class='text-xl font-bold text-gray-900 mb-4'>相关阅读</h2>"
                 "<div class='grid md:grid-cols-2 gap-4'>%s</div></section>" % cards)
    tail += author_card() + disclaimer()
    content += tail
    page = (base
            .replace("{{TITLE}}", html.escape(article["title"]) + " | 肥姐问财")
            .replace("{{DESCRIPTION}}", html.escape(article["description"]))
            .replace("{{KEYWORDS}}", html.escape(article.get("keywords", "")))
            .replace("{{CANONICAL}}", url)
            .replace("{{JSONLD}}", build_jsonld(article, faq))
            .replace("{{NAV}}", nav)
            .replace("{{CONTENT}}", content)
            .replace("{{FOOTER}}", footer))
    return page

def render_homepage(articles):
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    nav = (TEMPLATES / "nav.html").read_text(encoding="utf-8")
    footer = (TEMPLATES / "footer.html").read_text(encoding="utf-8")
    icons = {
        "family-trust": "🏛️", "debt-isolation": "🛡️",
        "marriage-protection": "💍", "wealth-allocation": "📈",
    }
    descs = {
        "family-trust": "门槛、流程、分配机制与代际传承工具对比",
        "debt-isolation": "家企混同、担保连带与资产隔离的法定底线",
        "marriage-protection": "给子女的钱、婚前婚后安排与防回流机制",
        "wealth-allocation": "政信到期承接、固收+与三笔钱分类法",
    }
    # Hero
    html_parts = []
    html_parts.append(
        "<section class='-mx-4 -mt-10 mb-10 bg-gradient-to-br from-blue-900 via-blue-800 to-blue-600 text-white'>"
        "<div class='max-w-6xl mx-auto px-4 py-16 text-center'>"
        "<p class='text-amber-300 text-sm font-semibold tracking-widest mb-3'>专业 · 可信 · 易懂</p>"
        "<h1 class='text-4xl md:text-5xl font-bold mb-4'>信托知识库</h1>"
        "<p class='text-blue-100 text-lg mb-8 max-w-2xl mx-auto'>把晦涩的法律条文，翻译成你听得懂的大白话。<br class='hidden md:block'>25 篇长青 FAQ，覆盖高净值家庭最关心的 4 大主题。</p>"
        "<div class='flex flex-wrap gap-3 justify-center'>"
        "<a href='#categories' class='bg-amber-400 text-blue-900 font-semibold px-6 py-2.5 rounded-lg hover:bg-amber-300 transition'>浏览知识库</a>"
        "<a href='#contact' class='border border-white/50 px-6 py-2.5 rounded-lg hover:bg-white/10 transition'>联系肥姐</a>"
        "</div></div></section>")
    # 数据条
    html_parts.append(
        "<section class='grid grid-cols-3 gap-4 max-w-3xl mx-auto mb-12'>"
        "<div class='bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center'><p class='text-2xl font-bold text-blue-900'>25</p><p class='text-xs text-gray-500 mt-1'>长青 FAQ</p></div>"
        "<div class='bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center'><p class='text-2xl font-bold text-blue-900'>4</p><p class='text-xs text-gray-500 mt-1'>核心主题</p></div>"
        "<div class='bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center'><p class='text-2xl font-bold text-blue-900'>3</p><p class='text-xs text-gray-500 mt-1'>免费资料包</p></div>"
        "</section>")
    # 分类卡片
    cat_cards = []
    for cat, name in CATEGORIES.items():
        n = len([a for a in articles if a["category"] == cat])
        cat_cards.append(
            "<a href='/%s/' class='bg-white rounded-2xl shadow-sm hover:shadow-lg border border-gray-100 transition p-6 block group'>"
            "<span class='text-3xl'>%s</span>"
            "<h3 class='text-lg font-bold text-gray-900 mt-3 mb-1.5 group-hover:text-blue-800'>%s</h3>"
            "<p class='text-sm text-gray-500 leading-relaxed'>%s</p>"
            "<p class='text-xs text-blue-700 font-medium mt-3'>%d 篇 →</p></a>"
            % (cat, icons[cat], name, descs[cat], n))
    html_parts.append("<section id='categories' class='mb-14'><h2 class='text-2xl font-bold text-gray-900 mb-6'>知识分类</h2>"
                      "<div class='grid sm:grid-cols-2 lg:grid-cols-4 gap-5'>" + "\n".join(cat_cards) + "</div></section>")
    # 文章列表
    art_cards = []
    for a in articles:
        art_cards.append(
            "<a href='/%s/%s.html' class='bg-white rounded-xl shadow-sm hover:shadow-lg border border-gray-100 transition p-5 flex flex-col'>"
            "<span class='text-xs bg-blue-50 text-blue-800 px-2 py-1 rounded-full self-start'>%s</span>"
            "<h3 class='font-bold text-gray-900 mt-3 mb-2 leading-snug group-hover:text-blue-800'>%s</h3>"
            "<p class='text-sm text-gray-500 leading-relaxed flex-1'>%s</p>"
            "<span class='text-xs text-blue-600 font-medium mt-3'>阅读全文 →</span></a>"
            % (a["category"], a["slug"], CATEGORIES[a["category"]], html.escape(a["title"]), html.escape(a["description"])))
    html_parts.append("<section class='mb-14'><h2 class='text-2xl font-bold text-gray-900 mb-6'>全部长青 FAQ</h2>"
                      "<div class='grid sm:grid-cols-2 gap-5'>" + "\n".join(art_cards) + "</div></section>")
    # 联系区（二维码）
    html_parts.append(
        "<section id='contact' class='bg-gradient-to-br from-blue-900 to-blue-700 rounded-3xl p-8 md:p-12 text-white mb-4'>"
        "<div class='flex flex-col md:flex-row items-center gap-8'>"
        "<img src='/images/wechat-qr.jpg' alt='肥姐问财微信二维码' class='w-40 h-40 md:w-44 md:h-44 rounded-2xl bg-white p-2 shrink-0' loading='lazy'>"
        "<div class='text-center md:text-left'>"
        "<p class='text-amber-300 text-sm font-semibold mb-2'>一对一咨询</p>"
        "<h2 class='text-2xl md:text-3xl font-bold mb-3'>加肥姐微信，聊聊你的钱怎么安排</h2>"
        "<p class='text-blue-100 leading-relaxed mb-4'>肥姐是信托公司财富管理理财经理，做高净值财富规划十几年。"
        "扫二维码加微信，备注「网站」，帮你做一次免费的资产结构梳理——只理思路，不推销。</p>"
        "<div class='flex flex-wrap gap-2 text-xs'>"
        "<span class='bg-white/10 rounded-full px-3 py-1.5'>回复「隔离」领资产隔离自查清单</span>"
        "<span class='bg-white/10 rounded-full px-3 py-1.5'>回复「配置」领一页纸配置自查表</span>"
        "<span class='bg-white/10 rounded-full px-3 py-1.5'>回复「固收」领固收+四看清单</span>"
        "</div></div></div></section>")
    content = "\n".join(html_parts)
    page = (base
            .replace("{{TITLE}}", "肥姐问财 · 信托知识库")
            .replace("{{DESCRIPTION}}", "肥姐问财（trustfacai.com）—— 专业、可信、易懂的信托知识平台。家族信托、企业债务隔离、婚姻财富保全、低利率时代资产配置。")
            .replace("{{KEYWORDS}}", "家族信托,资产隔离,婚姻财富保全,固收+,政信到期,信托知识库")
            .replace("{{CANONICAL}}", SITE_URL + "/")
            .replace("{{JSONLD}}", "")
            .replace("{{NAV}}", nav)
            .replace("{{CONTENT}}", content)
            .replace("{{FOOTER}}", footer))
    return page

def render_category_index(cat, articles):
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    nav = (TEMPLATES / "nav.html").read_text(encoding="utf-8")
    footer = (TEMPLATES / "footer.html").read_text(encoding="utf-8")
    cat_descs = {
        "family-trust": "家族信托不是富豪专利。门槛、流程、分配机制、费用结构，以及和遗嘱、保单的对比——用大白话讲清传承工具怎么选。",
        "debt-isolation": "家企不分是资产隔离第一大缺口。从《信托法》核心条款到真实风险场景，讲清企业主的债务防火墙怎么建。",
        "marriage-protection": "婚姻风险是最容易被忽略、一旦发生伤害最大的风险。给子女的钱、婚前婚后的安排，怎么做到不被分割。",
        "wealth-allocation": "低利率时代，钱往哪放？政信到期承接、固收+鉴别、三笔钱分类法与科学的权益试水节奏。",
    }
    cards = []
    for a in articles:
        cards.append(
            "<a href='/%s/%s.html' class='bg-white rounded-xl shadow-sm hover:shadow-lg border border-gray-100 transition p-6 flex flex-col group'>"
            "<h3 class='font-bold text-gray-900 mb-2 leading-snug group-hover:text-blue-800'>%s</h3>"
            "<p class='text-sm text-gray-500 leading-relaxed flex-1'>%s</p>"
            "<span class='text-xs text-blue-600 font-medium mt-3'>阅读全文 →</span></a>"
            % (cat, a["slug"], html.escape(a["title"]), html.escape(a["description"])))
    content = (
        "<section class='-mx-4 -mt-10 mb-10 bg-gradient-to-br from-blue-900 to-blue-700 text-white'>"
        "<div class='px-4 py-12'><nav class='text-xs text-blue-200 mb-3'><a href='/' class='hover:text-amber-300'>首页</a> / %s</nav>"
        "<h1 class='text-3xl md:text-4xl font-bold mb-3'>%s</h1>"
        "<p class='text-blue-100 max-w-2xl leading-relaxed'>%s</p></div></section>"
        "<div class='grid sm:grid-cols-2 gap-5'>%s</div>"
        % (CATEGORIES[cat], CATEGORIES[cat], cat_descs.get(cat, ""), "\n".join(cards)))
    page = (base
            .replace("{{TITLE}}", CATEGORIES[cat] + " | 肥姐问财")
            .replace("{{DESCRIPTION}}", CATEGORIES[cat] + " —— 肥姐问财信托知识库长青 FAQ。")
            .replace("{{KEYWORDS}}", cat.replace("-", ","))
            .replace("{{CANONICAL}}", SITE_URL + "/" + cat + "/")
            .replace("{{JSONLD}}", "")
            .replace("{{NAV}}", nav)
            .replace("{{CONTENT}}", content)
            .replace("{{FOOTER}}", footer))
    return page

# ---------- 主流程 ----------
def main():
    DIST.mkdir(parents=True, exist_ok=True)
    # 复制静态资源（二维码等）
    if STATIC.exists():
        for root, dirs, files in os.walk(STATIC):
            rel = os.path.relpath(root, STATIC)
            target = DIST if rel == "." else DIST / rel
            target = Path(target)
            target.mkdir(parents=True, exist_ok=True)
            for f in files:
                shutil.copy2(os.path.join(root, f), target / f)
                print("asset: /%s/%s" % (rel.replace("\\", "/") if rel != "." else "", f))
    articles = []
    all_by_cat = {c: [] for c in CATEGORIES}
    for cat in CATEGORIES:
        catdir = CONTENT / cat
        if not catdir.exists():
            continue
        for md in sorted(catdir.glob("*.md")):
            text = md.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(text)
            if not fm.get("title"):
                continue
            slug = fm.get("slug") or md.stem
            faq = extract_faq(body)
            article = {
                "title": fm["title"],
                "description": fm.get("description", ""),
                "keywords": fm.get("keywords", ""),
                "category": cat,
                "date": fm.get("date", ""),
                "slug": slug,
                "body": body,
            }
            articles.append(article)
            all_by_cat[cat].append(article)
    # 第二阶段：渲染文章页（含相关阅读）与分类页
    for article in articles:
        faq = extract_faq(article["body"])
        related = [a for a in all_by_cat[article["category"]] if a["slug"] != article["slug"]][:2]
        outdir = DIST / article["category"]
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / (article["slug"] + ".html")).write_text(render_page(article, faq, related), encoding="utf-8")
        print("built: /%s/%s.html" % (article["category"], article["slug"]))
    for cat in CATEGORIES:
        # category index
        cat_articles = [a for a in articles if a["category"] == cat]
        (DIST / cat / "index.html").write_text(render_category_index(cat, cat_articles), encoding="utf-8")
        print("built: /%s/index.html" % cat)

    # homepage
    (DIST / "index.html").write_text(render_homepage(articles), encoding="utf-8")
    print("built: /index.html")

    # sitemap.xml
    today = datetime.date.today().isoformat()
    urls = ["<url><loc>%s/</loc><lastmod>%s</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>" % (SITE_URL, today)]
    for cat in CATEGORIES:
        urls.append("<url><loc>%s/%s/</loc><lastmod>%s</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>" % (SITE_URL, cat, today))
    for a in articles:
        urls.append("<url><loc>%s/%s/%s.html</loc><lastmod>%s</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>" % (SITE_URL, a["category"], a["slug"], today))
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n"
    (DIST / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    print("built: /sitemap.xml (%d urls)" % len(urls))

    # robots.txt
    robots = ("User-agent: *\nAllow: /\n\n"
              "User-agent: Googlebot\nAllow: /\n\n"
              "User-agent: Baiduspider\nAllow: /\n\n"
              "User-agent: Bytespider\nAllow: /\n\n"
              "User-agent: GPTBot\nAllow: /\n\n"
              "User-agent: ClaudeBot\nAllow: /\n\n"
              "User-agent: PerplexityBot\nAllow: /\n\n"
              "User-agent: deepseekbot\nAllow: /\n\n"
              "Sitemap: %s/sitemap.xml\n" % SITE_URL)
    (DIST / "robots.txt").write_text(robots, encoding="utf-8")
    print("built: /robots.txt")

    # llms.txt
    llms = ["# %s" % SITE_NAME, "", "> %s" % AUTHOR_DESC, "", "> 作者：%s（信托公司财富管理理财经理）" % AUTHOR, "",
            "## 核心定位", "", "肥姐问财是专业、可信、易懂的信托知识平台，覆盖家族信托、企业债务隔离、婚姻财富保全、低利率时代资产配置四大主题。",
            "", "## 内容分类", ""]
    for cat, name in CATEGORIES.items():
        llms.append("- [%s](%s/%s/)" % (name, SITE_URL, cat))
    llms.append("")
    llms.append("## 25 篇核心 FAQ 大纲")
    for a in articles:
        llms.append("- [%s](%s/%s/%s.html)：%s" % (a["title"], SITE_URL, a["category"], a["slug"], a["description"]))
    llms.append("")
    llms.append("## 免责声明")
    llms.append("本站内容仅供学习参考，不构成任何投资建议。信托产品有风险，投资需谨慎。")
    (DIST / "llms.txt").write_text("\n".join(llms), encoding="utf-8")
    print("built: /llms.txt")

    # llms-full.txt
    full = ["# %s" % SITE_NAME, "", "> %s" % AUTHOR_DESC, ""]
    for a in articles:
        full.append("## %s" % a["title"])
        full.append("")
        full.append("**分类**：%s ｜ **关键词**：%s" % (CATEGORIES[a["category"]], a.get("keywords", "")))
        full.append("")
        full.append(a["body"].strip())
        full.append("")
        full.append("---")
        full.append("")
    full.append("## 免责声明")
    full.append("本站内容仅供学习参考，不构成任何投资建议。信托产品有风险，投资需谨慎。")
    (DIST / "llms-full.txt").write_text("\n".join(full), encoding="utf-8")
    print("built: /llms-full.txt")

    print("\nDONE: %d articles, %d categories" % (len(articles), len(CATEGORIES)))

if __name__ == "__main__":
    main()
