---
name: feishu-cli-development
description: Develop skills and workflows for Feishu/Lark CLI. Handle authentication, scope limitations, cross-domain data aggregation, and workaround strategies for personal accounts.
version: 1.1.0
author: Hermes Agent
metadata:
  hermes:
    tags: [feishu, lark, cli, workflow, automation]
    related_skills: [competition-sprint-planning]
---

# Feishu/Lark CLI Development

## Overview

Develop custom skills and workflows for the Feishu/Lark CLI (`lark-cli`). This skill covers authentication handling, scope limitations (especially for personal accounts), cross-domain data aggregation patterns, and practical workarounds.

## Key Challenges & Solutions

### Challenge 1: Personal Account Scope Limitations

**Problem**: Personal Feishu accounts cannot obtain certain scopes like `search:docs:read` which require enterprise/developer permissions. The device authorization flow may show "请求不合法" (request invalid) for these scopes.

**Error symptoms**:
```json
{
  "ok": false,
  "error": {
    "type": "missing_scope",
    "message": "missing required scope(s): search:docs:read"
  }
}
```

Or during auth: "flow id请求不合法" - the scope requires enterprise/developer account.

**Solution**: Use alternative commands that don't require restricted scopes.

| Restricted Command | Alternative | Notes |
|-------------------|-------------|-------|
| `docs +search` | `wiki spaces list` + `wiki nodes list` | Get documents via Wiki API |
| `drive files list` | N/A (requires `space:document:retrieve`) | Use wiki approach instead |
| `im +chat-create` | Use existing groups | Search with `im +chat-search` |

**How to identify scope issues**:
1. Run `lark-cli auth status` to see current scopes
2. If `--scope "xxx"` fails with "请求不合法", it's enterprise-only
3. Try `--domain xxx` instead - it grants available scopes for that domain
4. Document workarounds in your skill for personal account users

**Wiki workflow**:
```bash
# Step 1: List available wiki spaces
lark-cli wiki spaces list

# Step 2: Get nodes in a specific space
lark-cli wiki nodes list --params '{"space_id":"YOUR_SPACE_ID"}'

# Step 3: Fetch document content
lark-cli docs +fetch --token "DOC_TOKEN_FROM_NODE"
```

### Challenge 2: Command Syntax Variations

**Issue**: Different commands use different flag patterns.

**Examples**:
```bash
# Task uses --page-limit
lark-cli task +get-my-tasks --page-limit 20

# IM search uses different pattern
lark-cli im +chat-search --query "关键词"

# Wiki requires JSON params
lark-cli wiki nodes list --params '{"space_id":"xxx"}'

# Base requires --base-token + --dsl
lark-cli base +data-query --base-token "xxx" --dsl '{"query":"xxx"}'
```

**Best practice**: Always check `--help` for each command:
```bash
lark-cli <domain> <command> --help
```

## Cross-Domain Workflow Pattern

### Authentication

```bash
# Login to multiple domains at once
lark-cli auth login --domain task,base,im

# For docs/wiki, they share the same auth
lark-cli auth login --domain docs

# Check current scopes
lark-cli auth status
```

### Data Aggregation Workflow

```yaml
workflow: project-sync
steps:
  1_task:
    command: lark-cli task +get-my-tasks --page-limit 50
    filter: by project name or custom field
    
  2_base:
    command: lark-cli base +data-query --base-token "xxx" --dsl "{}"
    requires: base-token from app
    
  3_doc:
    # Personal account workaround
    command_1: lark-cli wiki spaces list
    command_2: lark-cli wiki nodes list --params '{"space_id":"xxx"}'
    filter: by title or update time
    
  4_im:
    command: lark-cli im +messages-send --chat-id "xxx" --content "message"
```

## Common Commands Reference

### Task Domain
```bash
# Get my tasks (note: --limit doesn't work, use --page-limit)
lark-cli task +get-my-tasks --page-limit 20

# Create a task
lark-cli task +create --summary "Task title" --description "Details" --due "2025-04-30"

# IMPORTANT: Task creation has sync delay!
# Tasks created may not appear in queries immediately (API sync delay)
# Wait 30-60 seconds or query by specific criteria

# Filter by completion status
lark-cli task +get-my-tasks --complete

# Filter by due date (ISO 8601 format required)
lark-cli task +get-my-tasks --due-end "2025-04-30T23:59:59+08:00"

# Search by keyword
lark-cli task +get-my-tasks --query "项目名称"
```

### Base Domain
```bash
# List apps
lark-cli base +list-apps

# Create a new base
lark-cli base +base-create --name "Project Tracker"

# List tables in base
lark-cli base +table-list --base-token "YOUR_BASE_TOKEN"

# List fields in table
lark-cli base +field-list --base-token "xxx" --table-id "tblxxx"

# Create/update record (use +record-upsert, not +record-create)
lark-cli base +record-upsert \
  --base-token "xxx" \
  --table-id "tblxxx" \
  --json '{"FieldName":"Value","Status":"Done"}'

# List records
lark-cli base +record-list --base-token "xxx" --table-id "tblxxx"

# Query with DSL (JSON query language)
lark-cli base +data-query --base-token "xxx" --dsl '{"query":"SELECT * FROM table"}'
```

### Wiki/Doc Domain (Personal Account)
```bash
# List spaces
lark-cli wiki spaces list

# List nodes in space
lark-cli wiki nodes list --params '{"space_id":"xxx"}'

# Fetch document
lark-cli docs +fetch --token "doc_token"
```

### IM Domain
```bash
# Search chats
lark-cli im +chat-search --query "群名"

# Send message
lark-cli im +messages-send --chat-id "xxx" --content "Hello"

# Send rich text (markdown)
lark-cli im +messages-send --chat-id "xxx" --msg-type markdown --content "# Title\nContent"
```

## Skill Development Workflow

### For Competition/Hackathon (14-day sprint)

```markdown
Week 1: Foundation
- Day 1: Environment verification + scope testing
- Day 2: Competitor analysis
- Day 3: CLI interface design
- Day 4: Data model design
- Day 5-6: SKILL.md draft
- Day 7: Review & revise

Week 2: Demo & Polish
- Day 8: Demo environment setup
- Day 9: Demo script
- Day 10: Message templates
- Day 11: Best practices
- Day 12: Final review
- Day 13: Submission materials
- Day 14: Submit
```

### SKILL.md Structure

```markdown
---
name: lark-workflow-xxx
description: Clear description of what this does
version: 1.0.0
author: Your name
---

# Workflow Name

## Overview
One sentence description

## Use Cases
### Case 1: Daily standup
Description...

## Prerequisites
### Auth
\`\`\`bash
lark-cli auth login --domain task,base,im
\`\`\`

### Scopes
- task:task:read
- base:app:read
- im:message

## Commands
\`\`\`bash
lark-cli workflow daily-standup --project "xxx"
\`\`\`

## Examples
Complete examples with expected output

## Best Practices
Tips and tricks

## Troubleshooting
Common issues and solutions
```

## Advanced Capabilities & Boundaries

### Domain Command Inventory (v1.0.23)

Total: 22 domains, 340+ commands. Use `lark-cli <domain> --help` for details.

| Domain | Cmds | R/W | Key Purpose |
|--------|------|-----|-------------|
| wiki | 6 | R/W | Knowledge spaces, nodes, members, move docs into wiki |
| docs | 9 | R/W | Document create/fetch/update/search, media, whiteboard |
| drive | 25 | R/W | Files, upload/download, import/export, sync, search, perms, comments |
| base | 75 | R/W | Bitable full lifecycle: tables, fields, records, views, dashboards, workflows, forms, roles |
| task | 24 | R/W | Tasks, tasklists, subtasks, AI agent, event subscription, search |
| im | 16 | R/W | Messages, chats, search, pins, reactions, resource download |
| calendar | 11 | R/W | Events, agenda, freebusy, rooms, RSVP, suggestions |
| sheets | 41 | R/W | Spreadsheet full operations: read/write, styles, filters, images |
| mail | 32 | R/W | Email, drafts, folders, labels, templates, rules, threads |
| okr | 19 | R/W | OKR cycles, objectives, key results, progress, indicators |
| contact | 2 | R | Search user, get user info |
| slides | 5 | R/W | Presentations, media, slide replacement |
| approval | 2 | R | Approval instances and tasks (read-only) |
| minutes | 4 | R/W | Meeting minutes search/download/upload |
| vc | 4 | R | Video conferences, recordings, notes |
| attendance | 1 | R | Attendance records |
| whiteboard | 2 | R/W | Whiteboards (mermaid/plantuml DSL) |
| event | 5 | R/W | Real-time event subscription/consumption |
| markdown | 3 | R/W | Drive-native .md file create/fetch/overwrite |
| config | 6 | -- | Configuration, credential binding, strict mode |
| auth | 6 | -- | OAuth, scope queries, login/logout |
| profile | 5 | -- | Multi-profile management |

## API Coverage (2500+ APIs across 22 domains)

| Domain | Command | APIs | Key Capabilities | Personal Data |
|--------|---------|------|------------------|---------------|
| **task** | `lark-cli task` | 75+3 | Task mgmt, checklists, reminders | ✅ Auth required |
| **calendar** | `lark-cli calendar` | 44+4 | Events, scheduling, attendees | ✅ Auth required |
| **im** | `lark-cli im` | 76+14 | Messages, groups, chat history | ✅ Auth required |
| **base** | `lark-cli base` | 52+2 | Bitable, records, views, dashboards | ✅ Auth required |
| **docs** | `lark-cli docs` | 12 | Doc creation, editing, media | ✅ Auth required |
| **wiki** | `lark-cli wiki` | 16 | Knowledge spaces, nodes | ✅ Auth required |
| **drive** | `lark-cli drive` | 40+10 | Files, uploads, downloads | ✅ Auth required |
| **sheets** | `lark-cli sheets` | 56 | Spreadsheets | ✅ Auth required |
| **slides** | `lark-cli slides` | - | Presentations | ✅ Auth required |
| **mail** | `lark-cli mail` | - | Email management | ✅ Auth required |
| **minutes** | `lark-cli minutes` | - | Meeting records | ✅ Auth required |
| **approval** | `lark-cli approval` | 55+7 | Approval workflows | ✅ Auth required |
| **attendance** | `lark-cli attendance` | 39 | Attendance tracking | ✅ Auth required |
| **contact** | `lark-cli contact` | 78+17 | Contacts, org structure | ✅ Auth required |
| **vc** | `lark-cli vc` | 57+18 | Video conferences | ✅ Auth required |
| **okr** | `lark-cli okr` | - | OKR management | ✅ Auth required |
| **helpdesk** | `lark-cli helpdesk` | 50+4 | Service desk tickets | ✅ Auth required |
| **workplace** | `lark-cli workplace` | 3 | Workbench apps | ❌ No personal data |
| **whiteboard** | `lark-cli whiteboard` | - | Whiteboards | ✅ Auth required |

### Batch Operations

| Operation | Batch Support | Limit | Command |
|-----------|--------------|-------|---------|
| Task create | ❌ | 1 per call | Loop required |
| Task update | ❌ | 1 per call | Loop required |
| Base record create | ✅ | 200/req | `+record-batch-create` (was 500, enforced 200 since v1.0.13) |
| Base record update | ✅ | 200/req | `+record-batch-update` (was 500, enforced 200 since v1.0.13) |
| Message send | ❌ | 1 per call | Rate limit: 20/sec |
| Calendar event create | ❌ | 1 per call | Loop required |
| Chat member add | ✅ | 50/req | `chat.members +add` |

### Data Export Formats

```bash
# JSON (default)
lark-cli task +get-my-tasks --format json

# Table (human-readable)
lark-cli calendar +agenda --format table

# CSV
lark-cli base +record-list --format csv

# NDJSON (streaming)
lark-cli contact +search-user --format ndjson

# Pretty (formatted)
lark-cli wiki spaces list --format pretty
```

### Advanced Query Patterns

#### Pagination
```bash
# Auto-pagination (fetches all pages)
lark-cli task +get-my-tasks --page-all --page-limit 40

# Custom page size
lark-cli base +record-list --base-token "xxx" --page-size 100

# With delay (avoid rate limits)
lark-cli contact +search-user --page-all --page-delay 500
```

#### JSON Filtering (jq)
```bash
# Filter specific fields
lark-cli task +get-my-tasks -q '.data.items[] | {summary, due_date}'

# Filter by condition
lark-cli base +record-list --base-token "xxx" -q '.data[] | select(.status == "Done")'
```

#### Dry Run (Preview)
```bash
# Preview without executing
lark-cli base +record-upsert --dry-run --base-token "xxx" --json '{...}'
```

### Schema Introspection

```bash
# View API metadata
lark-cli schema task.tasks.get
lark-cli schema calendar.events.create
lark-cli schema contact.users.list

# Shows: parameters, response structure, required scopes, doc links
```

### Generic API Access

```bash
# Direct API calls for any endpoint
lark-cli api GET /open-apis/calendar/v4/calendars
lark-cli api POST /open-apis/task/v2/tasks --data '{"summary":"test"}'
lark-cli api GET /open-apis/contact/v3/users --params '{"page_size":50}'
```

### Rate Limits & Constraints

| Resource | Limit | Notes |
|----------|-------|-------|
| API calls | 100/sec/app | Enterprise can request increase |
| Message send | 20/sec/app | Anti-spam protection |
| File upload | 100MB/file | Single file limit |
| Batch records | 500/operation | Base batch operations |
| Query time range | 180 days | Calendar time span |
| Page size | 50-500 | Domain dependent |

### Data Sync Delays

| Operation | Delay | Cause | Workaround |
|-----------|-------|-------|------------|
| Task create→query | 1-5 sec | Eventual consistency | Wait 30-60s or query by specific criteria |
| Message send→display | Real-time | Immediate sync | None needed |
| Doc update→search | 1-5 min | Indexing delay | Use Wiki nodes list instead |
| Base record→query | Real-time | Immediate sync | None needed |
| Calendar event→query | Real-time | Immediate sync | None needed |

**Important**: Task creation has a notable sync delay. After creating a task, it may not appear in `+get-my-tasks` queries immediately. This is normal behavior, not an error.

**Testing approach**:
```bash
# Create task
lark-cli task +create --summary "Test" --due "2025-04-30"
# Returns: guid created

# Immediate query may return empty
lark-cli task +get-my-tasks --query "Test"
# Returns: items: null (expected!)

# Wait 30-60 seconds and retry
sleep 30
lark-cli task +get-my-tasks --query "Test"
# Returns: task data (now available)
```
## Troubleshooting

### Issue: "missing required scope(s)"

**Check**: Run `lark-cli auth status` and check scope list

**Solutions**:
1. Try `--domain` auth instead of `--scope`
2. Find alternative commands that work with available scopes
3. For personal accounts, accept limitations and document workarounds

### Issue: "unknown flag"

**Check**: Command syntax varies by domain

**Solution**: Always verify with `--help`:
```bash
lark-cli <domain> <command> --help
```

### Issue: Empty results after creating data

**Symptom**: Task/Base created successfully but queries return empty

**Causes**:
1. **Task API**: Sync delay between create and query (30-60 seconds or longer)
2. **Base API**: Immediate availability, check table-id and base-token
3. **Auth scope**: Token doesn't have permission to read the data

**Solutions**:
- For tasks: Wait or query by specific criteria (due date, completion status)
- For base: Verify token and table permissions
- Check `lark-cli auth status` for scope coverage
- **Important**: Document this delay in your skill - users should expect tasks to not appear immediately

### Issue: "unknown flag: --limit"

**Cause**: Different commands use different flag names

**Solution**: Use domain-specific flags:
```bash
# Task uses --page-limit
lark-cli task +get-my-tasks --page-limit 20

# IM uses --page-limit
lark-cli im +chat-search --query "xxx"

# Wiki uses --params for JSON
lark-cli wiki nodes list --params '{"space_id":"xxx"}'
```

## Industry Research for Skill Positioning

When developing Feishu skills for specific use cases, research the target industries to ensure relevance. This helps position your skill for the right audience and demonstrate real-world value.

### Research Methodology

**Step 1: Browse Customer Cases**
```bash
# Visit the customer showcase page
https://www.feishu.cn/customers

# Filter by industry
https://www.feishu.cn/customers?tag=制造业
https://www.feishu.cn/customers?tag=互联网
https://www.feishu.cn/customers?tag=零售
```

**Step 2: Analyze Industry Solutions**
```bash
# Check dedicated industry solution pages
https://www.feishu.cn/industry_solutions/manufacturing
https://www.feishu.cn/industry_solutions/retail
https://www.feishu.cn/industry_solutions/catering
```

**Step 3: Identify Scale Indicators**
Look for employee count badges in case studies:
- `>100,000 人` - Enterprise scale (e.g., 极兔速递)
- `>50,000 人` - Large enterprise (e.g., 霸王茶姬)
- `>10,000 人` - Mid-large enterprise (e.g., 益禾堂)

**Step 4: Extract Pain Points**
From case study descriptions, identify:
- Workflow inefficiencies
- Coordination challenges
- Scale-related issues
- Compliance requirements

### Top Feishu User Industries (by customer case studies)

| Industry | Priority | Use Case Fit | Examples |
|----------|----------|--------------|----------|
| **Manufacturing** | ⭐⭐⭐⭐⭐ | Project management, quality control | 理想汽车, 小米, 三一重工 |
| **Retail/Chain** | ⭐⭐⭐⭐⭐ | Store operations, staff onboarding | 海底捞, 霸王茶姬, 物美 |
| **Internet/SaaS** | ⭐⭐⭐⭐⭐ | Team collaboration, agile dev | 抖音, PingCAP, 去哪儿 |
| **Food & Beverage** | ⭐⭐⭐⭐ | Multi-store management | 海底捞, 西贝, 益禾堂 |
| **Smart Mobility** | ⭐⭐⭐⭐ | Supply chain, R&D | 理想, 蔚来, 小鹏 |
| **Logistics** | ⭐⭐⭐ | Large workforce management | 极兔速递 (100k+ employees) |
| **Healthcare** | ⭐⭐⭐ | Compliance, knowledge management | 联影医疗 |

### Research Method

1. **Browse customer cases**: https://www.feishu.cn/customers
2. **Filter by industry tag**: `/customers?tag=制造业`
3. **Check solution pages**: `/industry_solutions/{industry}`
4. **Analyze scale indicators**: Look for employee counts (e.g., ">50,000 人")

### Skill Positioning Tips

- **Retail/F&B chains**: High-frequency onboarding, standardized processes
- **Manufacturing**: Blue-collar worker onboarding, safety training
- **Internet/SaaS**: Technical onboarding, documentation-heavy
- **Logistics**: Large-scale, seasonal hiring patterns

## Document Indexing Pattern: Base + Wiki (方案1+3)

Solving the "scattered cloud docs" problem with a two-layer architecture:
- Base (多维表格) as structured data/index layer
- Wiki (知识库) as navigation/discovery layer

### Why Not Shortcut?

**Critical limitation**: `wiki +node-create --node-type shortcut --origin-node-token TOKEN`
only works when TOKEN is a wiki node token. Documents in Drive root, chat messages,
or shared folders cannot be shortcutted into a wiki space.

**Workaround**: Create docx pages in wiki containing markdown hyperlinks to original docs.
`docs +create --wiki-space XXX --title "Index Card" --markdown "- [Doc Title](feishu_url)"`
Users click hyperlinks in Feishu client to jump to originals. Originals stay in place.

### Architecture: Three Layers

| Layer | Feishu Object | Purpose |
|---|---|---|
| Raw sources | Scattered Feishu cloud docs (never moved or modified) | Ground truth |
| Data layer | Base (多维表格) with structured fields + Dashboard | Search, filter, statistics |
| Navigation layer | Wiki tree with index-card docx pages | Human browsing, categorization |

### Base Table Schema

Fields: 标题(text) | 类型(singleSelect: docx/sheet/bitable/mindnote/slides) |
来源(singleSelect: Drive/Wiki/聊天/共享) | 创建时间(date) | 编辑时间(date) |
标签(multiSelect) | 链接(link) | AI摘要(text) | 状态(singleSelect: 待整理/已整理/待复核/已归档)

### API Pitfalls (Base + Wiki)

1. **+table-create --fields JSON**: Do NOT include `property` key on datetime fields. Error 800010701 "Unrecognized key(s)". Just use `{"name":"字段名","type":"datetime"}`.

2. **+record-batch-create with select fields**: Values MUST match existing field options exactly. Error 800030005 "not_found". If you created a select field without options, you cannot write to it via batch. Either: (a) skip that field in the batch, or (b) use +field-update to add options first.

3. **@file paths must be relative**: `--json @/tmp/file.json` fails. Must use `--json @file.json` from current directory. Cd or use relative paths like `./file.json`. **For hermes execute_code**: the sandbox CWD differs from terminal CWD, so `@file.json` won't find files written to /tmp. Use `cat file | lark-cli ... --json -` pipe pattern instead, or write files to the terminal CWD.

4. **Dashboard +dashboard-create**: May return internal error (800008006) on first call but actually succeed. A retry gives "name already exists" conflict, confirming creation worked.

5. **drive +search --page-token**: The page_token is a complex JSON string with special chars. Must save to file and use `@file` to pass it. Pagination sometimes returns duplicate results -- verify data before ingesting.

6. **Wiki space has no root node**: A newly created wiki space returns empty nodes list. You must create the first node with `wiki +node-create --space-id XXX --title "Root"`. This becomes the root page.

7. **docs +update via stdin**: `--markdown -` reads from stdin. Use subprocess pipe (not hermes terminal) for multi-line markdown content with special characters. **In hermes execute_code**: `cat /tmp/file.md | lark-cli docs +update --doc TOKEN --mode overwrite --markdown -` works reliably.

8. **New base includes default table**: Always list tables after +base-create, then delete the default "数据表" with `--yes` flag. Cannot delete the last table -- create your table first, then delete the default.

9. **link type field unsupported**: `+field-create --json '{"name":"链接","type":"link"}'` fails silently or errors. Use `"type":"url"` instead -- it creates a text field that accepts URLs. The link type is a UI-only concept in Feishu, not a real field type via API.

10. **URL field values must be plain strings**: When writing to a url-type field via API, pass a plain string `"https://..."`, NOT an object like `{"link":"https://...","text":"..."}`. Object format causes `TextFieldConvFail` error 1254060.

11. **+field-create ignores property**: The `--json` flag on +field-create does not support setting `property` (e.g., select options). Create the field empty, then use raw API `lark-cli api PUT "/open-apis/bitable/v1/apps/TOKEN/tables/TBL/fields/FIELD_ID" --data '{"field_name":"Name","type":3,"property":{"options":[{"name":"opt1","color":0}]}}'` to set options. Type codes: 3=singleSelect, 4=multiSelect.

12. **drive +search HTML highlights**: Search results in `title_highlighted` contain `<h>` tags for match highlighting. Always clean with `re.sub(r'</?h>', '', title)` before using titles.

13. **drive +search limited pagination**: Empty-query pagination returns same results repeatedly for personal accounts. Use multiple keyword queries (`--query "AI"`, `--query "飞书"`, etc.) to discover more documents. Deduplicate by URL.

14. **Dashboard block group_by format**: The `--data-config` for +dashboard-block-create expects `group_by` as an **array** `{"group_by":[{"field_name":"类型"}]}`, not an object `{"group_by":{"field_name":"类型"}}`. The object format causes "Expected array, received object" validation error.

15. **docs +update --new-title for rename**: Wiki nodes have no rename API. Use `lark-cli docs +update --doc OBJ_TOKEN --new-title "New Title" --mode overwrite --markdown -` to change the displayed title in wiki tree.

16. **+field-delete requires --yes**: `lark-cli base +field-delete` prompts for confirmation. Add `--yes` flag for scripted use.

17. **hermes terminal jq limitations**: When using `-q` (jq filter) with hermes terminal tool, curly braces in jq expressions may get mangled. Use `-q '.data.data | length'` (simple filters) or redirect to file then parse with execute_code instead of complex jq with string interpolation.

### CLI Workflow

Step 1 -- Scan scattered docs:
```bash
lark-cli drive +search --query "" --sort edit_time --page-size 20
# Omit --space-ids and --folder-tokens for cross-space search
# Use --mine for "docs I created"
# Use --doc-types to filter by type
```

Step 2 -- Ingest into Base:
```bash
lark-cli base +record-upsert --base-token XXX --table-id XXX \
  --json '{"标题":"doc name","类型":"docx","来源":"Drive","链接":"https://..."}'
# Or batch:
lark-cli base +record-batch-create --base-token XXX --table-id XXX \
  --json '{"fields":["标题","类型","链接"],"rows":[["doc1","docx","url1"],["doc2","sheet","url2"]]}'
```

Step 3 -- Create wiki index cards:
```bash
# Create parent node for category
lark-cli wiki +node-create --space-id XXX --title "按项目" --obj-type docx
# Create index card under parent
lark-cli wiki +node-create --space-id XXX --parent-node-token PARENT --title "项目A - 文档索引" --obj-type docx
# Write content with hyperlinks to originals
lark-cli docs +update --doc CARD_TOKEN --mode append \
  --markdown "## 相关文档\n- [需求文档](https://feishu.cn/docx/TOKEN)\nAI摘要: ..."
```

Step 4 -- Create Base dashboard:
```bash
lark-cli base +dashboard-create --base-token XXX --name "文档统计"
```

### Dashboard Block Creation

```bash
# Create dashboard
lark-cli base +dashboard-create --base-token TOKEN --name "文档统计"

# Create chart blocks (group_by MUST be array!)
lark-cli base +dashboard-block-create --base-token TOKEN --dashboard-id DASH_ID \
  --name "文档类型分布" --type "pie" \
  --data-config '{"table_name":"文档索引","count_all":true,"group_by":[{"field_name":"类型"}]}'

# Supported block types: statistics, pie, bar, column, ring, text, funnel
# data-config options: count_all (bool), group_by (array of {field_name})

# Auto-layout all blocks after creation
lark-cli base +dashboard-arrange --base-token TOKEN --dashboard-id DASH_ID
```

### Data Cleanup Pattern (Bulk Field Updates)

```bash
# +record-batch-update applies SAME fields to ALL records in record_id_list
lark-cli base +record-batch-update --base-token TOKEN --table-id TBL \
  --json '{"record_id_list":["rec1","rec2"],"fields":{"标签":"AI/图像生成"}}'

# For per-record different values, use individual PUT via raw API:
lark-cli api PUT "/open-apis/bitable/v1/apps/TOKEN/tables/TBL/records/REC_ID" \
  --data '{"fields":{"标签":"新标签","类型":"DOCX"}}'

# NOTE: raw API batch_update (POST .../records/batch_update) fails with select field
# validation errors even when single PUT works. Prefer single PUT loops for reliability.
```

### End-to-End Execution Template

The workflow below shows how to create your own Base, Wiki space, and dashboard.
Replace every placeholder token with resources from your own Feishu/Lark tenant.

**Resource placeholders:**
- Base: `YOUR_BASE_TOKEN`, table `YOUR_TABLE_ID`
- Wiki: `YOUR_SPACE_ID`, root node `YOUR_ROOT_NODE`
- Dashboard: `YOUR_DASHBOARD_ID`

**Step 0 -- Wiki space creation:**
```bash
# No dedicated command exists; use generic API
lark-cli api POST /open-apis/wiki/v2/spaces \
  --data '{"name":"文档导航中心","description":"飞书云文档统一导航与发现","space_type":"team"}'
# Returns: space_id, root_page_token
```

**Step 1 -- Base creation + table setup:**
```bash
# Create base
lark-cli base +base-create --name "文档导航中心"
# Create table (NOTE: omit property on datetime fields!)
lark-cli base +table-create --base-token TOKEN --name "文档索引" \
  --fields '[{"name":"标题","type":"text"},{"name":"类型","type":"singleSelect"},{"name":"链接","type":"url"}]'
# ^^^ Even if error 800010701 fires, table may still be created. Check with +table-list.
# Delete default empty table AFTER creating your own (can't delete last table)
lark-cli base +table-delete --base-token TOKEN --table-id DEFAULT_TBL --yes
```

**Step 2 -- Add remaining fields individually:**
```bash
# Fields not created by +table-create (due to error interrupt) must be added manually
lark-cli base +field-create --base-token TOKEN --table-id TBL \
  --json '{"name":"类型","type":"singleSelect"}'
lark-cli base +field-create --base-token TOKEN --table-id TBL \
  --json '{"name":"来源","type":"singleSelect"}'
lark-cli base +field-create --base-token TOKEN --table-id TBL \
  --json '{"name":"更新时间","type":"dateTime"}'
lark-cli base +field-create --base-token TOKEN --table-id TBL \
  --json '{"name":"所有者","type":"text"}'
lark-cli base +field-create --base-token TOKEN --table-id TBL \
  --json '{"name":"链接","type":"url"}'  # NOT "link" type!
```

**Step 3 -- Scan and ingest documents:**
```bash
# Scan scattered docs across all spaces
lark-cli drive +search --query "" --sort edit_time --page-size 20 --format json
# Individual record insert (works reliably for small batches)
lark-cli base +record-create --base-token TOKEN --table-id TBL \
  --data '{"标题":"Doc Name","链接":"https://feishu.cn/wiki/TOKEN","所有者":"Owner Name"}'
# NOTE: select fields (类型/来源) left null if no options defined yet
```

**Step 4 -- Wiki tree + index cards:**
```bash
# Create root page
lark-cli wiki +node-create --space-id SPACE --title "文档导航中心" --obj-type docx
# Create category folders under root
lark-cli wiki +node-create --space-id SPACE --parent-node-token ROOT --title "按类型" --obj-type docx
lark-cli wiki +node-create --space-id SPACE --parent-node-token ROOT --title "按主题" --obj-type docx
lark-cli wiki +node-create --space-id SPACE --parent-node-token ROOT --title "最近更新" --obj-type docx

# Create index card under category (e.g., under 按主题)
lark-cli wiki +node-create --space-id SPACE --parent-node-token THEME_FOLDER --title "AI/图像生成" --obj-type docx
# Write content via stdin pipe (NOT hermes terminal -- use subprocess)
# Python: subprocess.Popen(["lark-cli","docs","+update","--doc",OBJ,"--mode","overwrite","--markdown","-"], stdin=PIPE)
echo "## AI/图像生成\n- [Doc Title](https://feishu.cn/wiki/TOKEN)" | \
  lark-cli docs +update --doc CARD_OBJ_TOKEN --mode overwrite --markdown -
```

**Step 5 -- Dashboard:**
```bash
lark-cli base +dashboard-create --base-token TOKEN --name "文档统计"
```

**Key lessons from execution:**
- Card naming: avoid redundant suffixes (name "文档" not "文档文档" under "按类型/")
- docs +update with --markdown - via stdin: must use subprocess pipe, hermes terminal mangles multi-line
- select fields without pre-defined options accept null only; add options via +field-update first if values needed
- Wiki tree verification: `lark-cli wiki nodes list --params '{"space_id":"XXX","parent_node_token":"PARENT"}'`

### Wiki Navigation Tree Structure

```
文档导航中心 (root)
├── 按项目/
│   ├── 项目A/ (index card with links)
│   └── 项目B/ (index card with links)
├── 按类型/
│   ├── 文档/ (index card)
│   ├── 表格/ (index card)
│   └── 多维表格/ (index card)
└── 最近更新/ (index card, grouped by week)
```

## Wiki Space as Knowledge Base (LLM Wiki Pattern)

Mapping Karpathy's LLM Wiki pattern onto Feishu's native Wiki Spaces. The goal: user finds good Feishu docs → AI extracts and structures them into a dedicated Wiki Space → knowledge compounds over time.

### Three-Layer Architecture (LLM Wiki Variant)

| LLM Wiki Layer | Feishu Implementation |
|---|---|
| Raw sources | Scattered Feishu cloud docs (read-only, never modified) |
| The Wiki | A dedicated Wiki Space with structured nodes (entities/, concepts/, comparisons/, index, log, schema) |
| The Schema | A Feishu doc within the space defining conventions, tags, page templates |

### Core CLI Commands for Wiki Knowledge Base

**Create folder structure (parent nodes):**
```bash
lark-cli wiki +node-create --space-id "SPACE_ID" --title "entities" --obj-type docx
```

**Create a knowledge page under a folder:**
```bash
lark-cli wiki +node-create \
  --space-id "SPACE_ID" \
  --parent-node-token "PARENT_TOKEN" \
  --title "Page Title"
```

**Fetch source document content:**
```bash
lark-cli docs +fetch --doc "SOURCE_DOC_TOKEN"
```

**Write structured content to a wiki page:**
```bash
lark-cli docs +update --doc "NODE_TOKEN" \
  --mode overwrite \
  --markdown "## Overview\n...\n## Sources\n- [Original](feishu_url)"
```

**Append cross-references to existing pages:**
```bash
lark-cli docs +update --doc "EXISTING_TOKEN" \
  --mode append \
  --markdown "\n**Related:** [Concept Name](wiki_url)"
```

**Update index at a specific section:**
```bash
lark-cli docs +update --doc "INDEX_TOKEN" \
  --selection-by-title "## Entities" \
  --mode insert_after \
  --markdown "- [Entity Name](wiki_url) - one-line summary"
```

**Append to log:**
```bash
lark-cli docs +update --doc "LOG_TOKEN" \
  --mode append \
  --markdown "\n## [2026-05-03] ingest | Source Title\n- Created: entities/x\n- Updated: concepts/y"
```

**List all wiki nodes (for query/lint):**
```bash
lark-cli wiki nodes list --params '{"space_id":"SPACE_ID"}' --page-all
```

**Create a shortcut node (like a symbolic link):**
```bash
lark-cli wiki +node-create \
  --space-id "SPACE_ID" \
  --node-type shortcut \
  --origin-node-token "ORIGINAL_TOKEN" \
  --title "Shortcut Title"
```

**Move an existing Drive doc into Wiki:**
```bash
lark-cli wiki +move \
  --obj-token "DOC_TOKEN" \
  --obj-type docx \
  --target-space-id "SPACE_ID"
```

### Key Limitations vs Obsidian/Local Markdown

| Capability | Feishu Wiki | Obsidian |
|---|---|---|
| Backlinks (auto) | NO -- must maintain manually in "Related" sections | YES |
| Graph view | NO -- only directory tree | YES |
| [[wikilinks]] | NO -- use [text](url) hyperlinks instead | YES |
| Full-text search API | LIMITED -- nodes list +逐个 fetch | YES (qmd/BM25) |
| Section-level update | selection-by-title works but precision is limited | Direct file edit |
| Cross-references | Manual hyperlink maintenance | Automatic |
| Team collaboration | YES (built-in) | Plugin-dependent |
| Permission control | YES (built-in) | Manual |
| Mobile access | YES (Feishu app) | Obsidian mobile app |

### Practical Workarounds

1. **Backlinks**: Every page gets a "## Related" section at the bottom. Lint operation scans all pages and reports orphan pages (no inbound links from other pages).

2. **Search at scale**: For wikis under ~50 pages, `nodes list` + selective `+fetch` is adequate. Beyond that, maintain a thorough index doc and use `selection-by-title` or `+search` to locate content.

3. **Graph visualization**: Not available natively. Option: use `drive +pull` to mirror wiki to local markdown, then open in Obsidian for graph view (dual-write approach).

4. **Complex document formats**: `docs +fetch` outputs Lark-flavored Markdown. Tables and whiteboards may lose formatting. For source docs with heavy formatting, keep the original link in the knowledge page rather than trying to replicate structure.

### Dual-Write Approach (Feishu + Obsidian)

For users wanting full LLM Wiki experience:
- AI writes to both Feishu Wiki Space (team consumption) and local markdown files (Obsidian graph view)
- `drive +pull` / `drive +push` (v1.0.23) for file-level sync
- Obsidian reads the same markdown files, provides graph view and local search
- This adds complexity but unlocks the complete pattern

## Detailed Domain Capability Boundaries

### Wiki Domain (6 commands)

CAN:
  + List all wiki spaces (spaces list)
  + List nodes with hierarchy (nodes list, filter by parent_node_token)
  + Node info: title, obj_token, obj_type, creator, has_child, create/edit time
  + Create nodes with hierarchy (+node-create: space-id, parent-node-token, obj-type, title)
  + Create shortcut nodes (symbolic links across spaces)
  + Move nodes within/across spaces (+move --node-token)
  + Move Drive docs into Wiki (+move --obj-token --obj-type --target-space-id)
  + Delete spaces (+delete-space)
  + Manage space members (members create/delete/list)

CANNOT:
  X Search wiki content directly (use drive +search --space-ids or docs +search)
  X Sort nodes via API
  X Tag/categorize nodes
  X Get backlinks between wiki pages
  X Copy/duplicate nodes (only move)
  X Batch create nodes
  X Create wiki spaces via shortcut (use lark-cli api POST /open-apis/wiki/v2/spaces)

### Docs Domain (9 commands)

CAN:
  + Create docs with markdown content (+create --wiki-space or --folder-token)
  + Create docs directly into a wiki space (--wiki-space flag)
  + Read docs as Markdown (+fetch, supports v1/v2)
  + Update docs with 7 modes: append, overwrite, replace_range, replace_all, insert_before, insert_after, delete_range
  + Locate sections by title (--selection-by-title "## Section")
  + Locate content by range (--selection-with-ellipsis "start...end")
  + Rename docs (--new-title)
  + Search docs (+search)
  + Media: upload/download/preview/insert images and files
  + Whiteboard: update with mermaid/plantuml DSL

CANNOT:
  X Get block-level AST (docs +fetch outputs rendered Markdown, not block tree)
  X Operate on embedded tables (they're not sheets, no independent API)
  X Create/manage document comments
  X Get document edit/view history
  X Set document permissions (use drive permission.members instead)
  X selection-by-title is ambiguous with duplicate headings
  X selection-with-ellipsis breaks when content changes

### Drive Domain (25 commands)

CAN:
  + File management: upload, download, create-folder, delete, move, create-shortcut
  + Import local files as cloud docs (+import: .docx/.xlsx/.md/.base)
  + Export cloud docs to local (+export: docx/pdf/xlsx/csv/markdown/.base)
  + One-way sync: +pull (Drive->local), +push (local->Drive), +status (diff)
  + Search with rich filters (+search: --space-ids, --doc-types, --mine, --query, time filters)
  + Comments: add/list/reply (+add-comment, file.comments)
  + Permissions: +apply-permission, permission.members
  + File statistics and view records
  + @file support for params and data (v1.0.23)

CANNOT (for pull/push):
  X Sync online docs (docx/sheet/bitable/mindnote/slides are SKIPPED by pull/push)
  X Only type=file entries are synced by pull/push
  X Knowledge base wiki pages cannot be synced to local via pull/push

IMPORTANT: drive +search --space-ids is the recommended alternative to docs +search
  for personal accounts that lack search:docs:read scope.

### Base Domain (75 commands -- largest domain)

Full lifecycle management for Bitable (multidimensional tables):
  Tables, Fields, Records, Views, Dashboards, Workflows, Forms, Roles
  Can serve as structured metadata storage for wiki knowledge bases
  (e.g., page index, tags, cross-references, relationship mapping)

### Markdown Domain (3 commands -- NEW in v1.0.23)

Operates on Drive-native .md files (NOT wiki docs):
  +create: create .md file in Drive with --content or --file
  +fetch: read .md file from Drive
  +overwrite: replace .md file content

Note: These are Drive files, not wiki nodes. Use wiki +move to bring them
into a wiki space after creation.

### Event Domain (5 commands -- NEW in v1.0.21)

Real-time event subscription system:
  list: show all available EventKeys grouped by domain
  schema: show event type details
  consume: start consuming events for an EventKey
  status: show event bus daemon status
  stop: stop event bus daemon

Available events (all bot-only auth):
  im: chat.disbanded, member.bot.added/deleted, member.user.added/deleted/withdrawn,
      chat.updated, message.read, reaction.created/deleted, message.receive
  (More events available depending on app configuration)

### Generic API Access (lark-cli api)

Fallback for any unimplemented operation:
  lark-cli api GET/POST/PUT/DELETE <path> [--params JSON] [--data JSON]
  Can call ANY Feishu Open Platform API endpoint.

Examples:
  lark-cli api POST /open-apis/wiki/v2/spaces --data '{"name":"New Space"}'
  lark-cli api GET /open-apis/wiki/v2/spaces/{space_id}/nodes

### Cross-Domain Integration Patterns

1. Doc -> Wiki: docs +create --wiki-space OR wiki +move --obj-token
2. Wiki -> Content: wiki nodes list -> docs +fetch --doc obj_token
3. IM -> Wiki: im +messages-search -> parse doc links -> docs +fetch -> wiki
4. Base as Index: base tables store page metadata, tags, relationships
5. Event-driven: event consume -> trigger auto-ingest on doc changes
6. Search alternative: drive +search --space-ids instead of docs +search

## External Tool Integration

### Tavily AI Search (API Wrapper Pattern)

When npm packages require specific runtimes (e.g., Bun) that aren't available, create a lightweight wrapper using curl:

**Problem**: `npm install -g tavily-cli` requires Bun runtime, not compatible with standard Node.js

**Solution**: Bash script wrapper calling REST API directly

```bash
#!/bin/bash
# tavily-cli.sh - API wrapper for Tavily

API_KEY="${TAVILY_API_KEY:-}"
BASE_URL="https://api.tavily.com"

cmd_search() {
    local query="$1"
    curl -s -X POST "$BASE_URL/search" \
        -H "Content-Type: application/json" \
        -d "{
            \"api_key\": \"$API_KEY\",
            \"query\": \"$query\",
            \"search_depth\": \"basic\",
            \"max_results\": 5
        }" | python3 -m json.tool
}

# Usage: ./tavily-cli.sh search "query"
```

**Benefits**:
- No runtime dependencies beyond curl + python3
- Full API coverage (search, extract, crawl)
- Easy to customize for specific use cases
- Works in restricted environments

**Setup**:
```bash
export TAVILY_API_KEY="tvly-xxx"
./tavily-cli.sh search "新员工入职最佳实践"
```

**Pattern applicability**: Any REST API with simple auth (API key in header/body)

## Version History & Key Features (1.0.15-1.0.23)

Current version: **1.0.23** (installed via `npm install -g @larksuite/cli`)
Check: `lark-cli --version`

### v1.0.23 (2026-04-30)
- **base**: Markdown output for record reads (#726)
- **cmdutil**: `@file` support for params and data -- read JSON from file (#724)
- **doc**: Warn when callout uses type= without background-color (#467)
- **drive**: `+pull` shortcut for one-way Drive -> local mirror (#696)
- **drive**: `+push` shortcut for one-way local -> Drive mirror (#709)
- **drive**: `+status` shortcut for content-hash diff (#692)
- **minutes**: Media upload shortcut (#725)
- **SKILL docs**: Official markdown shortcuts and skill docs system (#704)
- **doc v2**: Guide for lark-doc v2 usage (#710)
- **drive export**: `--file-name` support (#685)

### v1.0.22 (2026-04-29)
- **task**: Resource agent & agent_task_step_info -- AI agent fields in tasks (#693)
- **task**: App members support (#712)
- **contact**: `+search-user --queries` multi-name fanout (#707)
- **mail**: Calendar events in emails (#646)
- **slides**: Template support (#684)

### v1.0.21 (2026-04-28)
- **event**: Event subscription & consume system (#654) -- critical for sync workflows
- **contact**: Search filters and richer profile fields (#648)
- **mail**: Email template management + `--template-id` on compose (#642)
- **okr**: Progress records (#574) -- new OKR domain capability
- **calendar**: Enhanced event search and room finding (#679)
- **drive**: `+add-comment` supports slides targets (#674)
- Risk tiering for operations (#633)

### v1.0.20 (2026-04-27)
- **drive**: `+search` shortcut with flat filter flags (#658)
- **im**: `at-chatter-ids` filter in `+messages-search` (#612)
- **mail**: Share emails to IM chats (#637)
- **calendar**: Update shortcut (#678)
- Pagination state preservation on truncation (#659)

### v1.0.19 (2026-04-24)
- **doc v2 API**: `docs +create`, `+fetch`, `+update` now support v2 API (#638)
- **mail**: Read receipt support (#639)
- **drive**: Wiki node targets in `+upload` (#611)
- **im**: Request thread roots for chat message list (#635)
- Content-safety scanning (#606)

### v1.0.18 (2026-04-23)
- **config**: `config bind` for per-Agent credential isolation (#515)
- **doc**: `--from-clipboard` flag in `+media-insert` (#508)
- **slides**: `+replace-slide` shortcut for block-level XML edits (#516)
- **wiki**: `+delete-space` shortcut with async task polling (#610)
- **base**: `.base` import and export for bitable (#599)
- SHA-256 checksum verification on install (#592)

### v1.0.17 (2026-04-22)
- **drive**: `+apply-permission` to request doc access (#588)
- **im**: Content-Disposition filename for message resource downloads (#536)
- Whiteboard image support

### v1.0.16 (2026-04-21)
- **doc**: `--selection-with-ellipsis` position flag in `+media-insert` (#335)
- **doc**: Pre-write semantic warnings in `docs +update` (#569)
- **mail**: Draft preview URL (#438), large email attachments (#537)

### v1.0.15 (2026-04-20)
- Auth sidecar proxy (#532)
- **sheets**: Float image shortcuts (#494)
- **base**: Preserve attachment metadata on uploads (#563)

### Most Impactful New Features for Competition

1. **Event subscription system** (#654) -- enables real-time sync workflows instead of polling
2. **Drive +pull/+push/+status** (#692,#696,#709) -- file sync is now a first-class operation
3. **@file params** (#724) -- batch operations via JSON files
4. **Doc v2 API** (#638) -- modern document operations
5. **SKILL docs** (#704) -- confirms official Skill documentation approach is correct direction
6. **Base markdown output** (#726) -- richer data presentation

## References

- Official repo: https://github.com/larksuite/cli
- Releases: https://github.com/larksuite/cli/releases
- Existing skills: https://github.com/larksuite/cli/tree/main/skills
- API docs: https://open.feishu.cn/
- Customer cases: https://www.feishu.cn/customers
- Industry solutions: https://www.feishu.cn/industry_solutions/
- Tavily API: https://docs.tavily.com
