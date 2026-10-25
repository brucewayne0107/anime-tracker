# 噜妹追番

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


## 电影与美剧目录

根目录 `catalog.json` 的 `tabs` 包含 `us`（美剧）、`douban`、`oscar`、`nolan`。电影条目填写 `title`、`original`、`year`；豆瓣加 `rank`，奥斯卡加 `ceremony` 和 `award_year`（页面按届数倒序）。美剧填写 `title`、`original`、`seasons`、`start`、`end`，每季分别解析，第一季匹配 `start` 年份，其余季限制在 `start`–`end` 范围内，不推算具体季年份。

```sh
python3 scripts/catalog.py          # 保留已找到的来源，只补缺失
python3 scripts/catalog.py --refresh # 强制重新搜索
```

输出为 `docs/data/catalog.json`，封面下载到 `docs/covers/`；主来源图片下载失败时尝试另一个来源的封面。请求至少间隔 0.55 秒，单个来源失败不影响其他条目；最后按 tab 打印找到/缺失统计（美剧按季计）。电影使用年份严格消歧，中文名未匹配时再搜别名和 `original`；可用 `"aliases": ["其他译名"]` 补充地区译名。手动指定 `"huaren": 123`、`"ikanbot": 456`、`"cover": "https://…"` 优先于搜索；美剧可用 `"huaren": {"1": 123, "2": 456}` 为每季指定，单个 ID 或封面只应用于第一季。缓存记录来源 ID；修改名称、原名、年份、季号或手动 ID 后会重新解析对应内容。未找到时页面提供华人搜索链接。

push 涉及 `catalog.json` 时 Actions 会解析并提交生成结果；原来的每三小时番剧检查不变。macOS 若 Python 报证书错误，可使用系统 CA：`SSL_CERT_FILE=/etc/ssl/cert.pem python3 scripts/catalog.py`。

## 吉祥物图片

新增噜噜噜妹图片放进 `docs/lulu/`，在 `docs/lulu/list.json` 里加上文件名；每次打开页面从中随机选一张做头像。

