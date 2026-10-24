#!/usr/bin/env python3
"""检查每部番的最新集数，写入 docs/data/status.json。

只用标准库。用法：python scripts/check.py [shows.json] [status.json]
"""
import datetime as dt
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 用普通浏览器 UA，ikanbot 的 Cloudflare 会拦自定义 UA
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")


def fetch_json(url):
    origin = "/".join(url.split("/")[:3])
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json", "Referer": origin + "/",
        "X-Requested-With": "XMLHttpRequest"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_text(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def _num(s):
    """从 '12' / '第12话' / '12.5' 里取集数，取不到返回 None。"""
    m = re.search(r"\d+(?:\.\d+)?", str(s or ""))
    if not m:
        return None
    n = float(m.group())
    return int(n) if n.is_integer() else n


# ---------- 来源适配器：都返回 {"latest": 集数, "url": 最新集链接, "page": 番剧页面} ----------

def src_bilibili(cfg, fetch=fetch_json):
    url = cfg.get("url", "")
    m = re.search(r"(ss|ep|md)(\d+)", url)
    if not m:
        raise ValueError(f"B站链接里找不到 ss/ep/md 编号: {url}")
    kind, num = m.groups()
    if kind == "md":
        info = fetch(f"https://api.bilibili.com/pgc/review/user?media_id={num}")
        num, kind = str(info["result"]["media"]["season_id"]), "ss"
    param = "season_id" if kind == "ss" else "ep_id"
    data = fetch(f"https://api.bilibili.com/pgc/view/web/season?{param}={num}")
    if data.get("code") != 0:
        raise RuntimeError(f"B站接口返回错误: {data.get('message')}")
    res = data["result"]
    # 只算正片（episodes），PV/特典在 section 里，不算
    eps = res.get("episodes") or []
    latest, ep_url = None, None
    for ep in eps:
        n = _num(ep.get("title"))
        if n is not None and (latest is None or n >= latest):
            latest = n
            ep_url = ep.get("share_url") or f"https://www.bilibili.com/bangumi/play/ep{ep.get('ep_id') or ep.get('id')}"
    if latest is None:
        latest = _num((res.get("new_ep") or {}).get("title"))
    page = res.get("link") or f"https://www.bilibili.com/bangumi/play/ss{res.get('season_id')}"
    return {"latest": latest, "url": ep_url or page, "page": page,
            "status": (res.get("new_ep") or {}).get("desc")}


def src_bangumi(cfg, fetch=fetch_json, today=None):
    sid = cfg.get("id") or _num(re.search(r"subject/(\d+)", cfg.get("url", "")).group(1))
    today = today or dt.date.today().isoformat()
    latest, ep_url, offset = None, None, 0
    while True:
        data = fetch(f"https://api.bgm.tv/v0/episodes?subject_id={sid}&type=0&limit=100&offset={offset}")
        items = data.get("data") or []
        for ep in items:
            air = ep.get("airdate") or ""
            if not air or air > today:
                continue
            n = ep.get("ep") or ep.get("sort")
            if n is not None and (latest is None or n >= latest):
                latest = int(n) if float(n).is_integer() else n
                ep_url = f"https://bgm.tv/ep/{ep['id']}"
        offset += len(items)
        if not items or offset >= data.get("total", 0):
            break
    page = f"https://bgm.tv/subject/{sid}"
    return {"latest": latest, "url": ep_url or page, "page": page}


def src_regex(cfg, fetch=fetch_text):
    """通用：抓 url 页面，用 pattern 匹配所有集数，取最大。
    pattern 里第一个捕获组是集数；可选 link 模板，{n} 替换成集数。"""
    html = fetch(cfg["url"])
    nums = [_num(m) for m in re.findall(cfg["pattern"], html)]
    nums = [n for n in nums if n is not None]
    latest = max(nums) if nums else None
    link = cfg.get("link")
    ep_url = link.replace("{n}", str(latest)) if (link and latest is not None) else cfg["url"]
    return {"latest": latest, "url": ep_url, "page": cfg["url"]}


def src_huaren(cfg, fetch=fetch_text):
    """huaren.live（MacCMS 站）：详情页里有每条线路的分集链接 /vodplay/{id}-{线路}-{序号}.html。"""
    vid = cfg.get("id") or re.search(r"/vod(?:detail|play)/(\d+)", cfg.get("url", "")).group(1)
    base = cfg.get("base", "https://huaren.live")
    page = f"{base}/voddetail/{vid}.html"
    html = fetch(page)
    best = None  # (集数, 链接)
    for href, text in re.findall(rf'href="(/vodplay/{vid}-\d+-\d+\.html)"[^>]*>([^<]*)<', html):
        n = _num(text)
        if n is not None and (best is None or n > best[0]):
            best = (n, base + href)
    if best is None:
        raise ValueError("详情页里没找到分集链接")
    return {"latest": best[0], "url": best[1], "page": page}


def ikanbot_token(current_id, e_token):
    """照抄 ikanbot 播放页里的 get_tks()：取 id 末 4 位，每位决定从 e_token 截哪 8 个字符。"""
    out = []
    for ch in str(current_id)[-4:]:
        s = int(ch) % 3 + 1
        out.append(e_token[s:s + 8])
        e_token = e_token[s + 8:]
    return "".join(out)


def _ikanbot_play(pid, fetch_t, fetch_j):
    page = f"https://www.ikanbot.com/play/{pid}"
    html = fetch_t(page)
    e_token = re.search(r'id="e_token" value="([^"]*)"', html).group(1)
    m = re.search(r'id="mtype" value="([^"]*)"', html)
    mtype = m.group(1) if m else "2"
    data = fetch_j(f"https://www.ikanbot.com/api/getResN?videoId={pid}&mtype={mtype}"
                   f"&token={ikanbot_token(pid, e_token)}")
    if data.get("state") != 1:
        raise RuntimeError(f"ikanbot 接口返回 state={data.get('state')}")
    latest = None
    for line in data["data"]["list"]:
        for item in (line.get("url") or "").split("#"):
            n = _num(item.split("$")[0])
            if n is not None and (latest is None or n > latest):
                latest = n
    return {"latest": latest, "url": page, "page": page}


def src_ikanbot(cfg, fetch_t=fetch_text, fetch_j=fetch_json):
    """ikanbot.com：同名条目常有好几个，搜索后挨个查，取集数最多的那个。
    可直接给 id（/play/ 后的数字），或给 q（搜索词）+ 可选 year。"""
    if cfg.get("id"):
        return _ikanbot_play(cfg["id"], fetch_t, fetch_j)
    q = cfg["q"]
    html = fetch_t("https://www.ikanbot.com/search?q=" + urllib.parse.quote(q))
    cands = []
    for pid, title in re.findall(r'href="/play/(\d+)" class="title-text">([^<]*)<', html):
        parts = title.split()
        year = parts[-1] if parts and re.fullmatch(r"\d{4}", parts[-1]) else ""
        name = " ".join(parts[:-1] if year else parts)
        if name == q and (not cfg.get("year") or year == str(cfg["year"])):
            cands.append(pid)
    best, errors = None, []
    for pid in cands[:cfg.get("max_candidates", 4)]:
        try:
            r = _ikanbot_play(pid, fetch_t, fetch_j)
        except Exception as e:
            errors.append(f"{pid}: {e}")
            continue
        if r["latest"] is not None and (best is None or r["latest"] > best["latest"]):
            best = r
    if best is None:
        title = re.search(r"<title>([^<]*)", html)
        raise ValueError(f"搜索「{q}」没找到可用条目（候选 {len(cands)} 个，页面「{title and title.group(1)}」）{errors[:2]}")
    return best


SOURCES = {"huaren": src_huaren, "ikanbot": src_ikanbot,
           "bilibili": src_bilibili, "bangumi": src_bangumi, "regex": src_regex}


def check_source(cfg):
    if not cfg:
        return None
    t = cfg.get("type")
    try:
        out = SOURCES[t](cfg)
        out["ok"] = True
    except Exception as e:  # 单个来源失败不影响其他番
        out = {"ok": False, "error": f"{type(e).__name__}: {e}", "page": cfg.get("url")}
    out["type"] = t
    return out


def run(shows_path, status_path, check=check_source, now=None):
    shows = json.loads(Path(shows_path).read_text("utf-8"))["shows"]
    old = {}
    if Path(status_path).exists():
        old = {s["name"]: s for s in json.loads(Path(status_path).read_text("utf-8")).get("shows", [])}
    now = now or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    result = []
    for show in shows:
        prev = old.get(show["name"], {})
        p, s = check(show.get("primary")), check(show.get("secondary"))
        # 某个来源这次失败了，就沿用上次成功的结果，避免页面闪回 0
        for key, cur in (("primary", p), ("secondary", s)):
            if cur and not cur["ok"] and (prev.get(key) or {}).get("ok"):
                cur.update({k: v for k, v in prev[key].items() if k not in ("ok", "error")})
                cur["stale"] = True
        candidates = [x["latest"] for x in (p, s) if x and x.get("latest") is not None]
        latest = max(candidates) if candidates else prev.get("latest")
        updated_at = prev.get("updated_at")
        if latest is not None and latest != prev.get("latest"):
            updated_at = now
        result.append({
            "name": show["name"],
            "watched": show.get("watched", 0),
            "day": show.get("day"),
            "latest": latest,
            "updated_at": updated_at,
            "primary": p,
            "secondary": s,
        })

    Path(status_path).parent.mkdir(parents=True, exist_ok=True)
    Path(status_path).write_text(
        json.dumps({"checked_at": now, "shows": result}, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return result


if __name__ == "__main__":
    shows = sys.argv[1] if len(sys.argv) > 1 else ROOT / "shows.json"
    status = sys.argv[2] if len(sys.argv) > 2 else ROOT / "docs" / "data" / "status.json"
    for r in run(shows, status):
        errs = [f"{k}: {r[k]['error']}" for k in ("primary", "secondary") if r[k] and not r[k]["ok"]]
        print(f"{r['name']}: 最新 {r['latest']}，看到 {r['watched']}" + (f"  [{'; '.join(errs)}]" if errs else ""))
