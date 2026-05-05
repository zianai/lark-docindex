#!/usr/bin/env python3
"""Batch import documents from a local JSON snapshot to Feishu Base."""
import argparse
import json
import os
import re
import subprocess

BASE = os.environ.get("BASE_TOKEN", "")
TABLE = os.environ.get("TABLE_ID", "")
OWNER_BONUS_KEYWORD = os.environ.get("OWNER_BONUS_KEYWORD", "")

TAG_RULES = [
    (["AI","GPT","Claude","LLM","Agent","OpenAI","Sora","Midjourney","Seedance","生图","图像","视频生成","AI切磋","HappyHorse"], "AI/图像生成"),
    (["教程","开源","指南","入门","Tutorial","GitHub","Git","CLI","API","部署","安装","配置","Docker","Python","代码"], "开源/教程"),
    (["Agent","产品","PM","用户","需求","MVP","SaaS"], "Agent/产品"),
    (["飞书","lark","多维表格","仪表盘"], "飞书CLI"),
    (["比赛","大赛","活动","训练营","黑客松"], "比赛/活动"),
    (["工作","效率","运营","管理","项目","OKR","日报","周报"], "工作/效率"),
    (["设计","UI","UX","Figma","原型"], "产品/设计"),
    (["开发","工程","后端","前端","架构","微服务","数据库"], "开发/工程"),
]

def classify_tag(title):
    tl = title.lower()
    for keywords, tag in TAG_RULES:
        for kw in keywords:
            if kw.lower() in tl:
                return tag
    return "生活/其他"

def classify_source(url):
    if "my.feishu.cn" in url:
        return "云盘"
    if "wiki" in url:
        return "Wiki"
    return "云盘"

def quick_score(d):
    from datetime import datetime, timezone, timedelta
    CST = timezone(timedelta(hours=8))
    tag_map = {"AI/图像生成":3.0,"开源/教程":2.8,"开发/工程":2.7,"飞书CLI":3.2,"Agent/产品":2.5,"产品/设计":2.5,"比赛/活动":2.3,"工作/效率":2.2,"生活/其他":1.5}
    base = tag_map.get(d.get("tag","生活/其他"), 1.5)
    if OWNER_BONUS_KEYWORD and OWNER_BONUS_KEYWORD in d.get("owner",""):
        base += 0.5
    updated = d.get("updated","")
    if updated:
        try:
            dt = datetime.fromisoformat(updated)
            days = (datetime.now(CST) - dt).days
            if days <= 7: base += 0.8
            elif days <= 30: base += 0.4
            elif days <= 90: base += 0.2
        except:
            pass
    return round(min(max(base, 1.0), 5.0), 1)

def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", default="data/full_scan_docs.json")
    parser.add_argument("--base-token", default=BASE)
    parser.add_argument("--table-id", default=TABLE)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def require_config(args):
    missing = []
    if not args.base_token:
        missing.append("--base-token or BASE_TOKEN")
    if not args.table_id:
        missing.append("--table-id or TABLE_ID")
    if missing:
        raise SystemExit(f"missing required option(s): {', '.join(missing)}")


def main():
    args = parse_args()
    require_config(args)

    print("获取已有记录...", flush=True)
    proc = subprocess.run(
        ["lark-cli", "base", "+record-list", "--base-token", args.base_token, "--table-id", args.table_id, "--limit", "500", "--format", "json"],
        capture_output=True, text=True, timeout=60
    )
    existing_urls = set(re.findall(r'(https?://[^\s",\]\)]+feishu\.[^\s",\]\)]+)', proc.stdout))
    existing_urls.update(set(re.findall(r'(https?://[^\s",\]\)]+larkoffice\.[^\s",\]\)]+)', proc.stdout)))
    print(f"已有 {len(existing_urls)} 条URL", flush=True)

    with open(args.input, encoding="utf-8") as f:
        all_docs = json.load(f)

    new_docs = [d for d in all_docs if d["url"] not in existing_urls]
    print(f"待导入 {len(new_docs)} 条", flush=True)

    success = 0
    fail = 0
    for i, d in enumerate(new_docs):
        tag = classify_tag(d.get("title",""))
        source = classify_source(d["url"])
        d["tag"] = tag
        d["source"] = source
        score = quick_score(d)

        fields = {
            "标题": d.get("title","")[:200],
            "类型": d.get("type","DOCX"),
            "来源": source,
            "所有者": d.get("owner","")[:50],
            "链接": d["url"],
            "标签": tag,
            "状态": "待整理",
            "重要性": score,
        }
        data = json.dumps({"fields": fields}, ensure_ascii=False)

        if args.dry_run:
            success += 1
        else:
            try:
                proc = subprocess.run(
                    ["lark-cli", "api", "POST", f"/open-apis/bitable/v1/apps/{args.base_token}/tables/{args.table_id}/records", "--data", data],
                    capture_output=True, text=True, timeout=10
                )
                resp = json.loads(proc.stdout)
                if resp.get("code") == 0:
                    success += 1
                else:
                    fail += 1
                    if fail <= 3:
                        print(f"FAIL [{i}]: {d.get('title','?')[:30]} -> {proc.stdout[:80]}", flush=True)
            except Exception:
                fail += 1

        if (i + 1) % 50 == 0:
            print(f"进度: {i+1}/{len(new_docs)} ok={success} fail={fail}", flush=True)

    print(f"\n完成: {success} 成功, {fail} 失败 (共 {len(new_docs)} 条)", flush=True)


if __name__ == "__main__":
    main()
