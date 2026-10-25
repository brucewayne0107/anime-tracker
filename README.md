# 追番进度

一个静态网页 + 定时脚本：每部番显示「看到第几集 / 最新第几集」，点名字跳到最新一集。

- 网页：`docs/index.html`，用 GitHub Pages 托管
- 检查脚本：`scripts/check.py`（只用 Python 标准库），GitHub Actions 每 3 小时跑一次，把结果写到 `docs/data/status.json`
- 番剧列表：`shows.json`

## 第一次设置

1. 仓库 Settings → Pages → Build and deployment → Source 选 **GitHub Actions**
2. Actions 页面手动运行一次「检查番剧更新」
3. 打开 `https://<你的用户名>.github.io/<仓库名>/`

## 加一部番

编辑 `shows.json`，加一条：

```json
{
  "name": "番名",
  "day": 7,
  "watched": 0,
  "primary":   { "type": "huaren", "id": 109 },
  "secondary": { "type": "ikanbot", "q": "仙逆", "year": 2023 }
}
```

`day` 是周几更新（1=周一 … 7=周日），页面按它分组。可选 `note` 写备注（含「完结」「停播」的会变灰）。

提交后会自动检查一次。

### 来源类型

| type | 需要填 | 说明 |
|---|---|---|
| `huaren` | `id`：huaren.live/voddetail/后面的数字 | 跳转链接是最新一集的播放页 |
| `ikanbot` | `q`：搜索词，可选 `year`；或直接给 `id`（/play/ 后的数字） | 同名条目会挨个查，取集数最多的；跳转到播放页 |
| `bilibili` | `url`：番剧页链接，含 `ss…`、`ep…` 或 `md…` 都行 | 跳转链接直接是最新一集的播放页 |
| `bangumi` | `id`：bgm.tv/subject/后面的数字（或填 `url`） | 只算已经播出的集 |
| `regex` | `url`、`pattern`（第一个括号是集数），可选 `link`（`{n}` 换成集数） | 适配其他网站，例：`"pattern": "第(\\d+)集"` |

最新集数取主次来源里较大的一个。某个来源这次检查失败，会沿用上次的结果，页面上标「检查失败」。

## 看到第几集

在网页上点 + / − 记录。每个链接旁有「复制」按钮，保存在当前浏览器。`shows.json` 里的 `watched` 是初始值；换设备时点页面底部「复制进度」，把数字填回 `shows.json`。

## 本地运行

```
python scripts/check.py
python -m unittest discover -s tests
```
