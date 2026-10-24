#!/usr/bin/env python3
"""检查每部番的最新集数，写入 docs/data/status.json。

只用标准库。用法：python scripts/check.py [shows.json] [status.json]
"""
import datetime as dt
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (anime-tracker; +https://github.com)"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
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


SOURCES = {"bilibili": src_bilibili, "bangumi": src_bangumi, "regex": src_regex}


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
