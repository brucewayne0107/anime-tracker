#!/usr/bin/env python3
"""新增 / 删除番剧，自动去 huaren 和 ikanbot 找条目，写回 shows.json。

用法：
  python scripts/add.py 仙逆 7          # 新增（或改周几），7=周日
  python scripts/add.py --remove 仙逆
  python scripts/add.py --issue "新增 仙逆 周日"   # GitHub issue 标题，Actions 里用
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402

SHOWS = check.ROOT / "shows.json"
DAY = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}


def parse_day(text):
    if not text:
        return None
    text = text.strip()
    if text.isdigit() and 1 <= int(text) <= 7:
        return int(text)
    m = re.fullmatch(r"(?:周|星期|礼拜)([一二三四五六日天])", text)
    return DAY[m.group(1)] if m else None


def parse_issue(title):
    """'新增 仙逆 周日' / '新增：仙逆 7' / '删除 仙逆' → (动作, 番名, 周几)"""
    m = re.fullmatch(r"\s*(新增|添加|加|删除|删)\s*[:：]?\s*(.+?)"
                     r"(?:\s+((?:周|星期|礼拜)[一二三四五六日天]|[1-7]))?\s*", title)
    if not m:
        raise ValueError(f"看不懂标题「{title}」，格式：新增 番名 周几 / 删除 番名")
    action = "remove" if m.group(1).startswith("删") else "add"
    return action, m.group(2).strip(), parse_day(m.group(3))


def resolve(name):
    """搜两个网站，返回 (primary, secondary, 说明)。"""
    notes = []
    results = check.huaren_search(name)
    vid = check.huaren_pick(name, results)
    title = next((t for v, t, _ in results if v == vid), name)
    if vid:
        primary = {"type": "huaren", "id": int(vid)}
        notes.append(f"华人直播：{title} https://huaren.live/voddetail/{vid}.html")
    else:
        primary = {"type": "huaren", "q": name}
        notes.append("华人直播：没搜到，先按番名搜索，之后可手动在 shows.json 填 id")
    secondary = {"type": "ikanbot", "q": name}
    if title != name:
        secondary["title"] = title
    try:
        r = check.src_ikanbot(secondary)
        notes.append(f"爱看机器人：第 {r['latest']} 集 {r['url']}")
    except Exception as e:
        notes.append(f"爱看机器人：没找到（{e}）")
    return primary, secondary, notes


def main(argv):
    if argv[:1] == ["--issue"]:
        action, name, day = parse_issue(" ".join(argv[1:]))
    elif argv[:1] == ["--remove"]:
        action, name, day = "remove", " ".join(argv[1:]).strip(), None
    else:
        action, name, day = "add", argv[0], parse_day(argv[1] if len(argv) > 1 else None)

    data = json.loads(SHOWS.read_text("utf-8"))
    shows = data["shows"]
    existing = next((s for s in shows if s["name"] == name), None)
    lines = []

    if action == "remove":
        if not existing:
            raise SystemExit(f"列表里没有「{name}」")
        shows.remove(existing)
        lines.append(f"已删除「{name}」")
    elif existing:
        existing["day"] = day
        lines.append(f"「{name}」已在列表里，更新为{('周' + '一二三四五六日'[day - 1]) if day else '未定'}")
    else:
        primary, secondary, notes = resolve(name)
        shows.append({"name": name, "day": day, "watched": 0, "primary": primary, "secondary": secondary})
        lines.append(f"已新增「{name}」，{('每周' + '一二三四五六日'[day - 1]) if day else '周几未定'}")
        lines += ["- " + n for n in notes]

    SHOWS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1:])
