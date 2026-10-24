import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check  # noqa: E402

BILI = {
    "code": 0,
    "result": {
        "season_id": 46244, "link": "https://www.bilibili.com/bangumi/media/md123",
        "new_ep": {"title": "12", "desc": "更新至第12话"},
        "episodes": [
            {"title": "1", "ep_id": 1001, "share_url": "https://www.bilibili.com/bangumi/play/ep1001"},
            {"title": "12", "ep_id": 1012, "share_url": "https://www.bilibili.com/bangumi/play/ep1012"},
            {"title": "11", "ep_id": 1011, "share_url": "https://www.bilibili.com/bangumi/play/ep1011"},
        ],
    },
}

BGM = {"total": 3, "data": [
    {"id": 1, "ep": 1, "sort": 1, "airdate": "2026-10-01"},
    {"id": 2, "ep": 2, "sort": 2, "airdate": "2026-10-08"},
    {"id": 3, "ep": 3, "sort": 3, "airdate": "2026-10-30"},  # 还没播
]}


class SourceTests(unittest.TestCase):
    def test_bilibili_picks_highest_episode(self):
        urls = []
        out = check.src_bilibili({"url": "https://www.bilibili.com/bangumi/play/ss46244"},
                                 fetch=lambda u: urls.append(u) or BILI)
        self.assertIn("season_id=46244", urls[0])
        self.assertEqual(out["latest"], 12)
        self.assertEqual(out["url"], "https://www.bilibili.com/bangumi/play/ep1012")

    def test_bilibili_ep_link(self):
        urls = []
        check.src_bilibili({"url": "https://www.bilibili.com/bangumi/play/ep1001"},
                           fetch=lambda u: urls.append(u) or BILI)
        self.assertIn("ep_id=1001", urls[0])

    def test_bangumi_skips_unaired(self):
        out = check.src_bangumi({"id": 400602}, fetch=lambda u: BGM, today="2026-10-24")
        self.assertEqual(out["latest"], 2)
        self.assertEqual(out["url"], "https://bgm.tv/ep/2")

    def test_regex(self):
        html = '<a href="/v/1">第1集</a><a href="/v/9">第9集</a><a>第10集</a>'
        out = check.src_regex({"url": "https://x", "pattern": r"第(\d+)集", "link": "https://x/v/{n}"},
                              fetch=lambda u: html)
        self.assertEqual(out["latest"], 10)
        self.assertEqual(out["url"], "https://x/v/10")


class RunTests(unittest.TestCase):
    def test_failure_keeps_previous_and_updated_at(self):
        d = Path(tempfile.mkdtemp())
        shows, status = d / "shows.json", d / "status.json"
        shows.write_text(json.dumps({"shows": [{"name": "A", "watched": 3,
                                                "primary": {"type": "x"}, "secondary": {"type": "y"}}]}))
        ok = lambda cfg: {"ok": True, "type": cfg["type"], "latest": 5, "url": "u"}
        check.run(shows, status, check=ok, now="T1")
        r = json.loads(status.read_text())["shows"][0]
        self.assertEqual((r["latest"], r["updated_at"], r["watched"]), (5, "T1", 3))

        # 没新集：updated_at 不变
        check.run(shows, status, check=ok, now="T2")
        self.assertEqual(json.loads(status.read_text())["shows"][0]["updated_at"], "T1")

        # 两个来源都失败：沿用上次结果
        bad = lambda cfg: {"ok": False, "type": cfg["type"], "error": "boom"}
        check.run(shows, status, check=bad, now="T3")
        r = json.loads(status.read_text())["shows"][0]
        self.assertEqual(r["latest"], 5)
        self.assertTrue(r["primary"]["stale"])


if __name__ == "__main__":
    unittest.main()
