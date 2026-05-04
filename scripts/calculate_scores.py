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
  python3 calculate_scores.py
"""

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# --- Config ---
BASE_TOKEN = "KgBBbaBGJaP1tvsjVd6cU79Rnmc"
TABLE_ID = "tblkB8prGR05ULlz"
SCORE_FIELD = "重要性"  # number field in Base

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
    if owner and "蒋激昂" in str(owner): return 5.0
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

def run_cli(cmd, input_data=None, timeout=30):
    """Run lark-cli command"""
    proc = subprocess.run(
        cmd, shell=True, input=input_data,
        capture_output=True, text=True, timeout=timeout
    )
    return proc.stdout


def get_field_value(val):
    """Extract string from possibly nested value"""
    if isinstance(val, list):
        return val[0] if val else ""
    return val or ""


# --- Main ---

def fetch_records():
    """Fetch all records from Base"""
    output = run_cli(
        f'lark-cli base +record-list --base-token "{BASE_TOKEN}" '
        f'--table-id "{TABLE_ID}" --limit 200 2>&1'
    )
    records = []
    for line in output.split("\n"):
        if line.startswith("|") and "_record_id" not in line and "---" not in line:
            parts = [p.strip() for p in line.split("|")]
            parts = [p for p in parts if p]  # remove empties
            if len(parts) >= 2:
                records.append(parts)
    return records


def update_score(record_id, score):
    """Update a single record's importance score"""
    data = json.dumps({"fields": {SCORE_FIELD: score}}, ensure_ascii=False)
    output = run_cli(
        f'lark-cli api PUT "/open-apis/bitable/v1/apps/{BASE_TOKEN}/'
        f'tables/{TABLE_ID}/records/{record_id}" --data \'{data}\' 2>&1'
    )
    try:
        resp = json.loads(output)
        return resp.get("code") == 0
    except Exception:
        return '"ok": true' in output


def main():
    print("=== 飞书云文档智能评分 ===\n")
    
    # Fetch records
    print("[1/3] 获取记录...")
    raw_records = fetch_records()
    print(f"  获取 {len(raw_records)} 条记录")
    
    # Load metadata for freshness calculation
    meta = {}
    try:
        with open("data/docs_all.json") as f:
            docs_all = json.load(f)
            meta = {d.get("url", ""): d for d in docs_all}
            print(f"  加载 {len(meta)} 条元数据")
    except Exception:
        print("  [WARN] 未找到元数据文件, 时效性按默认计算")
    
    # Calculate scores
    print("\n[2/3] 计算评分...")
    scored = []
    for parts in raw_records:
        if len(parts) < 2:
            continue
        record_id = parts[0]
        title = parts[1] if len(parts) > 1 else ""
        
        record = {
            "标题": title,
            "标签": parts[5] if len(parts) > 5 else "",
            "来源": parts[8] if len(parts) > 8 else "",
            "所有者": parts[12] if len(parts) > 12 else "",
        }
        url = parts[11] if len(parts) > 11 else ""
        m = meta.get(url, {})
        
        score = calculate_score(record, m)
        scored.append((record_id, title, score))
    
    # Distribution
    from collections import Counter
    dist = Counter(s[2] for s in scored)
    high = sum(1 for s in scored if s[2] >= 3.5)
    medium = sum(1 for s in scored if 2.5 <= s[2] < 3.5)
    low = sum(1 for s in scored if s[2] < 2.5)
    print(f"  高价值(>=3.5): {high} | 中等(2.5-3.4): {medium} | 低(<2.5): {low}")
    
    # Update Base
    print(f"\n[3/3] 回填 Base...")
    success = 0
    for record_id, title, score in scored:
        if update_score(record_id, score):
            success += 1
        else:
            print(f"  FAIL: {title[:30]} (score={score})")
    
    print(f"\n=== 完成: {success}/{len(scored)} 条评分已回填 ===")
    return 0 if success == len(scored) else 1


if __name__ == "__main__":
    sys.exit(main())
