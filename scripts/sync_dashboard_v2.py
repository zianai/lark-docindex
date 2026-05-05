#!/usr/bin/env python3
"""Sync agent-audited dashboard fields and rebuild the Base dashboard V2."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from docindex_lib import clean_title, scalar_value


BASE_TOKEN = os.environ.get("BASE_TOKEN", "")
TABLE_ID = os.environ.get("TABLE_ID", "")
DASHBOARD_ID = os.environ.get("DASHBOARD_ID", "")
TABLE_NAME = os.environ.get("TABLE_NAME", "文档索引")

REVIEW_CONFIDENCE = 0.7
HIGH_VALUE_SCORE = 3.5

SEED_TOPICS = [
    "AI/图像生成",
    "开源/教程",
    "Agent/产品",
    "飞书CLI",
    "比赛/活动",
    "工作/效率",
    "产品/设计",
    "开发/工程",
    "生活/其他",
    "未分类",
]

TOPIC_ALIASES = {
    "AI": "AI/图像生成",
    "图像生成": "AI/图像生成",
    "视频": "AI/图像生成",
    "开源": "开源/教程",
    "教程": "开源/教程",
    "Agent": "Agent/产品",
    "产品": "Agent/产品",
    "比赛": "比赛/活动",
    "生活": "生活/其他",
}

DYNAMIC_TOPIC_RULES = [
    ("跨境电商", ["跨境", "电商", "爬虫", "评论分析"], 0.82),
    ("提示词/技能", ["提示词", "prompt", "system prompt", "skill", "skills"], 0.82),
    ("AI哲学", ["哲学", "伦理", "经济学", "本质", "价值", "趋势"], 0.8),
    ("内容创作", ["自媒体", "公众号", "写作", "短剧", "漫剧", "影视", "分镜"], 0.8),
    ("课程纪要", ["智能纪要", "直播回放", "课程", "课后作业", "训练营"], 0.78),
    ("商业/运营", ["运营", "管理", "商业", "公司", "效率", "项目"], 0.76),
]

SELECT_FIELDS = {
    "主题大类": SEED_TOPICS,
    "分类来源": ["规则命中", "Agent判断", "人工修正"],
    "价值档位": ["高价值", "中价值", "低价值", "未评分"],
}

TEXT_FIELDS = ["Agent建议主题", "分类理由", "仪表盘标题"]
NUMBER_FIELDS = ["分类置信度"]

PALETTE = [
    ("Blue", "Lighter"),
    ("Orange", "Lighter"),
    ("Wathet", "Lighter"),
    ("Yellow", "Lighter"),
    ("Turquoise", "Lighter"),
    ("Red", "Lighter"),
    ("Purple", "Lighter"),
    ("Green", "Lighter"),
    ("Carmine", "Lighter"),
    ("Lime", "Lighter"),
    ("Gray", "Lighter"),
]


def cli(args: list[str], timeout: int = 60, dry_run: bool = False) -> dict[str, Any]:
    if dry_run and any(part in args for part in ["+field-create", "+field-update", "+record-upsert", "+dashboard-block-delete", "+dashboard-block-create", "+dashboard-arrange"]):
        print("DRY RUN:", " ".join(args))
        return {"ok": True, "dry_run": True}
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    output = proc.stdout.strip() or proc.stderr.strip()
    try:
        payload = json.loads(output[output.find("{"):])
    except Exception as exc:
        raise RuntimeError(f"Command did not return JSON: {' '.join(args)}\n{output}") from exc
    if proc.returncode != 0 or payload.get("ok") is False:
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{json.dumps(payload, ensure_ascii=False, indent=2)}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def field_options(field: dict[str, Any]) -> list[str]:
    return [option.get("name", "") for option in field.get("options", []) if option.get("name")]


def option_payload(names: list[str], existing: dict[str, dict[str, Any]] | None = None) -> list[dict[str, str]]:
    payload = []
    existing = existing or {}
    for index, name in enumerate(dict.fromkeys(names)):
        current = existing.get(name, {})
        hue, lightness = PALETTE[index % len(PALETTE)]
        payload.append(
            {
                "name": name,
                "hue": current.get("hue", hue),
                "lightness": current.get("lightness", lightness),
            }
        )
    return payload


def fetch_fields() -> dict[str, dict[str, Any]]:
    payload = cli(["lark-cli", "base", "+field-list", "--base-token", BASE_TOKEN, "--table-id", TABLE_ID])
    return {field["name"]: field for field in payload["data"]["fields"]}


def ensure_base_fields(dry_run: bool = False) -> dict[str, dict[str, Any]]:
    fields = fetch_fields()

    for name in TEXT_FIELDS:
        if name not in fields:
            cli(
                [
                    "lark-cli",
                    "base",
                    "+field-create",
                    "--base-token",
                    BASE_TOKEN,
                    "--table-id",
                    TABLE_ID,
                    "--json",
                    json.dumps({"name": name, "type": "text"}, ensure_ascii=False),
                ],
                dry_run=dry_run,
            )

    for name in NUMBER_FIELDS:
        if name not in fields:
            cli(
                [
                    "lark-cli",
                    "base",
                    "+field-create",
                    "--base-token",
                    BASE_TOKEN,
                    "--table-id",
                    TABLE_ID,
                    "--json",
                    json.dumps({"name": name, "type": "number"}, ensure_ascii=False),
                ],
                dry_run=dry_run,
            )

    fields = fetch_fields()
    for name, options in SELECT_FIELDS.items():
        if name not in fields:
            body = {"name": name, "type": "select", "multiple": False, "options": option_payload(options)}
            cli(
                [
                    "lark-cli",
                    "base",
                    "+field-create",
                    "--base-token",
                    BASE_TOKEN,
                    "--table-id",
                    TABLE_ID,
                    "--json",
                    json.dumps(body, ensure_ascii=False),
                ],
                dry_run=dry_run,
            )

    return fetch_fields()


def planned_fields(fields: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Add synthetic field definitions so dry-run can continue after planned creates."""
    result = dict(fields)
    for name in TEXT_FIELDS:
        result.setdefault(name, {"id": f"dry_{name}", "name": name, "type": "text"})
    for name in NUMBER_FIELDS:
        result.setdefault(name, {"id": f"dry_{name}", "name": name, "type": "number"})
    for name, options in SELECT_FIELDS.items():
        result.setdefault(
            name,
            {
                "id": f"dry_{name}",
                "name": name,
                "type": "select",
                "multiple": False,
                "options": option_payload(options),
            },
        )
    return result


def ensure_select_options(field: dict[str, Any], required: list[str], dry_run: bool = False) -> None:
    existing_options = {option["name"]: option for option in field.get("options", []) if option.get("name")}
    merged_names = list(existing_options) + [name for name in required if name not in existing_options]
    if len(merged_names) == len(existing_options):
        return
    body = {
        "name": field["name"],
        "type": "select",
        "multiple": field.get("multiple", False),
        "options": option_payload(merged_names, existing_options),
    }
    cli(
        [
            "lark-cli",
            "base",
            "+field-update",
            "--base-token",
            BASE_TOKEN,
            "--table-id",
            TABLE_ID,
            "--field-id",
            field["id"],
            "--json",
            json.dumps(body, ensure_ascii=False),
        ],
        dry_run=dry_run,
    )


def fetch_records(limit: int = 200) -> tuple[list[str], list[dict[str, Any]]]:
    offset = 0
    fields: list[str] = []
    records: list[dict[str, Any]] = []
    while True:
        payload = cli(
            [
                "lark-cli",
                "base",
                "+record-list",
                "--base-token",
                BASE_TOKEN,
                "--table-id",
                TABLE_ID,
                "--limit",
                str(limit),
                "--offset",
                str(offset),
                "--format",
                "json",
            ],
            timeout=120,
        )
        data = payload["data"]
        if not fields:
            fields = data["fields"]
        rows = data.get("data", [])
        ids = data.get("record_id_list", [])
        for record_id, row in zip(ids, rows):
            records.append({"record_id": record_id, "fields": dict(zip(fields, row))})
        if len(rows) < limit:
            break
        offset += limit
        if offset > 10000:
            raise RuntimeError("Pagination exceeded safety limit")
    return fields, records


def cell(value: Any) -> Any:
    return scalar_value(value)


def as_float(value: Any) -> float | None:
    value = cell(value)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def title_for_dashboard(title: str, max_len: int = 44) -> str:
    text = clean_title(title)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def value_tier(score: float | None) -> str:
    if score is None:
        return "未评分"
    if score >= HIGH_VALUE_SCORE:
        return "高价值"
    if score >= 2.5:
        return "中价值"
    return "低价值"


def normalize_topic(raw: Any) -> str:
    topic = str(cell(raw) or "").strip()
    return TOPIC_ALIASES.get(topic, topic)


def classify_topic(title: str, tag: Any, existing_topic: Any, existing_source: Any) -> dict[str, Any]:
    source = str(cell(existing_source) or "")
    manual_topic = normalize_topic(existing_topic)
    if source == "人工修正" and manual_topic:
        return {
            "topic": manual_topic,
            "suggested": manual_topic,
            "confidence": 1.0,
            "source": "人工修正",
            "reason": "保留人工修正分类",
        }

    tag_topic = normalize_topic(tag)
    if tag_topic in SEED_TOPICS and tag_topic not in {"生活/其他", "未分类"}:
        return {
            "topic": tag_topic,
            "suggested": tag_topic,
            "confidence": 0.95,
            "source": "规则命中",
            "reason": f"标签命中 {tag_topic}",
        }

    lower_title = title.lower()
    for topic, keywords, confidence in DYNAMIC_TOPIC_RULES:
        for keyword in keywords:
            if keyword.lower() in lower_title:
                return {
                    "topic": topic,
                    "suggested": topic,
                    "confidence": confidence,
                    "source": "Agent判断",
                    "reason": f"标题关键词「{keyword}」提示该主题",
                }

    if tag_topic == "生活/其他":
        return {
            "topic": "生活/其他",
            "suggested": "生活/其他",
            "confidence": 0.68,
            "source": "Agent判断",
            "reason": "旧标签为生活/其他，语义较宽，建议复核",
        }

    return {
        "topic": "未分类",
        "suggested": "未分类",
        "confidence": 0.5,
        "source": "Agent判断",
        "reason": "未命中主题规则，等待 agent 或人工复核",
    }


def derive_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    title_counts = Counter(title_for_dashboard(record["fields"].get("标题", "")) for record in records)
    seen_titles: Counter[str] = Counter()
    derived = []
    for record in records:
        fields = record["fields"]
        title = clean_title(fields.get("标题", ""))
        dashboard_title = title_for_dashboard(title)
        if title_counts[dashboard_title] > 1:
            owner = str(cell(fields.get("所有者")) or "").strip()
            suffix = owner or record["record_id"][-6:]
            dashboard_title = title_for_dashboard(f"{dashboard_title} | {suffix}", max_len=54)
        seen_titles[dashboard_title] += 1
        if seen_titles[dashboard_title] > 1:
            dashboard_title = title_for_dashboard(f"{dashboard_title} #{seen_titles[dashboard_title]}", max_len=58)

        score = as_float(fields.get("重要性"))
        topic = classify_topic(title, fields.get("标签"), fields.get("主题大类"), fields.get("分类来源"))
        patch = {
            "主题大类": topic["topic"],
            "Agent建议主题": topic["suggested"],
            "分类置信度": round(float(topic["confidence"]), 2),
            "分类来源": topic["source"],
            "分类理由": topic["reason"],
            "价值档位": value_tier(score),
            "仪表盘标题": dashboard_title,
        }
        derived.append({"record_id": record["record_id"], "patch": patch, "title": title})
    return derived


def patch_changed(current: dict[str, Any], patch: dict[str, Any]) -> bool:
    for key, value in patch.items():
        existing = cell(current.get(key))
        if isinstance(value, float):
            try:
                if round(float(existing), 2) == value:
                    continue
            except (TypeError, ValueError):
                return True
        elif existing == value:
            continue
        return True
    return False


def sync_record_fields(records: list[dict[str, Any]], derived: list[dict[str, Any]], dry_run: bool = False) -> int:
    by_id = {record["record_id"]: record for record in records}
    updated = 0
    if dry_run:
        samples = []
        for item in derived:
            current = by_id[item["record_id"]]["fields"]
            if patch_changed(current, item["patch"]):
                updated += 1
                if len(samples) < 5:
                    samples.append({"record_id": item["record_id"], "title": item["title"], "patch": item["patch"]})
        print(f"DRY RUN: 将回填 {updated}/{len(derived)} 条记录派生字段")
        for sample in samples:
            print("DRY RUN sample:", json.dumps(sample, ensure_ascii=False))
        return updated

    for index, item in enumerate(derived, start=1):
        current = by_id[item["record_id"]]["fields"]
        patch = item["patch"]
        if not patch_changed(current, patch):
            continue
        cli(
            [
                "lark-cli",
                "base",
                "+record-upsert",
                "--base-token",
                BASE_TOKEN,
                "--table-id",
                TABLE_ID,
                "--record-id",
                item["record_id"],
                "--json",
                json.dumps(patch, ensure_ascii=False),
            ],
            timeout=60,
            dry_run=dry_run,
        )
        updated += 1
        if updated % 50 == 0:
            print(f"  已回填 {updated} 条派生字段...")
    print(f"派生字段回填完成: {updated}/{len(derived)} 条需要更新")
    return updated


def backup_dashboard(blocks: list[dict[str, Any]], dry_run: bool = False) -> Path | None:
    if dry_run:
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path("data") / f"dashboard_v1_backup_{timestamp}.json"
    dashboard = cli(
        [
            "lark-cli",
            "base",
            "+dashboard-get",
            "--base-token",
            BASE_TOKEN,
            "--dashboard-id",
            DASHBOARD_ID,
            "--format",
            "json",
        ],
        timeout=60,
    )
    block_details = []
    for block in blocks:
        try:
            detail = cli(
                [
                    "lark-cli",
                    "base",
                    "+dashboard-block-get",
                    "--base-token",
                    BASE_TOKEN,
                    "--dashboard-id",
                    DASHBOARD_ID,
                    "--block-id",
                    block["block_id"],
                    "--format",
                    "json",
                ],
                timeout=60,
            )
        except Exception as exc:
            detail = {"error": str(exc), "block": block}
        block_details.append(detail)
    write_json(backup_path, {"dashboard": dashboard, "blocks": block_details})
    print(f"已备份旧仪表盘配置: {backup_path}")
    return backup_path


def current_blocks() -> list[dict[str, Any]]:
    payload = cli(
        [
            "lark-cli",
            "base",
            "+dashboard-block-list",
            "--base-token",
            BASE_TOKEN,
            "--dashboard-id",
            DASHBOARD_ID,
            "--page-size",
            "100",
            "--format",
            "json",
        ],
        timeout=60,
    )
    return payload["data"]["items"]


def dashboard_blocks_v2() -> list[dict[str, Any]]:
    return [
        {"name": "总索引数", "type": "statistics", "data_config": {"table_name": TABLE_NAME, "count_all": True}},
        {
            "name": "高价值文档",
            "type": "statistics",
            "data_config": {
                "table_name": TABLE_NAME,
                "count_all": True,
                "filter": {
                    "conjunction": "and",
                    "conditions": [{"field_name": "重要性", "operator": "isGreaterEqual", "value": HIGH_VALUE_SCORE}],
                },
            },
        },
        {
            "name": "待复核分类",
            "type": "statistics",
            "data_config": {
                "table_name": TABLE_NAME,
                "count_all": True,
                "filter": {
                    "conjunction": "or",
                    "conditions": [
                        {"field_name": "分类置信度", "operator": "isLess", "value": REVIEW_CONFIDENCE},
                        {"field_name": "主题大类", "operator": "isEmpty"},
                    ],
                },
            },
        },
        {
            "name": "高价值文档排行",
            "type": "bar",
            "data_config": {
                "table_name": TABLE_NAME,
                "series": [{"field_name": "重要性", "rollup": "MAX"}],
                "group_by": [{"field_name": "仪表盘标题", "mode": "integrated", "sort": {"type": "value", "order": "desc"}}],
                "filter": {"conjunction": "and", "conditions": [{"field_name": "价值档位", "operator": "is", "value": "高价值"}]},
            },
        },
        {
            "name": "主题浏览",
            "type": "bar",
            "data_config": {
                "table_name": TABLE_NAME,
                "count_all": True,
                "group_by": [{"field_name": "主题大类", "mode": "integrated", "sort": {"type": "value", "order": "desc"}}],
            },
        },
        {
            "name": "高价值主题",
            "type": "column",
            "data_config": {
                "table_name": TABLE_NAME,
                "series": [{"field_name": "重要性", "rollup": "AVERAGE"}],
                "group_by": [{"field_name": "主题大类", "mode": "integrated", "sort": {"type": "value", "order": "desc"}}],
                "filter": {"conjunction": "and", "conditions": [{"field_name": "重要性", "operator": "isGreaterEqual", "value": 0}]},
            },
        },
        {
            "name": "来源质量",
            "type": "bar",
            "data_config": {
                "table_name": TABLE_NAME,
                "series": [{"field_name": "重要性", "rollup": "AVERAGE"}],
                "group_by": [{"field_name": "来源", "mode": "integrated", "sort": {"type": "value", "order": "desc"}}],
                "filter": {"conjunction": "and", "conditions": [{"field_name": "重要性", "operator": "isGreaterEqual", "value": 0}]},
            },
        },
        {
            "name": "说明",
            "type": "text",
            "data_config": {
                "text": "文档发现工作台。高价值 = 重要性 >= 3.5。主题大类由 agent 自动维护；低置信分类会进入待复核。本看板用于优先发现值得阅读、整理和复用的文档。"
            },
        },
    ]


def rebuild_dashboard(dry_run: bool = False) -> None:
    blocks = current_blocks()
    backup_dashboard(blocks, dry_run=dry_run)
    print(f"准备删除旧组件: {len(blocks)} 个")
    for block in blocks:
        cli(
            [
                "lark-cli",
                "base",
                "+dashboard-block-delete",
                "--base-token",
                BASE_TOKEN,
                "--dashboard-id",
                DASHBOARD_ID,
                "--block-id",
                block["block_id"],
                "--yes",
            ],
            timeout=60,
            dry_run=dry_run,
        )
        time.sleep(1.0)

    print("开始创建 V2 组件...")
    for block in dashboard_blocks_v2():
        cli(
            [
                "lark-cli",
                "base",
                "+dashboard-block-create",
                "--base-token",
                BASE_TOKEN,
                "--dashboard-id",
                DASHBOARD_ID,
                "--name",
                block["name"],
                "--type",
                block["type"],
                "--data-config",
                json.dumps(block["data_config"], ensure_ascii=False),
            ],
            timeout=60,
            dry_run=dry_run,
        )
        print(f"  created: {block['name']}")
        time.sleep(1.0)

    cli(
        [
            "lark-cli",
            "base",
            "+dashboard-arrange",
            "--base-token",
            BASE_TOKEN,
            "--dashboard-id",
            DASHBOARD_ID,
        ],
        timeout=60,
        dry_run=dry_run,
    )
    print("仪表盘 V2 重建完成")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print mutating commands without executing them")
    parser.add_argument("--skip-fields", action="store_true", help="do not create/sync derived fields")
    parser.add_argument("--skip-dashboard", action="store_true", help="do not rebuild dashboard blocks")
    return parser.parse_args()


def require_env() -> None:
    missing = [name for name, value in (("BASE_TOKEN", BASE_TOKEN), ("TABLE_ID", TABLE_ID), ("DASHBOARD_ID", DASHBOARD_ID)) if not value]
    if missing:
        raise SystemExit(f"missing required environment variable(s): {', '.join(missing)}")


def main() -> int:
    args = parse_args()
    require_env()
    print("=== lark-docindex dashboard V2 sync ===")
    print(f"Base={BASE_TOKEN} Table={TABLE_ID} Dashboard={DASHBOARD_ID}")

    if not args.skip_fields:
        print("\n[1/2] 准备派生字段...")
        fields = ensure_base_fields(dry_run=args.dry_run)
        if args.dry_run:
            fields = planned_fields(fields)
        _, records = fetch_records()
        derived = derive_records(records)
        required_topics = SEED_TOPICS + sorted({item["patch"]["主题大类"] for item in derived})
        fields = fetch_fields() if not args.dry_run else planned_fields(fields)
        ensure_select_options(fields["主题大类"], required_topics, dry_run=args.dry_run)
        ensure_select_options(fields["分类来源"], SELECT_FIELDS["分类来源"], dry_run=args.dry_run)
        ensure_select_options(fields["价值档位"], SELECT_FIELDS["价值档位"], dry_run=args.dry_run)
        fields = fetch_fields() if not args.dry_run else planned_fields(fields)
        print(f"记录数: {len(records)}；主题选项数: {len(field_options(fields['主题大类']))}")
        sync_record_fields(records, derived, dry_run=args.dry_run)

    if not args.skip_dashboard:
        print("\n[2/2] 重建仪表盘...")
        rebuild_dashboard(dry_run=args.dry_run)

    print("\n完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
