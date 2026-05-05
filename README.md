# lark-docindex

用 `lark-cli` 为飞书 / Lark 云文档构建一个轻量、可复用的文档索引层。

它不复制正文、不替代飞书搜索，也不自动删除或改写原文档。它做的事情是：扫描文档元数据，清洗去重，写入多维表格（Base），生成主题导航、推荐阅读、延伸阅读关系和管理仪表盘。

## Features

- 扫描飞书云盘文档元数据，输出本地 JSON 快照
- 清洗、纠偏、去重 URL，避免坏数据写入 Base
- 自动分类主题和标签，计算重要性评分
- 重建一个面向阅读和整理的 Base 索引表
- 生成常用视图：全部文档、推荐阅读、主题导航、待整理、延伸阅读
- 生成 5 个管理仪表盘模块：总文档数、推荐阅读、主题分布、价值结构、来源分布
- 支持 dry-run、断点恢复、瞬时 API 错误重试
- 可选更新 Wiki / Docs 导航卡片

## What This Is Not

- 不是全文搜索引擎
- 不是飞书知识库替代品
- 不是文档备份工具
- 不会自动删除、合并、移动或改写你的原始文档

## Requirements

- Python 3.9+
- 已安装并配置 `lark-cli`
- 当前 `lark-cli` 用户有目标 Base 的读写权限

安装 `lark-cli` 后，请先完成登录授权：

```bash
lark-cli auth login --domain base
lark-cli auth login --domain drive
lark-cli auth login --domain docs
```

实际需要的 scope 取决于你使用的功能。只使用 Base 重建时，至少需要 Base 表、字段、记录、视图和仪表盘相关权限。

## Quick Start

1. 克隆项目：

```bash
git clone https://github.com/<your-name>/lark-docindex.git
cd lark-docindex
```

2. 创建本地环境变量文件：

```bash
cp .env.example .env
```

填入你自己的资源 ID：

```bash
export BASE_TOKEN="app_or_base_token"
export TABLE_ID="source_table_id"
export SOURCE_TABLE_ID="source_table_id"
export V3_TABLE_NAME="文档索引"
export V3_DASHBOARD_NAME="文档索引管理"
```

加载环境变量：

```bash
set -a
source .env
set +a
```

3. 预演重建流程：

```bash
python3 scripts/rebuild_index_v3.py --dry-run
```

4. 创建新的索引表、视图和仪表盘：

```bash
python3 scripts/rebuild_index_v3.py
```

完成后脚本会输出：

```text
table_name=...
table_id=...
dashboard_id=...
```

请把这些值保存到你的 `.env` 或笔记里，后续补配视图/仪表盘时会用到。

## Common Workflows

### 1. 扫描云盘文档

```bash
bash scripts/scan_docs.sh "" data/docs_scanned.json
```

第一个参数是搜索关键词，留空表示按默认搜索策略扫描；第二个参数是输出文件。

### 2. 清洗和校验本地数据

```bash
python3 scripts/normalize_data.py data/docs_scanned.json -o data/docs_clean.json
python3 scripts/validate_data.py data/docs_clean.json
```

如果你想检查原始快照中是否有字段错位、坏 URL 或重复 URL：

```bash
python3 scripts/validate_data.py --raw data/docs_clean.json
```

### 3. 导入已有数据到 Base

```bash
python3 scripts/batch_import.py data/docs_clean.json --dry-run
python3 scripts/batch_import.py data/docs_clean.json
```

该脚本会读取 `BASE_TOKEN` 和 `TABLE_ID`，并跳过已经存在的 URL。

### 4. 计算重要性评分

默认只计算不写入：

```bash
python3 scripts/calculate_scores.py --dry-run
```

确认无误后再写入 Base：

```bash
python3 scripts/calculate_scores.py --apply
```

如果你希望某个 owner 获得轻微加权，可以设置：

```bash
export OWNER_BONUS_KEYWORD="your_name_or_team"
```

### 5. 重建 V3 索引

从源表重建一张新的索引表：

```bash
python3 scripts/rebuild_index_v3.py
```

只给已经存在的目标表补配视图和仪表盘：

```bash
python3 scripts/rebuild_index_v3.py \
  --target-table-id "$TARGET_TABLE_ID" \
  --target-table-name "$TARGET_TABLE_NAME"
```

如果重建中途失败，但记录已经导入成功，可以恢复延伸阅读关系、视图和仪表盘：

```bash
python3 scripts/rebuild_index_v3.py \
  --resume-table-id "$TARGET_TABLE_ID" \
  --resume-table-name "$TARGET_TABLE_NAME"
```

### 6. 可选：更新 Wiki / Docs 导航卡片

`update_cards.py` 需要你提供卡片名称到飞书文档 `obj_token` 的映射。

示例 `cards_map.json`：

```json
{
  "DOCX": "docx_token_for_docx_card",
  "BITABLE": "docx_token_for_bitable_card",
  "AI/图像生成": "docx_token_for_topic_card",
  "最近更新": "docx_token_for_recent_card"
}
```

先 dry-run：

```bash
python3 scripts/update_cards.py --data data/docs_clean.json --dry-run
```

再写入：

```bash
python3 scripts/update_cards.py --data data/docs_clean.json --cards-map cards_map.json
```

## Environment Variables

| Name | Required | Used by | Description |
| --- | --- | --- | --- |
| `BASE_TOKEN` | Yes | Base scripts | 飞书 Base token |
| `TABLE_ID` | Yes for existing table workflows | import / scoring / dashboard v2 | 目标或源表 ID |
| `SOURCE_TABLE_ID` | Yes for V3 rebuild | `rebuild_index_v3.py` | 旧索引源表 ID；未设置时回退到 `TABLE_ID` |
| `V3_TABLE_NAME` | No | `rebuild_index_v3.py` | 新索引表名称，默认 `文档索引` |
| `V3_DASHBOARD_NAME` | No | `rebuild_index_v3.py` | 新仪表盘名称，默认 `文档索引管理` |
| `DASHBOARD_ID` | Yes for dashboard v2 | `sync_dashboard_v2.py` | 需要重建的仪表盘 ID |
| `TABLE_NAME` | No | dashboard scripts | 仪表盘 data_config 使用的表名 |
| `OWNER_BONUS_KEYWORD` | No | scoring/import | 评分 owner 加权关键词 |

## Base Schema

V3 索引表默认创建以下字段：

- `标题`
- `链接`
- `主题`
- `标签`
- `价值等级`
- `状态`
- `来源`
- `类型`
- `所有者`
- `重要性`
- `延伸阅读理由`
- `原记录ID`
- `相关文档`

默认视图：

- `全部文档`
- `推荐阅读`
- `主题导航`
- `待整理`
- `延伸阅读`

默认仪表盘模块：

- `总文档数`
- `推荐阅读`
- `主题分布`
- `价值结构`
- `来源分布`

## Project Structure

```text
lark-docindex/
  README.md
  .env.example
  SKILL.md
  scripts/
    scan_docs.sh
    normalize_data.py
    validate_data.py
    batch_import.py
    build_index.py
    calculate_scores.py
    rebuild_index_v3.py
    sync_dashboard_v2.py
    update_cards.py
    docindex_lib.py
  data/
    # local snapshots, ignored by git
```

## Safety Notes

- `data/*.json` 默认被 `.gitignore` 忽略，避免把你的私人文档索引快照提交到仓库。
- `.env` 默认应加入 `.gitignore`，不要提交 Base token、table ID、dashboard ID 等私人资源信息。
- 所有会写入飞书的脚本都建议先运行 `--dry-run`。
- 本项目只写索引表、视图、仪表盘和可选导航卡片，不会修改原始文档正文。

## Development Checks

语法检查：

```bash
python3 -B -c "from pathlib import Path; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in Path('scripts').glob('*.py')]; print('syntax OK')"
```

本地数据校验：

```bash
python3 scripts/validate_data.py data/docs_clean.json
```

V3 重建 dry-run：

```bash
python3 scripts/rebuild_index_v3.py --dry-run
```

## License

MIT. See [LICENSE](LICENSE).
