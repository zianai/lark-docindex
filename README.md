# lark-docindex

飞书云文档智能索引系统 -- 基于飞书 CLI 构建的三层文档导航方案。

## 项目简介

飞书云文档散落在不同知识空间、聊天记录、云盘文件夹中，查找困难。
lark-docindex 通过飞书 CLI 自动扫描、结构化索引、分类导航，一键解决文档发现和管理痛点。

灵感来自 Karpathy 的 LLM Wiki 模式：不复制原始内容，而是建立索引层（超链接到原文）。

## 三层架构

```
+------------------+
|  导航层 (Wiki)    |  分类浏览入口 + AI 索引卡片
+------------------+
        |
+------------------+
|  数据层 (Base)    |  结构化元数据 + 仪表盘可视化
+------------------+
        |
+------------------+
|  原始源 (云文档)   |  飞书云盘中的原始文档保持不动
+------------------+
```

## 当前规模

- 已收录：51 篇文档
- 文档类型：DOCX(46) / BITABLE(5)
- 主题分类：AI/图像生成 / 开源/教程 / 生活/其他 / Agent/产品 / 飞书CLI / 比赛/活动
- 仪表盘：7 个可视化区块（指标卡 + 饼图 + 条形图 + 柱状图 + 环形图 + 漏斗图 + 文本说明）

## 资源链接

- Base 仪表盘：https://feishu.cn/base/KgBBbaBGJaP1tvsjVd6cU79Rnmc
- Wiki 空间：space_id=7636032943726545882

## 目录结构

```
lark-docindex/
  README.md            -- 项目说明
  SKILL.md             -- 飞书 CLI 完整开发指南（参赛核心文档）
  data/                -- 数据快照
    docs.json          -- 原始文档元数据（18条初始集）
    docs_all.json      -- 全量文档元数据（51条）
    docs_grouped.json  -- 按类型/主题分组数据
    cards_data.json    -- 索引卡片生成数据
    final_data.json    -- 最终清洗后数据
  scripts/             -- 自动化脚本
    scan_docs.sh       -- 扫描飞书云盘文档
    build_index.py     -- 构建 Base 索引 + Wiki 卡片
    update_cards.py    -- 更新索引卡片内容
```

## 技术栈

- 飞书 CLI (lark-cli v1.0.23)
- 飞书开放平台 API（Base / Wiki / Docs / Drive）
- AI Agent 辅助（Hermes + GLM）

## 参赛信息

飞书 CLI 创作者大赛（飞书CLI创作者大赛） -- 角逐最佳实践奖
