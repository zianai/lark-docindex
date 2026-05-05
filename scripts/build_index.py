#!/usr/bin/env python3
"""
build_index.py -- 基于 lark-cli 构建 Base 索引 + Wiki 卡片

用法:
  python3 build_index.py --docs data/docs_all.json

前置条件:
  - lark-cli 已安装并认证 (lark-cli auth status)
  - docs JSON 文件存在

功能:
  1. 创建 Base（如不存在）
  2. 创建字段（标题/类型/来源/标签/链接/所有者/状态）
  3. 批量导入文档记录
  4. 创建 Wiki 空间 + 根页面
  5. 创建分类目录（按类型/按主题/最近更新）
  6. 生成索引卡片
"""

import subprocess, json, sys, os, re
from collections import Counter, defaultdict

BASE_TOKEN = os.environ.get("BASE_TOKEN", "")
TABLE_ID = os.environ.get("TABLE_ID", "")
SPACE_ID = os.environ.get("SPACE_ID", "")

def cli(cmd):
    """Execute lark-cli command and return parsed JSON."""
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        print(f"  [WARN] Command failed: {' '.join(cmd[:4])}...")
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None

def api(method, path, data=None):
    """Call lark-cli api directly."""
    cmd = ["lark-cli", "api", method, path]
    if data is not None:
        cmd.extend(["--data", json.dumps(data, ensure_ascii=False)])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None

def main():
    docs_file = "data/docs_all.json"
    if len(sys.argv) > 2 and sys.argv[1] == "--docs":
        docs_file = sys.argv[2]

    with open(docs_file, encoding="utf-8") as f:
        docs = json.load(f)

    print(f"加载 {len(docs)} 篇文档")

    # Step 1: 创建或使用已有 Base
    if not BASE_TOKEN:
        print("\n[1] 创建 Base...")
        r = cli(["lark-cli", "base", "+base-create", "--name", "文档导航中心"])
        # parse base_token from output
        print(f"  请设置 BASE_TOKEN 环境变量")
        return
    else:
        print(f"\n[1] 使用已有 Base: {BASE_TOKEN}")
        if not TABLE_ID:
            print("  错误: 请同时设置 TABLE_ID 环境变量")
            return

    # Step 2: 导入记录
    print(f"\n[2] 导入 {len(docs)} 条记录到 Base...")
    success = 0
    for doc in docs:
        fields = {
            "标题": doc["title"],
            "链接": doc["url"],
            "类型": "BITABLE" if doc.get("type") == "bitable" else "DOCX",
            "来源": "云盘",
            "所有者": doc.get("owner", ""),
            "标签": auto_tag(doc["title"]),
            "状态": "待整理"
        }
        r = api("POST", f"/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{TABLE_ID}/records", {"fields": fields})
        if r and r.get("code") == 0:
            success += 1
    print(f"  导入成功: {success}/{len(docs)}")

    print("\n完成! 后续步骤:")
    print("  1. 运行 update_cards.py 更新 Wiki 索引卡片")
    print("  2. 在飞书中打开 Base 查看仪表盘")

def auto_tag(title):
    t = title.lower()
    if any(k in t for k in ["ai","gpt","image","图像","生成","seedance"]):
        return "AI/图像生成"
    if any(k in t for k in ["开源","openclaw","trae","教程","训练","git","claude code"]):
        return "开源/教程"
    if any(k in t for k in ["飞书","cli","lark","feishu"]):
        return "飞书CLI"
    if any(k in t for k in ["比赛","大赛","活动","创新","训练营","切磋"]):
        return "比赛/活动"
    if any(k in t for k in ["agent","hermes","产品"]):
        return "Agent/产品"
    return "生活/其他"

if __name__ == "__main__":
    main()
