#!/usr/bin/env python3
"""Shared helpers for lark-docindex data normalization."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag


VALID_TYPES = {"DOCX", "BITABLE"}
DEFAULT_STATUS = "待整理"
DEFAULT_SOURCE = "云盘"
DEFAULT_TAG = "生活/其他"

TAG_RULES = [
    (
        [
            "ai",
            "gpt",
            "claude",
            "llm",
            "openai",
            "sora",
            "midjourney",
            "seedance",
            "生图",
            "图像",
            "视频生成",
            "happyhorse",
        ],
        "AI/图像生成",
    ),
    (
        [
            "教程",
            "开源",
            "指南",
            "入门",
            "tutorial",
            "github",
            "git",
            "api",
            "部署",
            "安装",
            "配置",
            "docker",
            "python",
            "代码",
            "openclaw",
            "trae",
        ],
        "开源/教程",
    ),
    (["飞书", "lark", "feishu", "cli", "多维表格", "仪表盘"], "飞书CLI"),
    (["agent", "hermes", "产品", "pm", "用户", "需求", "mvp", "saas"], "Agent/产品"),
    (["比赛", "大赛", "活动", "训练营", "黑客松", "切磋", "创新"], "比赛/活动"),
    (["工作", "效率", "运营", "管理", "项目", "okr", "日报", "周报"], "工作/效率"),
    (["设计", "ui", "ux", "figma", "原型"], "产品/设计"),
    (["开发", "工程", "后端", "前端", "架构", "微服务", "数据库"], "开发/工程"),
]


def load_json(path: str | Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str | Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def clean_title(title: Any) -> str:
    text = html.unescape(str(scalar_value(title) or ""))
    text = re.sub(r"</?h>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().strip("\\").strip()


def scalar_value(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else ""
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return parsed[0] if parsed else ""
            except json.JSONDecodeError:
                pass
    return value


def normalize_type(value: Any, url: Any = "") -> str:
    text = str(scalar_value(value) or "").strip().lower()
    url_text = str(scalar_value(url) or "").lower()
    if text in {"bitable", "base", "app"} or "/base/" in url_text or "/app/" in url_text:
        return "BITABLE"
    return "DOCX"


def normalize_source(value: Any, url: Any = "") -> str:
    text = str(scalar_value(value) or "").strip()
    if text:
        if text.upper() in {"WIKI", "DOC"}:
            return text.title()
        return text
    return DEFAULT_SOURCE


def normalize_url(url: Any, keep_anchor: bool = True) -> str:
    text = str(scalar_value(url) or "").strip()
    if not text.startswith(("http://", "https://")):
        return text
    if keep_anchor:
        return text
    return urldefrag(text)[0]


def canonical_url(url: Any) -> str:
    return normalize_url(url, keep_anchor=False)


def classify_tag(title: Any, fallback: Any = "") -> str:
    fallback_text = str(fallback or "").strip()
    if fallback_text:
        return fallback_text
    lower_title = clean_title(title).lower()
    for keywords, tag in TAG_RULES:
        if any(keyword.lower() in lower_title for keyword in keywords):
            return tag
    return DEFAULT_TAG


def parse_datetime(value: Any) -> datetime:
    text = str(value or "")
    if not text:
        return datetime.min
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min


def normalize_record(record: dict[str, Any], keep_anchor: bool = True) -> dict[str, Any]:
    raw_url = record.get("url") or record.get("链接")
    raw_type = record.get("type") or record.get("类型")
    raw_source = record.get("source") or record.get("来源")
    raw_owner = record.get("owner") or record.get("所有者")
    if not str(scalar_value(raw_url) or "").startswith(("http://", "https://")) and str(
        scalar_value(raw_type) or ""
    ).startswith(("http://", "https://")):
        raw_url, raw_type, raw_source, raw_owner = raw_type, raw_owner, raw_url, ""

    title = clean_title(record.get("title") or record.get("标题"))
    url = normalize_url(raw_url, keep_anchor=keep_anchor)
    type_ = normalize_type(raw_type, url)
    tag = classify_tag(title, record.get("tag") or record.get("标签"))
    normalized = {
        "title": title,
        "status": str(record.get("status") or record.get("状态") or DEFAULT_STATUS),
        "tag": tag,
        "source": normalize_source(raw_source, url),
        "url": url,
        "type": type_,
        "owner": str(scalar_value(raw_owner) or ""),
    }
    for source_key, target_key in (("updated", "updated"), ("updated_at", "updated"), ("update_time", "updated")):
        if record.get(source_key):
            normalized[target_key] = record[source_key]
            break
    if record.get("created") or record.get("create_time"):
        normalized["created"] = record.get("created") or record.get("create_time")
    if record.get("id"):
        normalized["id"] = record["id"]
    return normalized


def normalize_records(
    records: list[dict[str, Any]],
    keep_anchor: bool = True,
    dedupe: bool = True,
    dedupe_canonical: bool = False,
) -> list[dict[str, Any]]:
    normalized = [normalize_record(record, keep_anchor=keep_anchor) for record in records]
    normalized = [record for record in normalized if record["title"] and record["url"].startswith(("http://", "https://"))]
    if not dedupe:
        return normalized

    by_url: dict[str, dict[str, Any]] = {}
    for record in sorted(normalized, key=lambda item: parse_datetime(item.get("updated")), reverse=True):
        key = canonical_url(record["url"]) if dedupe_canonical else record["url"]
        by_url.setdefault(key, record)
    return list(by_url.values())


def group_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_type = {type_: [] for type_ in sorted(VALID_TYPES)}
    by_tag: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_type.setdefault(record["type"], []).append(card_record(record))
        by_tag.setdefault(record["tag"], []).append(card_record(record))
    recent = sorted(records, key=lambda item: parse_datetime(item.get("updated")), reverse=True)
    return {
        "by_type": {key: value for key, value in by_type.items() if value},
        "by_tag": by_tag,
        "recent": [card_record(record, include_owner=True) for record in recent],
        "all": records,
    }


def card_record(record: dict[str, Any], include_owner: bool = True) -> dict[str, Any]:
    result = {"title": record["title"], "url": record["url"]}
    if include_owner:
        result["owner"] = record.get("owner", "")
    if record.get("updated"):
        result["updated"] = record["updated"]
    return result


def validate_grouped_data(data: dict[str, Any]) -> list[str]:
    records = data.get("all")
    if not isinstance(records, list):
        return ["missing or invalid top-level 'all' list"]
    return validate_records(records)


def validate_records(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for index, record in enumerate(records):
        prefix = f"record[{index}]"
        title = str(record.get("title") or "")
        url = str(record.get("url") or "")
        type_ = str(record.get("type") or "")
        tag = str(record.get("tag") or "")
        source = str(record.get("source") or "")
        if not title:
            errors.append(f"{prefix}: title is empty")
        if not url.startswith(("http://", "https://")):
            errors.append(f"{prefix}: url is not http(s): {url!r}")
        if type_ not in VALID_TYPES:
            errors.append(f"{prefix}: invalid type {type_!r}")
        if not tag:
            errors.append(f"{prefix}: tag is empty")
        if not source:
            errors.append(f"{prefix}: source is empty")
        key = url
        if key in seen:
            errors.append(f"{prefix}: duplicate url {key!r}")
        seen.add(key)
    return errors
