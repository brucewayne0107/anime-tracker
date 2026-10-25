# 嘟妹追番

一个静态网页 + 定时脚本：每部番显示「看到第几集 / 最新第几集」，点名字跳到最新一集。

- 网页：`docs/index.html`，用 GitHub Pages 托管
- 检查脚本：`scripts/check.py`（只用 Python 标准库），GitHub Actions 每 3 小时跑一次，把结果写到 `docs/data/status.json`
- 番剧列表：`shows.json`

## 第一次设置

1. 仓库 Settings → Pages → Build and deployment → Source 选 **GitHub Actions**
2. Actions 页面手动运行一次「检查番剧更新」
3. 打开 `https://<你的用户名>.github.io/<仓库名>/`

## 加一部番（最简单）

在网页右上角点「＋ 新增」，填番名、选周几，跳到 GitHub 后点「Submit new issue」。
大约 1 分钟后 Actions 自动去两个网站找到条目，写进 `shows.json`，在 issue 里回复找到了什么并关掉它，网页也跟着更新。
删除：新开一个标题为「删除 番名」的 issue。改周几：再「新增 番名 周X」一次。

也可以本地运行：`python scripts/add.py 凡人修仙传 3`、`python scripts/add.py --remove 凡人修仙传`。

自动找错了条目的话，在 `shows.json` 里改 id 就行（网页底部有「编辑列表」链接）。

## 手动编辑 shows.json

每部番一条：

```json
{
  "name": "番名",
  "day": 7,
  "primary":   { "type": "huaren", "id": 109 },
  "secondary": { "type": "ikanbot", "q": "仙逆", "year": 2023 }
}
```

`day` 是周几更新（1=周一 … 7=周日），页面按它分组；可选 `time` 写几点更新（如 `"10:00"`），同一天按时间排。`day` / `time` 都按**北京时间**填，网页会换算成看网页那台设备的时区。可选 `note` 写备注（含「完结」「停播」的会变灰）。卡片背景默认用来源页的封面（自动下载到 `docs/covers/`），想换图就加 `"cover": "图片链接"`。

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

新加的番默认「已经看到加入时的最新一集」，之后出的新集才显示 +N。
在网页上点 + / −，或者直接点数字输入，保存在当前浏览器。也可以在 `shows.json` 里写 `watched` 指定初始值；换设备时点页面底部「复制进度」，把数字填回 `shows.json`。

备注里写了「完结」「停播」「停更」的番会放进「停更」tab。

### 多设备同步

点网页右上角 ☁️，按提示新建一个 GitHub fine-grained token（只给这个仓库，Contents 读写），粘贴保存。
之后看到第几集会存进仓库根目录的 `progress.json`，每台设备填一次 token 就能同步；不填 token 也能读到已同步的进度，只是改了不会上传。

## 本地运行

```
python scripts/check.py
python -m unittest discover -s tests
```
