#!/usr/bin/env python3
"""
Phase 2: 智能评分系统
为飞书云文档计算重要性评分并回填到 Base

评分算法 v2 (5分制):
  - 35% 时效性 (freshness): 最近更新的文档分数更高
  - 20% 标签相关性 (tag relevance): AI/开发类标签加分
  - 15% 标题丰富度 (title richness): 标题越长信息越多
  - 15% 来源权重 (source bonus): 云盘个人文档加分
  - 15% 所有者权重 (owner bonus): 自己创建的文档加分

Usage:
  python3 calculate_scores.py --dry-run
  python3 calculate_scores.py --apply
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

from docindex_lib import canonical_url

# --- Config ---
BASE_TOKEN = os.environ.get("BASE_TOKEN", "")
TABLE_ID = os.environ.get("TABLE_ID", "")
SCORE_FIELD = "重要性"  # number field in Base
OWNER_BONUS_KEYWORD = os.environ.get("OWNER_BONUS_KEYWORD", "")
CLI_RETRIES = 3

CST = timezone(timedelta(hours=8))

# --- Scoring Functions ---

def calc_freshness(updated_str):
    """时效性评分 (0-5), 越新越高"""
    if not updated_str:
        return 2.0
    try:
        dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00")).astimezone(CST)
    except Exception:
        return 2.0
    days = (datetime.now(CST) - dt).days
    if days <= 3: return 5.0
    if days <= 7: return 4.5
    if days <= 14: return 4.0
    if days <= 30: return 3.5
    if days <= 60: return 3.0
    if days <= 90: return 2.5
    if days <= 180: return 2.0
    return 1.0


def calc_title_richness(title):
    """标题丰富度 (0-5)"""
    length = len(title or "")
    if length >= 25: return 5.0
    if length >= 15: return 4.0
    if length >= 8:  return 3.0
    return 1.5


def calc_tag_relevance(tag):
    """标签相关性 (0-5)"""
    if isinstance(tag, list):
        tag = tag[0] if tag else ""
    tag_map = {
        "AI/图像生成": 4.5, "开源/教程": 4.5, "开发/工程": 4.0,
        "飞书CLI": 4.0, "产品/设计": 3.5, "Agent/产品": 3.5,
        "比赛/活动": 3.0, "工作/效率": 3.0, "生活/其他": 2.0,
        "生活/记录": 2.0,
    }
    return tag_map.get(tag, 1.5)


def calc_source_bonus(source):
    """来源权重 (0-5)"""
    if isinstance(source, list):
        source = source[0] if source else ""
    source_str = str(source)
    if "云盘" in source_str: return 4.5
    if "Wiki" in source_str: return 3.0
    return 2.0


def calc_owner_bonus(owner):
    """所有者权重 (0-5)"""
    if isinstance(owner, list):
        owner = owner[0] if owner else ""
    if OWNER_BONUS_KEYWORD and owner and OWNER_BONUS_KEYWORD in str(owner): return 5.0
    if owner: return 3.0
    return 2.0


def calculate_score(record, meta=None):
    """
    计算综合评分 (1.0-5.0)
    
    Weights:
      freshness: 35%
      tag:       20%
      title:     15%
      source:    15%
      owner:     15%
    """
    updated = (meta or {}).get("updated", "")
    
    score = (
        0.35 * calc_freshness(updated) +
        0.20 * calc_tag_relevance(record.get("标签")) +
        0.15 * calc_title_richness(record.get("标题", "")) +
        0.15 * calc_source_bonus(record.get("来源")) +
        0.15 * calc_owner_bonus(record.get("所有者"))
    )
    
    return round(min(max(score, 1.0), 5.0), 1)


# --- Helpers ---

def is_transient_error(text):
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
            " 429",
            " 500",
            " 502",
            " 503",
            " 504",
        )
    )


def cli_json(cmd, timeout=60, retries=CLI_RETRIES):
    """Run lark-cli and return parsed JSON with useful errors."""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            output = proc.stdout.strip() or proc.stderr.strip()
            try:
                payload = json.loads(output[output.find("{"):])
            except Exception as exc:
                raise RuntimeError(f"Command did not return JSON: {' '.join(cmd)}\n{output}") from exc
            if proc.returncode != 0 or payload.get("ok") is False:
                message = f"Command failed: {' '.join(cmd)}\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
                if attempt < retries and is_transient_error(message):
                    print(f"  retry {attempt}/{retries}: {' '.join(cmd[:4])}", flush=True)
                    time.sleep(2 * attempt)
                    continue
                raise RuntimeError(message)
            return payload
        except subprocess.TimeoutExpired as exc:
            last_error = exc
            if attempt < retries:
                print(f"  retry {attempt}/{retries}: command timed out: {' '.join(cmd[:4])}", flush=True)
                time.sleep(2 * attempt)
                continue
            raise RuntimeError(f"Command timed out: {' '.join(cmd)}") from exc
        except RuntimeError as exc:
            last_error = exc
            if attempt < retries and is_transient_error(str(exc)):
                print(f"  retry {attempt}/{retries}: {' '.join(cmd[:4])}", flush=True)
                time.sleep(2 * attempt)
                continue
            raise
    raise RuntimeError(f"Command failed after retries: {' '.join(cmd)}") from last_error


def get_field_value(val):
    """Extract string from possibly nested value"""
    if isinstance(val, list):
        return get_field_value(val[0]) if val else ""
    if isinstance(val, dict):
        for key in ("text", "link", "url", "name", "value"):
            if key in val:
                return get_field_value(val[key])
        return json.dumps(val, ensure_ascii=False)
    return val or ""


def record_list_items(payload):
    """Convert lark-cli +record-list JSON output into record objects."""
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    fields = data.get("fields")
    rows = data.get("data")
    ids = data.get("record_id_list")
    if isinstance(fields, list) and isinstance(rows, list) and isinstance(ids, list):
        return [{"record_id": record_id, "fields": dict(zip(fields, row))} for record_id, row in zip(ids, rows)]
    return find_record_items(payload)


def find_record_items(payload):
    """Find the first list that looks like Base records in a CLI JSON payload."""
    if isinstance(payload, list):
        if payload and all(isinstance(item, dict) for item in payload):
            if any("fields" in item or "record_id" in item or "_record_id" in item for item in payload):
                return payload
        return []
    if not isinstance(payload, dict):
        return []
    for key in ("items", "records"):
        items = payload.get(key)
        if isinstance(items, list):
            return items
    for value in payload.values():
        items = find_record_items(value)
        if items:
            return items
    return []


# --- Main ---

def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-token", default=BASE_TOKEN)
    parser.add_argument("--table-id", default=TABLE_ID)
    parser.add_argument("--score-field", default=SCORE_FIELD)
    parser.add_argument("--metadata", default="data/docs_all.json")
    parser.add_argument("--dry-run", action="store_true", help="calculate and print distribution without writing Base")
    parser.add_argument("--apply", action="store_true", help="write scores back to Base")
    return parser.parse_args()


def require_config(args):
    missing = []
    if not args.base_token:
        missing.append("--base-token or BASE_TOKEN")
    if not args.table_id:
        missing.append("--table-id or TABLE_ID")
    if missing:
        raise SystemExit(f"missing required option(s): {', '.join(missing)}")


def fetch_records(base_token, table_id, limit=200):
    """Fetch all records from Base"""
    offset = 0
    records = []
    while True:
        payload = cli_json(
            [
                "lark-cli",
                "base",
                "+record-list",
                "--base-token",
                base_token,
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
        items = record_list_items(payload)
        records.extend(items)
        if len(items) < limit:
            break
        offset += limit
    return records


def update_score(base_token, table_id, score_field, record_id, score):
    """Update a single record's importance score"""
    cli_json(
        [
            "lark-cli",
            "base",
            "+record-upsert",
            "--base-token",
            base_token,
            "--table-id",
            table_id,
            "--record-id",
            record_id,
            "--json",
            json.dumps({score_field: score}, ensure_ascii=False),
        ],
        timeout=60,
    )


def main():
    args = parse_args()
    require_config(args)
    if args.dry_run and args.apply:
        raise SystemExit("--dry-run and --apply cannot be used together")
    write_scores = args.apply and not args.dry_run
    print("=== 飞书云文档智能评分 ===\n")
    
    # Fetch records
    print("[1/3] 获取记录...")
    raw_records = fetch_records(args.base_token, args.table_id)
    print(f"  获取 {len(raw_records)} 条记录")
    
    # Load metadata for freshness calculation
    meta = {}
    try:
        with open(args.metadata, encoding="utf-8") as f:
            docs_all = json.load(f)
            for d in docs_all:
                url = d.get("url", "")
                if url:
                    meta[url] = d
                    meta[canonical_url(url)] = d
            print(f"  加载 {len(meta)} 条元数据")
    except Exception:
        print("  [WARN] 未找到元数据文件, 时效性按默认计算")
    
    # Calculate scores
    print("\n[2/3] 计算评分...")
    scored = []
    for item in raw_records:
        if not isinstance(item, dict):
            continue
        fields = item.get("fields", item)
        record_id = item.get("record_id") or item.get("_record_id") or item.get("id")
        if not record_id or not isinstance(fields, dict):
            continue
        title = get_field_value(fields.get("标题"))
        
        record = {
            "标题": title,
            "标签": get_field_value(fields.get("标签")),
            "来源": get_field_value(fields.get("来源")),
            "所有者": get_field_value(fields.get("所有者")),
        }
        url = get_field_value(fields.get("链接"))
        m = meta.get(url) or meta.get(canonical_url(url)) or {}
        
        score = calculate_score(record, m)
        scored.append((record_id, title, score))
    
    # Distribution
    high = sum(1 for s in scored if s[2] >= 3.5)
    medium = sum(1 for s in scored if 2.5 <= s[2] < 3.5)
    low = sum(1 for s in scored if s[2] < 2.5)
    print(f"  高价值(>=3.5): {high} | 中等(2.5-3.4): {medium} | 低(<2.5): {low}")

    if not write_scores:
        print("\n[3/3] dry-run: 未回填 Base；使用 --apply 才会写入")
        for record_id, title, score in scored[:10]:
            print(f"  {record_id} {score}: {title[:40]}")
        return 0

    # Update Base
    print(f"\n[3/3] 回填 Base...")
    success = 0
    for record_id, title, score in scored:
        try:
            update_score(args.base_token, args.table_id, args.score_field, record_id, score)
            success += 1
        except Exception as exc:
            print(f"  FAIL: {title[:30]} (score={score}) {exc}")
    
    print(f"\n=== 完成: {success}/{len(scored)} 条评分已回填 ===")
    return 0 if success == len(scored) else 1


if __name__ == "__main__":
    sys.exit(main())
