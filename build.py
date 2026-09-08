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
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
CONTENT = SRC / "content"
TEMPLATES = SRC / "templates"
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
def render_page(article, faq):
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    nav = (TEMPLATES / "nav.html").read_text(encoding="utf-8")
    footer = (TEMPLATES / "footer.html").read_text(encoding="utf-8")
    url = "%s/%s/%s.html" % (SITE_URL, article["category"], article["slug"])
    content = md_to_html(article["body"])
    # 面包屑
    crumb = ("<nav class='text-xs text-gray-500 mb-4'><a href='/' class='hover:text-blue-700'>首页</a> <span>/</span> "
             "<a href='/%s/' class='hover:text-blue-700'>%s</a> <span>/</span> %s</nav>"
             % (article["category"], CATEGORIES.get(article["category"], ""), article["title"]))
    content = crumb + "<article>" + content + "</article>"
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
    # 分类卡片
    cat_cards = []
    for cat, name in CATEGORIES.items():
        n = len([a for a in articles if a["category"] == cat])
        cat_cards.append(
            "<a href='/%s/' class='bg-white rounded-xl shadow hover:shadow-lg transition p-6 block'>"
            "<h3 class='text-lg font-bold text-blue-900 mb-1'>%s</h3>"
            "<p class='text-sm text-gray-500'>%d 篇长青 FAQ</p></a>" % (cat, name, n))
    # 文章卡片
    art_cards = []
    for a in articles:
        art_cards.append(
            "<a href='/%s/%s.html' class='bg-white rounded-xl shadow hover:shadow-lg transition p-6 block'>"
            "<span class='text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full'>%s</span>"
            "<h3 class='text-lg font-bold text-blue-900 mt-3 mb-2'>%s</h3>"
            "<p class='text-sm text-gray-600'>%s</p></a>"
            % (a["category"], a["slug"], CATEGORIES[a["category"]], html.escape(a["title"]), html.escape(a["description"])))
    content = (
        "<section class='text-center py-10'>"
        "<h1 class='text-3xl md:text-5xl font-bold text-blue-900 mb-4'>信托知识库</h1>"
        "<p class='text-lg text-gray-600'>专业 · 可信 · 易懂 —— 让信托知识触手可及</p></section>"
        "<section class='grid md:grid-cols-2 gap-5 mb-10'>%s</section>"
        "<h2 class='text-2xl font-bold text-blue-900 mb-4'>全部长青 FAQ</h2>"
        "<div class='grid md:grid-cols-2 gap-5'>%s</div>"
        % ("\n".join(cat_cards), "\n".join(art_cards)))
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
    cards = []
    for a in articles:
        cards.append(
            "<a href='/%s/%s.html' class='bg-white rounded-xl shadow hover:shadow-lg transition p-6 block'>"
            "<h3 class='text-lg font-bold text-blue-900 mb-2'>%s</h3>"
            "<p class='text-sm text-gray-600'>%s</p></a>"
            % (cat, a["slug"], html.escape(a["title"]), html.escape(a["description"])))
    content = ("<nav class='text-xs text-gray-500 mb-4'><a href='/' class='hover:text-blue-700'>首页</a> <span>/</span> %s</nav>"
               "<h1 class='text-3xl font-bold text-blue-900 mb-6'>%s</h1>"
               "<div class='grid gap-5'>%s</div>"
               % (CATEGORIES[cat], CATEGORIES[cat], "\n".join(cards)))
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
    articles = []
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
            outdir = DIST / cat
            outdir.mkdir(parents=True, exist_ok=True)
            (outdir / (slug + ".html")).write_text(render_page(article, faq), encoding="utf-8")
            print("built: /%s/%s.html" % (cat, slug))
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
