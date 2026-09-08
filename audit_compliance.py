#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trustfacai-wiki 合规审计脚本
- 扫描范围: src/content/**/*.md, src/templates/*, dist/**/*.{html,txt}
- 黑名单: 核心禁止词 / 同业信托公司名 / 违规销售承诺词
- 模式:
    python audit_compliance.py          # 只读扫描, 输出审计报告
    python audit_compliance.py --fix    # 对 src/ 源文件自动脱敏替换 (dist 由 build.py 重新生成)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
DIST = ROOT / "dist"

# ---------------------------------------------------------------
# 黑名单词库: (敏感词, 类别, 替换值)  替换值 None = 彻底删除
# ---------------------------------------------------------------
BANNED = [
    # 1. 核心禁止词（最高优先级）
    ("大生·尊享", "核心禁止-产品名", "标准化家族信托"),
    ("国通信托", "核心禁止-公司名", "持牌信托机构"),
    ("国通", "核心禁止-公司名", "持牌信托机构"),
    ("武汉金控", "核心禁止-机构名", None),          # 机构名 → 彻底删除
    ("鼎力多资产", "核心禁止-产品名", "某标杆产品"),
    ("鼎力", "核心禁止-产品名", "某标杆产品"),       # 裸品牌名兜底
    ("400-886-0786", "核心禁止-内部电话", None),    # 内部电话 → 彻底删除
    # 2. 同业信托公司名称
    ("中信信托", "同业公司名", "某信托公司"),
    ("平安信托", "同业公司名", "某信托公司"),
    ("中融信托", "同业公司名", "某信托公司"),
    ("华润信托", "同业公司名", "某信托公司"),
    ("建信信托", "同业公司名", "某信托公司"),
    ("五矿信托", "同业公司名", "某信托公司"),
    ("外贸信托", "同业公司名", "某信托公司"),
    ("中航信托", "同业公司名", "某信托公司"),
    ("陕国投", "同业公司名", "某信托公司"),
    ("重庆信托", "同业公司名", "某信托公司"),
    ("光大信托", "同业公司名", "某信托公司"),
    ("山东信托", "同业公司名", "某信托公司"),
    ("交银国际信托", "同业公司名", "某信托公司"),
    ("兴业信托", "同业公司名", "某信托公司"),
    # 3. 违规销售承诺词
    ("保本保息", "销售承诺", "稳健运作"),
    ("稳赚不赔", "销售承诺", "稳健收益"),
    ("规避遗产税", "违规税务表述", "合规税务安排"),
    ("避税", "违规税务表述", "合规节税"),
    ("逃税", "违规税务表述", "税收违法"),
    ("刚性兑付", "销售承诺", "刚性兑付预期"),
]

# 正则规则: (pattern, 替换值) —— 按顺序执行, 长句优先
REGEX_RULES = [
    # --- 句级脱敏（语境化重写, 避免破坏警示句语义） ---
    (r"严禁说[“”\"]避税[“”\"]", "严禁出现涉税违规表述"),
    (r"[“”\"]随便套个壳就能避税[“”\"]", "“随便套个壳就能获得税务优势”"),
    (r"[“”\"]能避税[“”\"]的承诺", "涉税违规的承诺"),
    (r"用违法所得、偷逃税款的钱做信托", "用违法所得的钱做信托"),
    # --- 鼎力产品品牌脱敏（长词优先） ---
    (r"比如鼎力多资产模型", "比如某持牌机构的多资产模型"),
    (r"而鼎力模型通过", "而某持牌机构的多资产模型通过"),
    (r"鼎力多资产动态调仓模型", "多资产动态调仓模型"),
    (r"鼎力多资产模型", "多资产动态调仓模型"),
    (r"鼎力模型", "某持牌机构的多资产模型"),
    (r"鼎力", "某标杆产品"),
    # --- 通用正则 ---
    (r"[\u4e00-\u9fa5A-Za-z0-9]{2,12}信托有限责任公司", "持牌信托机构"),
    (r"[（(][^（）()]*400[-‐–―—]886[-‐–―—]0786[^（）()]*[）)]", ""),   # 带括号的电话 → 连括号删除
]

# 句级修正表（普通字符串替换, 在正则之后兜底）
SENTENCE_FIXES = []

# 按敏感词长度降序，保证长词优先命中
BANNED_SORTED = sorted(BANNED, key=lambda x: len(x[0]), reverse=True)


def scan_files():
    """收集待扫描文件: (路径, 类型)"""
    files = []
    if (SRC / "content").exists():
        files += [(p, "md") for p in sorted((SRC / "content").rglob("*.md"))]
    if (SRC / "templates").exists():
        files += [(p, "tpl") for p in sorted((SRC / "templates").iterdir()) if p.is_file()]
    if DIST.exists():
        files += [(p, "dist") for p in sorted(DIST.rglob("*")) if p.is_file() and p.suffix in (".html", ".txt")]
    return files


def find_hits(text):
    """返回 [(敏感词, 类别, 行号, 上下文)]"""
    hits = []
    lines = text.split("\n")
    for word, cat, _ in BANNED_SORTED:
        for i, line in enumerate(lines, 1):
            for m in re.finditer(re.escape(word), line):
                s = max(0, m.start() - 25)
                e = min(len(line), m.end() + 25)
                ctx = ("…" if s > 0 else "") + line[s:e] + ("…" if e < len(line) else "")
                hits.append((word, cat, i, ctx))
    for pat, _ in REGEX_RULES:
        for i, line in enumerate(lines, 1):
            for m in re.finditer(pat, line):
                s = max(0, m.start() - 25)
                e = min(len(line), m.end() + 25)
                ctx = ("…" if s > 0 else "") + line[s:e] + ("…" if e < len(line) else "")
                hits.append((m.group(0), "正则规则", i, ctx))
    return hits


def apply_fix(text):
    """对源文本执行脱敏替换, 返回 (新文本, 变更明细[(前, 后)])"""
    changes = []
    original = text
    # 正则规则先行
    for pat, rep in REGEX_RULES:
        text = re.sub(pat, rep, text)
    # 句级修正（在词替换前, 处理已知语境）
    for a, b in SENTENCE_FIXES:
        if a in text:
            changes.append((a, b))
            text = text.replace(a, b)
    # 词级替换（长词优先）
    for word, cat, rep in BANNED_SORTED:
        if word in text:
            changes.append((word, rep if rep is not None else "(已删除)"))
            text = text.replace(word, rep if rep is not None else "")
    # 清理删除后的残留标点
    text = re.sub(r"[，,]{2,}", "，", text)
    text = re.sub(r"[（(]\s*[）)]", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    if text != original:
        pass
    return text, changes


def main():
    fix = "--fix" in sys.argv
    files = scan_files()
    all_hits = []
    for path, kind in files:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        hits = find_hits(text)
        for word, cat, ln, ctx in hits:
            all_hits.append((path, kind, word, cat, ln, ctx))

    print("=" * 72)
    print("肥姐问财 trustfacai.com · 全站合规审计报告")
    print("=" * 72)
    print(f"扫描文件数: {len(files)}  (src/content/*.md + src/templates/* + dist/*)")

    if not all_hits:
        print()
        print("✅ 全站扫描完毕，未发现任何信托公司名称及违规词汇！")
        return 0

    print(f"\n发现敏感命中 {len(all_hits)} 处：\n")
    for path, kind, word, cat, ln, ctx in all_hits:
        rel = path.relative_to(ROOT)
        print(f"【{rel}】行{ln}  敏感词「{word}」({cat})")
        print(f"    上下文: {ctx}")

    if not fix:
        print("\n-- 未执行修复（只读扫描）。运行 python audit_compliance.py --fix 执行自动脱敏。 --")
        return 1

    # ---- fix 模式: 只修改 src/ 源文件 ----
    print("\n" + "-" * 72)
    print("执行自动脱敏（仅修改 src/ 源文件，dist 由 build.py 重新生成）\n")
    changed_files = 0
    for path, kind, word, cat, ln, ctx in all_hits:
        if kind == "dist":
            continue  # dist 由 build 重新生成, 不手改
        text = path.read_text(encoding="utf-8")
        new_text, changes = apply_fix(text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed_files += 1
            print(f"已修复: {path.relative_to(ROOT)}")
            for a, b in changes:
                print(f"    「{a}」 → 「{b}」")
    print(f"\n共修复 {changed_files} 个源文件。")
    print("下一步: python build.py && python update_server.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
