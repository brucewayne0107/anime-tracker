import json
import re
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


class HuarenIkanbotTests(unittest.TestCase):
    def test_huaren_latest_from_link_text(self):
        html = ('<a href="/vodplay/109-1-1.html">01</a><a href="/vodplay/109-1-125.html">虚天战纪</a>'
                '<a href="/vodplay/109-1-164.html">163</a><a href="/vodplay/109-2-163.html">162</a>')
        out = check.src_huaren({"id": 109}, fetch=lambda u: html)
        self.assertEqual(out["latest"], 163)
        self.assertEqual(out["url"], "https://huaren.live/vodplay/109-1-164.html")

    def test_huaren_pick_skips_movies_and_spinoffs(self):
        res = [("24161", "星辰变第三季", "12集全"), ("197856", "星辰变第七季", "12集全"),
               ("138558", "牧神记之延康变法", "全61集"), ("91978", "牧神记", "105"),
               ("130850", "海贼王：狂热行动", "正片"), ("108", "海贼王", "1180")]
        self.assertEqual(check.huaren_pick("星辰变", res), "197856")
        self.assertEqual(check.huaren_pick("牧神记", res), "91978")
        self.assertEqual(check.huaren_pick("海贼王", res), "108")

    def test_ikanbot_token(self):
        self.assertEqual(check.ikanbot_token("978607", "ja4503464f8oa06b6883z963697c3ux341dbb44"),
                         "503464f8a06b6883963697c3341dbb44")

    def test_ikanbot_parses_resdata_and_picks_best(self):
        search = ('<a href="/play/1" class="title-text">仙逆  2023</a>'
                  '<a href="/play/2" class="title-text">仙逆  1986</a>'
                  '<a href="/play/3" class="title-text">仙逆彩蛋  2026</a>')
        page = '<input id="e_token" value="ja4503464f8oa06b6883z963697c3ux341dbb44"/><input id="mtype" value="2"/>'
        eps = {"1": "第01集$a.m3u8#第163集$b.m3u8#预告$c.m3u8", "2": "第01集$a.m3u8"}

        def fj(u):
            pid = re.search(r"videoId=(\d+)", u).group(1)
            return {"state": 1, "data": {"list": [{"resData": json.dumps([{"url": eps[pid]}])}]}}
        out = check.src_ikanbot({"q": "仙逆"}, fetch_t=lambda u: search if "search" in u else page, fetch_j=fj)
        self.assertEqual(out["latest"], 163)
        self.assertEqual(out["url"], "https://www.ikanbot.com/play/1")

    def test_ep_num(self):
        self.assertEqual([check._ep_num(x) for x in ["01", "第12集", "EP05", "2026-10-25", "预告"]],
                         [1, 12, 5, None, None])


class AddTests(unittest.TestCase):
    def test_parse_issue(self):
        import add
        self.assertEqual(add.parse_issue("新增 仙逆 周日"), ("add", "仙逆", 7))
        self.assertEqual(add.parse_issue("新增：一念永恒 3"), ("add", "一念永恒", 3))
        self.assertEqual(add.parse_issue("删除 仙逆"), ("remove", "仙逆", None))
        self.assertEqual(add.parse_issue("新增 灵笼 第二季 周六"), ("add", "灵笼 第二季", 6))
        with self.assertRaises(ValueError):
            add.parse_issue("随便写写")


if __name__ == "__main__":
    unittest.main()
