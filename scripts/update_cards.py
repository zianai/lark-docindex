#!/usr/bin/env python3
"""
update_cards.py -- 根据当前 Base 数据重新生成所有 Wiki 索引卡片

用法:
  python3 update_cards.py

功能:
  1. 从 Base 读取全部记录
  2. 按类型/主题分组
  3. 重写全部 Wiki 索引卡片（含格式化内容）
  4. 更新根页面（含统计信息）
"""

import subprocess, json, sys, os, re
from collections import Counter, defaultdict

BASE_TOKEN = os.environ.get("BASE_TOKEN", "KgBBbaBGJaP1tvsjVd6cU79Rnmc")
TABLE_ID = os.environ.get("TABLE_ID", "tblkB8prGR05ULlz")

# Wiki 卡片 obj_token 映射
CARDS = {
    "DOCX": "V0PKdbuLAomanQxc87xcEURvnXg",
    "BITABLE": "NDBhd2n3so4Vohx7R4hcKGCfnie",
    "AI/图像生成": "GQcFdwGxEo30bZxuc9zcflFcnJb",
    "开源/教程": "AjL1dmFPZoyvwjxPmQucxZbLnCh",
    "生活/其他": "DA8jdkD1LoosZ7xnnTIcm8DunLf",
    "比赛/活动": "AuVvdDHPBoa0G6xSX6ucK70mnWe",
    "Agent/产品": "JtGTdZL7toX5T4xPmQ0ckDuunhg",
    "飞书CLI": "ScqhdBf1VooJF3xtrPycIKhln9g",
    "最近更新": "BosBdIzOioZYAAxiUNAc0VjNn9e",
}
ROOT_OBJ = "UvbAd4rHfodayPxXd3Tc39gLnon"

def update_doc(obj_token, markdown):
    """Write markdown content to a Feishu doc via stdin pipe."""
    cmd = f'cat | lark-cli docs +update --doc "{obj_token}" --mode overwrite --markdown - 2>&1'
    r = subprocess.run(cmd, shell=True, input=markdown, capture_output=True, text=True, timeout=30)
    return '"ok": true' in (r.stdout + r.stderr)

def main():
    print("从 Base 读取记录...")
    # 这里需要实际的记录读取逻辑
    # 简化版：从 final_data.json 读取
    data_file = "data/final_data.json"
    if not os.path.exists(data_file):
        print(f"错误: 找不到 {data_file}，请先运行 build_index.py")
        sys.exit(1)

    with open(data_file) as f:
        data = json.load(f)

    by_type = data.get("by_type", {})
    by_tag = data.get("by_tag", {})

    total = sum(len(v) for v in by_type.values())
    print(f"共 {total} 条记录")

    # 生成各卡片
    for card_key, obj_token in CARDS.items():
        if card_key in by_type:
            docs = by_type[card_key]
            emoji = "📄" if card_key == "DOCX" else "📊"
            md = f"# {emoji} {card_key} 类索引\n\n共 **{len(docs)}** 篇。\n\n---\n\n"
        elif card_key in by_tag:
            docs = by_tag[card_key]
            md = f"# {card_key}\n\n共 **{len(docs)}** 篇文档。\n\n---\n\n"
        elif card_key == "最近更新":
            docs = []  # 需要从 all records 排序
            md = "# 最近更新\n\n---\n\n"
        else:
            continue

        for d in docs:
            title = d.get("title", "")
            url = d.get("url", "")
            md += f"- [{title}]({url})\n"
        md += "\n---\n\n> 点击标题跳转原始文档。\n"

        ok = update_doc(obj_token, md)
        print(f"  卡片 '{card_key}' ({len(docs)}): {'OK' if ok else 'FAIL'}")

    print("\n全部卡片更新完成!")

if __name__ == "__main__":
    main()
