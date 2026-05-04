#!/bin/bash
# scan_docs.sh -- 扫描飞书云盘文档，导出元数据 JSON
# 用法: bash scan_docs.sh [关键词] [输出文件]

QUERY="${1:-}"
OUTPUT="${2:-data/docs_scanned.json}"
PAGE_SIZE=50

echo "扫描飞书云盘文档 (query='${QUERY}')..."

lark-cli drive +search \
  --query "${QUERY}" \
  --sort edit_time \
  --page-size ${PAGE_SIZE} \
  > /tmp/scan_raw.json 2>&1

# 提取 results 并清理 HTML 高亮标签
python3 -c "
import json, re, sys
with open('/tmp/scan_raw.json') as f:
    raw = f.read()
data = json.loads(raw[raw.find('{'):])
results = data.get('data',{}).get('results',[])
cleaned = []
for r in results:
    title = re.sub(r'</?[^>]+>', '', r.get('title',''))
    cleaned.append({
        'title': title,
        'token': r.get('token',''),
        'type': r.get('type',''),
        'url': r.get('url',''),
        'owner': r.get('owner',{}).get('name','') if isinstance(r.get('owner'), dict) else str(r.get('owner','')),
        'updated_at': r.get('last_modified_time','')
    })
with open('${OUTPUT}', 'w') as f:
    json.dump(cleaned, f, ensure_ascii=False, indent=2)
print(f'扫描到 {len(cleaned)} 篇文档，已保存到 ${OUTPUT}')
"
