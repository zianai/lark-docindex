#!/usr/bin/env python3
"""Rebuild a clean human-facing document index table and dashboard."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from docindex_lib import clean_title, scalar_value


BASE_TOKEN = os.environ.get("BASE_TOKEN", "")
SOURCE_TABLE_ID = os.environ.get("SOURCE_TABLE_ID", os.environ.get("TABLE_ID", ""))
TABLE_NAME = os.environ.get("V3_TABLE_NAME", "文档索引")
DASHBOARD_NAME = os.environ.get("V3_DASHBOARD_NAME", "文档索引管理")

HIGH_VALUE_SCORE = 3.5
MEDIUM_VALUE_SCORE = 2.5
MAX_RELATED = 5
CLI_RETRIES = 3
CLI_RETRY_DELAY = 2.0

TOPICS = [
    "AI/图像生成",
    "开源/教程",
    "Agent/产品",
    "飞书CLI",
    "工作/效率",
    "产品/设计",
    "开发/工程",
    "内容创作",
    "商业/运营",
    "提示词/技能",
    "课程纪要",
    "跨境电商",
    "AI哲学",
    "比赛/活动",
    "生活/其他",
    "未分类",
]

VALUE_LEVELS = ["推荐阅读", "普通参考", "存档", "待判断"]
STATUSES = ["待整理", "已整理", "待复核", "已归档"]
SOURCES = ["云盘", "Wiki", "Drive", "聊天", "共享链接", "外部链接"]
TYPES = ["docx", "bitable", "sheet", "mindnote", "slides", "file", "DOCX", "BITABLE", "SHEET", "MINDNOTE", "FILE"]

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

TOPIC_RULES = [
    ("跨境电商", ["跨境", "电商", "爬虫", "评论分析", "选品"]),
    ("提示词/技能", ["提示词", "prompt", "system prompt", "skill", "skills"]),
    ("课程纪要", ["智能纪要", "直播回放", "课程", "课后作业", "训练营"]),
    ("内容创作", ["自媒体", "公众号", "写作", "短剧", "漫剧", "影视", "分镜"]),
    ("商业/运营", ["运营", "管理", "商业", "公司", "增长"]),
    ("AI哲学", ["哲学", "伦理", "经济学", "本质", "价值", "趋势"]),
    ("飞书CLI", ["飞书", "lark", "feishu", "cli", "多维表格", "base"]),
    ("开发/工程", ["开发", "工程", "架构", "代码", "python", "github", "api", "部署"]),
    ("产品/设计", ["设计", "ui", "ux", "figma", "原型", "产品方案"]),
    ("Agent/产品", ["agent", "hermes", "产品", "需求", "mvp", "saas"]),
    ("AI/图像生成", ["ai", "gpt", "image", "图像", "生图", "视频生成", "seedance", "midjourney"]),
    ("开源/教程", ["开源", "教程", "指南", "入门", "安装", "配置", "openclaw", "trae"]),
    ("比赛/活动", ["比赛", "大赛", "活动", "黑客松", "切磋"]),
    ("工作/效率", ["工作", "效率", "项目", "okr", "日报", "周报"]),
]


def is_transient_error(text: str) -> bool:
    lower = text.lower()
    return any(
        marker in lower
        for marker in (
            "tls handshake timeout",
            "timeout",
            "temporarily unavailable",
            "too many requests",
            "rate limit",
            "connection reset",
            "connection refused",
            "eof",
            " 429",
            " 500",
            " 502",
            " 503",
            " 504",
        )
    )


def cli(args: list[str], timeout: int = 60, retries: int = CLI_RETRIES) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
            output = proc.stdout.strip() or proc.stderr.strip()
            try:
                payload = json.loads(output[output.find("{"):])
            except Exception as exc:
                raise RuntimeError(f"Command did not return JSON: {' '.join(args)}\n{output}") from exc
            if proc.returncode != 0 or payload.get("ok") is False:
                message = f"Command failed: {' '.join(args)}\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
                if attempt < retries and is_transient_error(message):
                    print(f"  retry {attempt}/{retries}: {' '.join(args[:4])}", flush=True)
                    time.sleep(CLI_RETRY_DELAY * attempt)
                    continue
                raise RuntimeError(message)
            return payload
        except subprocess.TimeoutExpired as exc:
            last_error = exc
            if attempt < retries:
                print(f"  retry {attempt}/{retries}: command timed out: {' '.join(args[:4])}", flush=True)
                time.sleep(CLI_RETRY_DELAY * attempt)
                continue
            raise RuntimeError(f"Command timed out: {' '.join(args)}") from exc
        except RuntimeError as exc:
            last_error = exc
            if attempt < retries and is_transient_error(str(exc)):
                print(f"  retry {attempt}/{retries}: {' '.join(args[:4])}", flush=True)
                time.sleep(CLI_RETRY_DELAY * attempt)
                continue
            raise
    raise RuntimeError(f"Command failed after retries: {' '.join(args)}") from last_error


def deep_find(obj: Any, keys: set[str]) -> Any:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in keys and value:
                return value
        for value in obj.values():
            found = deep_find(value, keys)
            if found:
                return found
    if isinstance(obj, list):
        for item in obj:
            found = deep_find(item, keys)
            if found:
                return found
    return None


def deep_find_table_id(obj: Any) -> str | None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in {"table_id", "id"} and isinstance(value, str) and value.startswith("tbl"):
                return value
        for value in obj.values():
            found = deep_find_table_id(value)
            if found:
                return found
    if isinstance(obj, list):
        for item in obj:
            found = deep_find_table_id(item)
            if found:
                return found
    return None


def option_payload(names: list[str]) -> list[dict[str, str]]:
    payload = []
    for index, name in enumerate(names):
        hue, lightness = PALETTE[index % len(PALETTE)]
        payload.append({"name": name, "hue": hue, "lightness": lightness})
    return payload


def select_field(name: str, options: list[str], multiple: bool = False) -> dict[str, Any]:
    return {"name": name, "type": "select", "multiple": multiple, "options": option_payload(options)}


def field_defs() -> list[dict[str, Any]]:
    return [
        {"name": "标题", "type": "text"},
        {"name": "链接", "type": "text", "style": {"type": "url"}},
        select_field("主题", TOPICS),
        select_field("标签", TOPICS, multiple=True),
        select_field("价值等级", VALUE_LEVELS),
        select_field("状态", STATUSES),
        select_field("来源", SOURCES),
        select_field("类型", TYPES),
        {"name": "所有者", "type": "text"},
        {"name": "重要性", "type": "number"},
        {"name": "延伸阅读理由", "type": "text"},
        {"name": "原记录ID", "type": "text"},
    ]


def cell(value: Any) -> Any:
    return scalar_value(value)


def select_value(value: Any) -> str:
    return str(cell(value) or "").strip()


def as_float(value: Any) -> float | None:
    value = cell(value)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def related_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item["id"]) for item in value if isinstance(item, dict) and item.get("id")]


def fetch_source_records(limit: int = 200) -> list[dict[str, Any]]:
    offset = 0
    records: list[dict[str, Any]] = []
    fields: list[str] = []
    while True:
        payload = cli(
            [
                "lark-cli",
                "base",
                "+record-list",
                "--base-token",
                BASE_TOKEN,
                "--table-id",
                SOURCE_TABLE_ID,
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
    return records


def existing_record_mapping(table_id: str, limit: int = 200) -> dict[str, str]:
    """Return source record id -> rebuilt record id for a partially rebuilt table."""
    offset = 0
    mapping: dict[str, str] = {}
    fields: list[str] = []
    while True:
        payload = cli(
            [
                "lark-cli",
                "base",
                "+record-list",
                "--base-token",
                BASE_TOKEN,
                "--table-id",
                table_id,
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
            record = dict(zip(fields, row))
            old_id = select_value(record.get("原记录ID"))
            if old_id:
                mapping[old_id] = record_id
        if len(rows) < limit:
            break
        offset += limit
    return mapping


def infer_topic(fields: dict[str, Any]) -> str:
    for key in ("主题大类", "标签"):
        candidate = select_value(fields.get(key))
        if candidate in TOPICS and candidate != "未分类":
            return candidate
    title = clean_title(fields.get("标题", "")).lower()
    for topic, keywords in TOPIC_RULES:
        if any(keyword.lower() in title for keyword in keywords):
            return topic
    return "生活/其他" if select_value(fields.get("标签")) == "生活/其他" else "未分类"


def value_level(score: float | None) -> str:
    if score is None:
        return "待判断"
    if score >= HIGH_VALUE_SCORE:
        return "推荐阅读"
    if score >= MEDIUM_VALUE_SCORE:
        return "普通参考"
    return "存档"


def normalize_tags(fields: dict[str, Any], topic: str) -> list[str]:
    tags = []
    for key in ("标签", "主题大类"):
        value = select_value(fields.get(key))
        if value in TOPICS and value not in tags:
            tags.append(value)
    if topic not in tags:
        tags.insert(0, topic)
    return tags[:4]


def normalize_type(value: Any) -> str:
    text = select_value(value)
    return text or "docx"


def status_for(fields: dict[str, Any], topic: str, level: str) -> str:
    current = select_value(fields.get("状态"))
    if current in {"已归档", "活跃"}:
        return "已归档" if current == "已归档" else "已整理"
    if topic == "未分类" or level == "待判断" or not select_value(fields.get("链接")):
        return "待整理"
    return "已整理"


def source_row(record: dict[str, Any]) -> dict[str, Any]:
    fields = record["fields"]
    title = clean_title(fields.get("标题", ""))
    topic = infer_topic(fields)
    score = as_float(fields.get("重要性"))
    level = value_level(score)
    return {
        "标题": title,
        "链接": select_value(fields.get("链接")),
        "主题": topic,
        "标签": normalize_tags(fields, topic),
        "价值等级": level,
        "状态": status_for(fields, topic, level),
        "来源": select_value(fields.get("来源")) or "云盘",
        "类型": normalize_type(fields.get("类型")),
        "所有者": select_value(fields.get("所有者")),
        "重要性": score,
        "延伸阅读理由": "导入后根据同主题和标题关键词生成。",
        "原记录ID": record["record_id"],
    }


def tokenize(text: str) -> set[str]:
    lower = text.lower()
    ascii_tokens = set(re.findall(r"[a-z0-9]{2,}", lower))
    zh_parts = re.findall(r"[\u4e00-\u9fff]{2,}", lower)
    tokens = set(ascii_tokens)
    for part in zh_parts:
        tokens.add(part)
        if len(part) >= 4:
            tokens.update(part[i : i + 2] for i in range(len(part) - 1))
    stop = {"文档", "教程", "指南", "智能", "案例", "分享", "使用", "方法", "方案", "工具", "模板"}
    return {token for token in tokens if token not in stop}


def proposed_related(old_id: str, rows_by_old_id: dict[str, dict[str, Any]]) -> list[str]:
    row = rows_by_old_id[old_id]
    title_tokens = tokenize(row["标题"])
    scored: list[tuple[float, str]] = []
    for candidate_old_id, candidate in rows_by_old_id.items():
        if candidate_old_id == old_id:
            continue
        score = 0.0
        if candidate["主题"] == row["主题"] and row["主题"] not in {"未分类", "生活/其他"}:
            score += 4
        score += 1.5 * len(title_tokens & tokenize(candidate["标题"]))
        if candidate["所有者"] and candidate["所有者"] == row["所有者"]:
            score += 0.4
        score += min(candidate.get("重要性") or 0, 5) * 0.15
        if score >= 3.8:
            scored.append((score, candidate_old_id))
    scored.sort(reverse=True)
    return [old_id for _, old_id in scored[:MAX_RELATED]]


def temp_json(payload: Any) -> str:
    tmp_dir = Path(".tmp")
    tmp_dir.mkdir(exist_ok=True)
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", prefix="lark-docindex-v3-", dir=tmp_dir, delete=False, encoding="utf-8")
    with handle:
        json.dump(payload, handle, ensure_ascii=False)
        handle.write("\n")
    path = Path(handle.name)
    if path.is_absolute():
        return str(path.relative_to(Path.cwd()))
    return str(path)


def unique_name(base: str, existing: set[str]) -> str:
    if base not in existing:
        return base
    suffix = datetime.now().strftime("%Y%m%d_%H%M")
    return f"{base} {suffix}"


def list_tables() -> dict[str, str]:
    payload = cli(["lark-cli", "base", "+table-list", "--base-token", BASE_TOKEN, "--limit", "100"], timeout=60)
    return {item["name"]: item["id"] for item in payload["data"]["tables"]}


def table_record_count(table_id: str) -> int:
    payload = cli(
        [
            "lark-cli",
            "base",
            "+record-list",
            "--base-token",
            BASE_TOKEN,
            "--table-id",
            table_id,
            "--limit",
            "1",
            "--format",
            "json",
        ],
        timeout=60,
    )
    data = payload.get("data", {})
    if "total" in data:
        return int(data["total"])
    return 1 if data.get("data") else 0


def table_fields(table_id: str) -> set[str]:
    payload = cli(["lark-cli", "base", "+field-list", "--base-token", BASE_TOKEN, "--table-id", table_id], timeout=60)
    return {field["name"] for field in payload["data"]["fields"]}


def create_table(name: str, dry_run: bool = False) -> str:
    if dry_run:
        print(f"DRY RUN: create table {name}")
        return "dry_table_id"
    payload = cli(
        [
            "lark-cli",
            "base",
            "+table-create",
            "--base-token",
            BASE_TOKEN,
            "--name",
            name,
            "--fields",
            json.dumps([{"name": "标题", "type": "text"}], ensure_ascii=False),
            "--view",
            json.dumps({"name": "全部文档", "type": "grid"}, ensure_ascii=False),
        ],
        timeout=120,
    )
    table_id = deep_find_table_id(payload)
    if not table_id:
        raise RuntimeError(f"Cannot find table id in response: {json.dumps(payload, ensure_ascii=False)}")
    return str(table_id)


def create_fields(table_id: str, dry_run: bool = False) -> None:
    existing = set() if dry_run else table_fields(table_id)
    for field in field_defs()[1:]:
        if field["name"] in existing:
            continue
        if dry_run:
            print("DRY RUN: create field", json.dumps(field, ensure_ascii=False))
            continue
        cli(
            [
                "lark-cli",
                "base",
                "+field-create",
                "--base-token",
                BASE_TOKEN,
                "--table-id",
                table_id,
                "--json",
                json.dumps(field, ensure_ascii=False),
            ],
            timeout=60,
        )
        time.sleep(0.2)
    link_field = {"name": "相关文档", "type": "link", "link_table": table_id, "bidirectional": False}
    if "相关文档" in existing:
        return
    if dry_run:
        print("DRY RUN: create self link field", json.dumps(link_field, ensure_ascii=False))
        return
    cli(
        [
            "lark-cli",
            "base",
            "+field-create",
            "--base-token",
            BASE_TOKEN,
            "--table-id",
            table_id,
            "--json",
            json.dumps(link_field, ensure_ascii=False),
        ],
        timeout=60,
    )


def batch_create_records(table_id: str, rows: list[dict[str, Any]], dry_run: bool = False) -> dict[str, str]:
    fields = [field["name"] for field in field_defs()]
    old_to_new: dict[str, str] = {}
    for start in range(0, len(rows), 200):
        chunk = rows[start : start + 200]
        body = {"fields": fields, "rows": [[row.get(field) for field in fields] for row in chunk]}
        if dry_run:
            print(f"DRY RUN: batch create rows {start + 1}-{start + len(chunk)}")
            for row in chunk:
                old_to_new[row["原记录ID"]] = f"dry_{row['原记录ID']}"
            continue
        path = temp_json(body)
        try:
            payload = cli(
                [
                    "lark-cli",
                    "base",
                    "+record-batch-create",
                    "--base-token",
                    BASE_TOKEN,
                    "--table-id",
                    table_id,
                    "--json",
                    f"@{path}",
                ],
                timeout=180,
            )
            ids = payload["data"].get("record_id_list", [])
            if len(ids) != len(chunk):
                raise RuntimeError(f"Expected {len(chunk)} record ids, got {len(ids)}")
            for row, new_id in zip(chunk, ids):
                old_to_new[row["原记录ID"]] = new_id
        finally:
            Path(path).unlink(missing_ok=True)
        print(f"  已导入 {min(start + 200, len(rows))}/{len(rows)} 条")
        time.sleep(0.5)
    return old_to_new


def update_related(table_id: str, source_records: list[dict[str, Any]], rows_by_old_id: dict[str, dict[str, Any]], old_to_new: dict[str, str], dry_run: bool = False) -> int:
    updated = 0
    missing = [record["record_id"] for record in source_records if record["record_id"] not in old_to_new]
    if missing and not dry_run:
        raise RuntimeError(f"Missing rebuilt record ids for {len(missing)} source records, first={missing[0]}")
    for index, record in enumerate(source_records, start=1):
        old_id = record["record_id"]
        old_related = [rid for rid in related_ids(record["fields"].get("相关文档")) if rid in old_to_new]
        related_old_ids = old_related[:MAX_RELATED] or proposed_related(old_id, rows_by_old_id)
        related_new_ids = [old_to_new[rid] for rid in related_old_ids if rid in old_to_new]
        reason = "已按旧索引关系迁移为延伸阅读。" if old_related else "同主题或标题关键词相近，适合作为延伸阅读。"
        patch = {"延伸阅读理由": reason}
        if related_new_ids:
            patch["相关文档"] = [{"id": rid} for rid in related_new_ids]
        if dry_run:
            if index <= 5:
                print("DRY RUN: related patch", old_id, json.dumps(patch, ensure_ascii=False))
            updated += 1
            continue
        cli(
            [
                "lark-cli",
                "base",
                "+record-upsert",
                "--base-token",
                BASE_TOKEN,
                "--table-id",
                table_id,
                "--record-id",
                old_to_new[old_id],
                "--json",
                json.dumps(patch, ensure_ascii=False),
            ],
            timeout=60,
        )
        updated += 1
        if updated % 50 == 0:
            print(f"  已重建延伸阅读 {updated}/{len(source_records)} 条")
            time.sleep(0.8)
    return updated


def view_specs() -> list[dict[str, Any]]:
    return [
        {"name": "全部文档", "visible": ["标题", "主题", "价值等级", "相关文档", "链接", "来源", "类型", "所有者", "状态"], "sort": [{"field": "价值等级"}, {"field": "重要性", "desc": True}]},
        {"name": "推荐阅读", "visible": ["标题", "主题", "价值等级", "相关文档", "链接", "重要性"], "filter": {"logic": "and", "conditions": [["价值等级", "intersects", ["推荐阅读"]]]}, "sort": [{"field": "重要性", "desc": True}]},
        {"name": "主题导航", "visible": ["标题", "主题", "价值等级", "相关文档", "链接", "重要性"], "group": {"group_config": [{"field": "主题"}]}, "sort": [{"field": "重要性", "desc": True}]},
        {"name": "待整理", "visible": ["标题", "主题", "价值等级", "链接", "状态"], "filter": {"logic": "or", "conditions": [["状态", "intersects", ["待整理", "待复核"]], ["主题", "intersects", ["未分类"]]]}, "sort": [{"field": "重要性", "desc": True}]},
        {"name": "延伸阅读", "visible": ["标题", "主题", "相关文档", "延伸阅读理由", "链接", "价值等级"], "filter": {"logic": "and", "conditions": [["相关文档", "non_empty", None]]}, "group": {"group_config": [{"field": "主题"}]}},
    ]


OBSOLETE_VIEWS = {"最近更新"}


def create_views(table_id: str, dry_run: bool = False) -> None:
    existing = {}
    if not dry_run:
        payload = cli(["lark-cli", "base", "+view-list", "--base-token", BASE_TOKEN, "--table-id", table_id], timeout=60)
        existing = {view["name"]: view["id"] for view in payload["data"].get("views", [])}
    for spec in view_specs():
        view_id = existing.get(spec["name"])
        if not view_id:
            if dry_run:
                view_id = spec["name"]
                print(f"DRY RUN: create view {spec['name']}")
            else:
                payload = cli(
                    ["lark-cli", "base", "+view-create", "--base-token", BASE_TOKEN, "--table-id", table_id, "--json", json.dumps({"name": spec["name"], "type": "grid"}, ensure_ascii=False)],
                    timeout=60,
                )
                view_id = payload["data"]["views"][0]["id"]
        sort_value = {"sort_config": spec["sort"]} if spec.get("sort") else None
        for command, key, value in (
            ("+view-set-visible-fields", "visible_fields", {"visible_fields": spec["visible"]}),
            ("+view-set-filter", "filter", spec.get("filter")),
            ("+view-set-sort", "sort", sort_value),
            ("+view-set-group", "group", spec.get("group")),
        ):
            if not value:
                continue
            if dry_run:
                print(f"DRY RUN: {command} {spec['name']} {json.dumps(value, ensure_ascii=False)}")
                continue
            cli(["lark-cli", "base", command, "--base-token", BASE_TOKEN, "--table-id", table_id, "--view-id", view_id, "--json", json.dumps(value, ensure_ascii=False)], timeout=60)
            time.sleep(0.2)
        print(f"  view ready: {spec['name']}")
    if dry_run:
        print("DRY RUN: delete default Grid View if present")
    elif "Grid View" in existing:
        cli(
            [
                "lark-cli",
                "base",
                "+view-delete",
                "--base-token",
                BASE_TOKEN,
                "--table-id",
                table_id,
                "--view-id",
                existing["Grid View"],
                "--yes",
            ],
            timeout=60,
        )
    for name in OBSOLETE_VIEWS:
        view_id = existing.get(name)
        if dry_run:
            print(f"DRY RUN: delete obsolete view {name} if present")
        elif view_id:
            cli(
                [
                    "lark-cli",
                    "base",
                    "+view-delete",
                    "--base-token",
                    BASE_TOKEN,
                    "--table-id",
                    table_id,
                    "--view-id",
                    view_id,
                    "--yes",
                ],
                timeout=60,
            )


def dashboard_blocks(table_name: str) -> list[dict[str, Any]]:
    return [
        {"name": "总文档数", "type": "statistics", "data_config": {"table_name": table_name, "count_all": True}},
        {"name": "推荐阅读", "type": "statistics", "data_config": {"table_name": table_name, "count_all": True, "filter": {"conjunction": "and", "conditions": [{"field_name": "重要性", "operator": "isGreaterEqual", "value": HIGH_VALUE_SCORE}]}}},
        {"name": "主题分布", "type": "bar", "data_config": {"table_name": table_name, "count_all": True, "group_by": [{"field_name": "主题", "mode": "integrated", "sort": {"type": "value", "order": "desc"}}]}},
        {"name": "价值结构", "type": "column", "data_config": {"table_name": table_name, "count_all": True, "group_by": [{"field_name": "价值等级", "mode": "integrated", "sort": {"type": "value", "order": "desc"}}]}},
        {"name": "来源分布", "type": "bar", "data_config": {"table_name": table_name, "count_all": True, "group_by": [{"field_name": "来源", "mode": "integrated", "sort": {"type": "value", "order": "desc"}}]}},
    ]


def create_dashboard(table_name: str, dry_run: bool = False) -> str:
    dashboards = {}
    if not dry_run:
        payload = cli(["lark-cli", "base", "+dashboard-list", "--base-token", BASE_TOKEN, "--format", "json"], timeout=60)
        dashboards = {item["name"]: item["dashboard_id"] for item in payload["data"].get("items", [])}
    name = unique_name(DASHBOARD_NAME, set(dashboards))
    if dry_run:
        print(f"DRY RUN: create dashboard {name}")
        dashboard_id = "dry_dashboard_id"
    else:
        payload = cli(["lark-cli", "base", "+dashboard-create", "--base-token", BASE_TOKEN, "--name", name, "--theme-style", "simplistic"], timeout=60)
        dashboard_id = str(deep_find(payload, {"dashboard_id", "id"}))
    for block in dashboard_blocks(table_name):
        if dry_run:
            print("DRY RUN: create dashboard block", block["name"], json.dumps(block["data_config"], ensure_ascii=False))
            continue
        cli(
            [
                "lark-cli",
                "base",
                "+dashboard-block-create",
                "--base-token",
                BASE_TOKEN,
                "--dashboard-id",
                dashboard_id,
                "--name",
                block["name"],
                "--type",
                block["type"],
                "--data-config",
                json.dumps(block["data_config"], ensure_ascii=False),
            ],
            timeout=60,
        )
        time.sleep(1.0)
    if not dry_run:
        cli(["lark-cli", "base", "+dashboard-arrange", "--base-token", BASE_TOKEN, "--dashboard-id", dashboard_id], timeout=60)
    return dashboard_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="preview the rebuild without creating anything")
    parser.add_argument("--skip-dashboard", action="store_true", help="only rebuild the table and views")
    parser.add_argument("--target-table-id", help="configure an existing rebuilt table instead of creating/importing records")
    parser.add_argument("--target-table-name", default=TABLE_NAME, help="table name to use in dashboard configs with --target-table-id")
    parser.add_argument("--resume-table-id", help="resume a failed rebuild after records were imported")
    parser.add_argument("--resume-table-name", default=TABLE_NAME, help="table name to use in dashboard configs with --resume-table-id")
    return parser.parse_args()


def require_env() -> None:
    missing = []
    if not BASE_TOKEN:
        missing.append("BASE_TOKEN")
    if not SOURCE_TABLE_ID:
        missing.append("SOURCE_TABLE_ID or TABLE_ID")
    if missing:
        raise SystemExit(f"missing required environment variable(s): {', '.join(missing)}")


def main() -> int:
    args = parse_args()
    require_env()
    print("=== lark-docindex V3 rebuild ===")
    print(f"Base={BASE_TOKEN} SourceTable={SOURCE_TABLE_ID}")

    source_records = fetch_source_records()
    rows = [source_row(record) for record in source_records]
    rows_by_old_id = {row["原记录ID"]: row for row in rows}
    print(f"源记录数: {len(source_records)}")
    print("主题分布:", json.dumps(Counter(row["主题"] for row in rows).most_common(8), ensure_ascii=False))
    print("价值等级:", json.dumps(Counter(row["价值等级"] for row in rows), ensure_ascii=False))
    print("状态:", json.dumps(Counter(row["状态"] for row in rows), ensure_ascii=False))

    tables = list_tables()
    if args.resume_table_id:
        table_id = args.resume_table_id
        table_name = args.resume_table_name
        print(f"\n[1/5] 恢复已导入表: {table_name} ({table_id})")
    elif args.target_table_id:
        table_id = args.target_table_id
        table_name = args.target_table_name
        print(f"\n[1/5] 继续配置已重建表: {table_name} ({table_id})")
    else:
        table_name = TABLE_NAME if args.dry_run else unique_name(TABLE_NAME, set())
        print(f"\n[1/5] 创建新索引表: {table_name}")
    if args.resume_table_id or args.target_table_id:
        pass
    elif not args.dry_run and TABLE_NAME in tables:
        table_id = tables[TABLE_NAME]
        existing_count = table_record_count(table_id)
        if existing_count:
            table_name = unique_name(TABLE_NAME, set(tables))
            table_id = create_table(table_name, dry_run=False)
        else:
            print(f"复用已创建的空 V3 表: {table_id}")
    else:
        table_id = create_table(table_name, dry_run=args.dry_run)

    if args.resume_table_id:
        print("\n[2-3/5] 跳过建表、字段和导入")
        print("\n[4/5] 恢复延伸阅读关系")
        old_to_new = existing_record_mapping(table_id)
        if len(old_to_new) != len(source_records):
            print(f"警告: 已导入记录映射 {len(old_to_new)}/{len(source_records)} 条")
        update_related(table_id, source_records, rows_by_old_id, old_to_new, dry_run=args.dry_run)
    elif not args.target_table_id:
        print("\n[2/5] 创建字段")
        create_fields(table_id, dry_run=args.dry_run)

        print("\n[3/5] 导入记录")
        old_to_new = batch_create_records(table_id, rows, dry_run=args.dry_run)

        print("\n[4/5] 重建延伸阅读关系")
        update_related(table_id, source_records, rows_by_old_id, old_to_new, dry_run=args.dry_run)
    else:
        print("\n[2-4/5] 跳过建表、字段、导入和延伸阅读重建")

    print("\n[5/5] 创建索引视图")
    create_views(table_id, dry_run=args.dry_run)

    dashboard_id = None
    if not args.skip_dashboard:
        print("\n[extra] 创建 V3 仪表盘")
        dashboard_id = create_dashboard(table_name, dry_run=args.dry_run)

    print("\n完成")
    print(f"table_name={table_name}")
    print(f"table_id={table_id}")
    if dashboard_id:
        print(f"dashboard_id={dashboard_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
