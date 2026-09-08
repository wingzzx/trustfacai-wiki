# trustfacai-wiki

肥姐问财（trustfacai.com）信托知识库 —— Git 驱动的静态站点工程。

## 技术栈
- 纯静态 HTML + Tailwind CSS（CDN）
- Python 构建脚本（无外部依赖）
- Schema.org 结构化数据（FAQPage + BreadcrumbList + Person）
- 面向 AI 爬虫的 llms.txt / llms-full.txt

## 目录结构
```
src/
  content/          # 纯 Markdown 原文（按分类存放）
    family-trust/       # 家族信托与代际传承
    debt-isolation/     # 企业债务与家企隔离
    marriage-protection/# 婚姻与子女财富保全
    wealth-allocation/  # 低利率时代与资产承接
  templates/        # 导航、页脚、基础骨架模板
build.py            # 静态站点构建器
dist/               # 构建输出（gitignore）
```

## 使用
```bash
# 构建全站
python build.py

# 输出到 dist/
# 包含：HTML 页面、sitemap.xml、robots.txt、llms.txt、llms-full.txt
```

## 内容格式
每篇 Markdown 以 YAML Frontmatter 开头：
```yaml
---
title: 文章标题
description: SEO 描述
keywords: 关键词1,关键词2
category: family-trust
date: 2026-09-08
slug: what-is-standard-family-trust
---
```
文末用 `## FAQ` + `**Q:**` / `**A:**` 成对列出常见问题，自动生成 FAQPage Schema。

## 部署
构建产物同步到服务器 `/var/www/trustfacai/`，由 Nginx 托管，SSL 由 Let's Encrypt 自动续期。
