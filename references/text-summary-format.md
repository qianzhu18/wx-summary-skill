# Text Summary Format

Use this format for `text` mode.

The goal is not a fluffy recap. It should help the reader quickly understand what mattered in the group and what is worth acting on for personal growth.

## Required structure

Write the markdown output in this order:

```markdown
# <群名> 群聊摘要

- 时间范围：<YYYY-MM-DD ~ YYYY-MM-DD>
- 消息总量：<count>
- 活跃人数：<count>
- 高峰日期：<date / count>
- 高峰时段：<hour / count>

## 群聊总结

## 热点

## 需求与链接人

## 资源

## 活跃之星

## 词云
```

## Section rules

### 群聊总结

- 2-4 short paragraphs
- Explain what the selected range was really about
- Mention the emotional / workflow texture of the group
- Keep it grounded in actual messages and data
- Make it useful for personal growth, but do not turn it into generic motivational writing

### 热点

List 3-8 hotspots.

Each hotspot should include:

- `关键词`
- `提及次数`
- `核心内容`
- `关键观点`
- `原话引用`

Rules:

- Group similar messages into one hotspot instead of repeating them
- Prioritize recurring themes over isolated chatter
- If a participant acted like a KOL in that topic, name them and summarize their view clearly
- Quotes must be real and attributable

Suggested shape:

```markdown
### 1. 关键词（12 次）
- 核心内容：
- 关键观点：
  - 张三：
  - 李四：
- 原话：
  > "..."
  > "..."
```

### 需求与链接人

Extract concrete needs behind people's messages, especially:

- resource requests
- how-to questions
- troubleshooting asks
- partner / connector asks

For each item include:

- `需求`
- `提出人`
- `链接人 / 响应者`
- `证据`
- `当前状态`

Rules:

- Distinguish explicit asks from your inference
- If nobody responded, say so plainly
- If a need was solved via a link, tool, or person, make that chain explicit

### 资源

List real resources that appeared in the chat:

- articles
- repos
- products
- documents
- tools
- event links

For each item include:

- `名称`
- `谁发的`
- `用途`
- `链接`

Never invent URLs. If the chat includes a title but not a URL, say `链接未在当前范围内保留`.

### 活跃之星

Use actual message counts and short observed roles.

Suggested shape:

```markdown
1. 张三（42 条）- 本周像群里的排障台
2. 李四（31 条）- 高频分享资源并接问题
```

Keep it observational, not flattering.

### 词云

List 15-30 high-frequency terms or phrases, ordered roughly by importance.

Rules:

- Prefer semantically meaningful phrases over single filler words
- Remove generic stop words
- Keep tool names, product names, event names, and repeated workflow words

Suggested shape:

```markdown
AI Agent / Codex / Claude Code / 工作流 / 中转站 / Token / 活动 / 远控 / Obsidian / ...
```

## Evidence discipline

- Use real names.
- Use accurate counts from `analysis.json`.
- Open raw messages if a quote, need, or link attribution is uncertain.
- Mark inference with wording like `推测` or `更像是在表达`.
- Do not overstate consensus.
