#!/usr/bin/env python3
"""Update Wiki index cards from normalized local document data.

用法:
  python3 update_cards.py [--data data/final_data.json] [--dry-run]

功能:
  1. 读取本地记录快照
  2. 按类型/主题分组
  3. 重写全部 Wiki 索引卡片（含格式化内容）
  4. 更新最近更新卡片
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from docindex_lib import group_records, load_json, normalize_records, validate_records
from normalize_data import extract_records

def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/final_data.json", help="record list or grouped data JSON")
    parser.add_argument("--cards-map", help="JSON file mapping card names to Feishu doc obj_token")
    parser.add_argument("--dry-run", action="store_true", help="render and validate without writing Feishu docs")
    parser.add_argument("--strip-anchor", action="store_true", help="remove URL fragments before grouping")
    parser.add_argument("--dedupe-canonical", action="store_true", help="dedupe URLs after removing fragments")
    parser.add_argument("--recent-limit", type=int, default=20)
    return parser.parse_args()


def load_cards_map(path: str | None, grouped: dict[str, object], dry_run: bool) -> dict[str, str]:
    if path:
        payload = load_json(path)
    else:
        payload = {}
    if not isinstance(payload, dict):
        raise SystemExit("--cards-map must be a JSON object")
    if payload:
        return {str(key): str(value) for key, value in payload.items()}
    if not dry_run:
        raise SystemExit("missing --cards-map for non-dry-run card updates")
    keys = list(grouped.get("by_type", {}).keys()) + list(grouped.get("by_tag", {}).keys()) + ["最近更新"]
    return {key: f"dry_{key}" for key in dict.fromkeys(keys)}


def update_doc(obj_token, markdown):
    """Write markdown content to a Feishu doc via stdin pipe."""
    r = subprocess.run(
        ["lark-cli", "docs", "+update", "--doc", obj_token, "--mode", "overwrite", "--markdown", "-"],
        input=markdown,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return '"ok": true' in (r.stdout + r.stderr)


def render_card(title, docs, subtitle=""):
    md = f"# {title}\n\n"
    if subtitle:
        md += f"{subtitle}\n\n"
    md += f"共 **{len(docs)}** 篇文档。\n\n---\n\n"
    for d in docs:
        owner = f" - {d.get('owner')}" if d.get("owner") else ""
        updated = f" - {d.get('updated')}" if d.get("updated") else ""
        md += f"- [{d.get('title', '')}]({d.get('url', '')}){owner}{updated}\n"
    md += "\n---\n\n> 点击标题跳转原始文档。\n"
    return md


def main():
    args = parse_args()
    print(f"读取记录: {args.data}")
    data = load_json(args.data)
    raw_records = extract_records(data)
    records = normalize_records(
        raw_records,
        keep_anchor=not args.strip_anchor,
        dedupe=True,
        dedupe_canonical=args.dedupe_canonical,
    )
    errors = validate_records(records)
    if errors:
        print(f"错误: 数据校验失败 ({len(errors)} errors)")
        for error in errors[:30]:
            print(f"  - {error}")
        sys.exit(1)

    grouped = group_records(records)
    by_type = grouped["by_type"]
    by_tag = grouped["by_tag"]
    recent = grouped["recent"][: args.recent_limit]
    cards = load_cards_map(args.cards_map, grouped, args.dry_run)

    print(f"共 {len(records)} 条有效记录 (原始 {len(raw_records)} 条)")

    # 生成各卡片
    for card_key, obj_token in cards.items():
        if card_key in by_type:
            docs = by_type[card_key]
            icon = "📄" if card_key == "DOCX" else "📊"
            md = render_card(f"{icon} {card_key} 类索引", docs)
        elif card_key in by_tag:
            docs = by_tag[card_key]
            md = render_card(card_key, docs)
        elif card_key == "最近更新":
            docs = recent
            md = render_card("最近更新", docs, subtitle=f"按更新时间排序，展示前 {len(docs)} 条。")
        else:
            continue

        ok = True if args.dry_run else update_doc(obj_token, md)
        print(f"  卡片 '{card_key}' ({len(docs)}): {'OK' if ok else 'FAIL'}")

    print("\n全部卡片处理完成!")

if __name__ == "__main__":
    main()
