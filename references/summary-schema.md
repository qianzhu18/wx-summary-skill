# Summary JSON Schema

`summary.json` is the human-reviewed content file for `webpage` mode.

## Shape

```json
{
  "group_name": "IGN AI | 洋来",
  "group_id": "43663749608@chatroom",
  "time_range": "2026-05-11 ~ 2026-05-17",
  "headline": "范围标题",
  "subheadline": "一句更具体的副标题",
  "opening": "2-4 句总述",
  "period_in_one_line": "一句话看这段时间",
  "main_threads": [
    {
      "title": "主题标题",
      "summary": "1 段解释"
    }
  ],
  "people": [
    {
      "name": "张三",
      "tag": "42 条 / 高频答疑",
      "desc": "本次观察"
    }
  ],
  "timeline": [
    {
      "date": "05-14",
      "label": "周四",
      "bullets": [
        "发生了什么",
        "又发生了什么"
      ]
    }
  ],
  "quotes": [
    {
      "text": "原话",
      "who": "说话人"
    }
  ],
  "links": [
    {
      "title": "值得记住的资源或工具",
      "note": "为什么它重要"
    }
  ],
  "next_actions": [
    "适合继续跟进的动作 1",
    "适合继续跟进的动作 2"
  ]
}
```

## Field notes

- `headline`
  The first-screen signal. Keep it short and concrete.
- `subheadline`
  Explain what the selected range was really about.
- `opening`
  This is the editorial entry for a reader who did not read the chat.
- `period_in_one_line`
  A compact judgment for the chosen range.
- `main_threads`
  Usually 4-6 items is enough.
- `people`
  Use observed roles, not praise.
- `timeline`
  Reflect the actual rhythm across the selected dates.
- `quotes`
  Keep them short, precise, and attributable.
- `links`
  Good for tools, posts, repos, docs, or events that explain the group's center of gravity.
- `next_actions`
  Optional, but useful when the group is action-oriented.

## Writing rules

- Do not invent outcomes the messages do not support.
- If the selected range is fragmented, say it is fragmented.
- If the group was mostly resource sharing, say that plainly.
- Keep this JSON aligned with `analysis.json`, not with wishful narrative.
