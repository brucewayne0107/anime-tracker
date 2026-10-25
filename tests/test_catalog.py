import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import catalog


def search_page(site, rows):
    if site == 'huaren':
        return ''.join(f'<div class="public-list-exp"><div class="thumb-txt"><a href="/voddetail/{pid}.html">{title}</a></div><a href="/vodsearch/year/{year}.html">{year}</a></div>' for pid,title,year in rows)
    return ''.join(f'<a href="/play/{pid}" class="title-text">{title}  {year}</a>' for pid,title,year in rows)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.network_patch = patch('urllib.request.urlopen', side_effect=AssertionError('Tests must not access network'))
        self.network = self.network_patch.start()

    def tearDown(self):
        try:
            self.network.assert_not_called()
        finally:
            self.network_patch.stop()

    def fake(self, rows):
        def fetch(url):
            if 'search' in url:
                return search_page('huaren' if 'huaren' in url else 'ikanbot', rows)
            return '<title>detail</title>'
        return fetch

    def test_season_matching(self):
        for title in ('老友记第一季', '老友记 第1季', '老友记 第一季'):
            self.assertTrue(catalog.matches(title, '老友记', 1))
        self.assertFalse(catalog.matches('老友记第十一季', '老友记', 1))
        self.assertFalse(catalog.matches('古宅老友记第一季', '老友记', 1))
        self.assertFalse(catalog.matches('西部世界', '西部世界', 1))
        result = catalog.resolve({'title':'老友记','season':5}, fetch=self.fake([('1','老友记 第一季',1994),('5','老友记第五季',1998)]))
        self.assertEqual([s['id'] for s in result['sources'].values()], ['5','5'])

    def test_year_disambiguation(self):
        result = catalog.resolve({'title':'小妇人','year':2019}, fetch=self.fake([('1','小妇人',1994),('2','小妇人',2019)]))
        self.assertEqual([s['id'] for s in result['sources'].values()], ['2','2'])
        result = catalog.resolve({'title':'小妇人','year':2020}, fetch=self.fake([('1','小妇人',1994)]))
        self.assertEqual(result['sources'], {})

    def test_manual_id_precedes_search_and_cache(self):
        urls = []
        def fetch(url):
            urls.append(url)
            self.assertNotIn('search', url)
            return ''
        item = {'title':'A','year':2000,'huaren':12,'ikanbot':34,'cover':'https://example.com/image.jpg'}
        result = catalog.resolve(item, fetch=fetch, saver=lambda u,d:'covers/manual.jpg')
        self.assertEqual(result['sources']['huaren']['id'], '12')
        self.assertEqual(result['cover'], 'covers/manual.jpg')
        item['huaren'] = 99
        result = catalog.resolve(item, result, fetch=fetch, saver=lambda u,d:'covers/manual.jpg')
        self.assertEqual(result['sources']['huaren']['id'], '99')
        self.assertEqual(len(urls), 3)

    def test_cache_skips_and_refresh_searches(self):
        item = {'title':'A','year':2000}
        fetch = self.fake([('1','A',2000)])
        old = catalog.resolve(item, fetch=fetch)
        def no_fetch(url):
            self.fail('Cached source fetched: ' + url)
        result = catalog.resolve(item, old, fetch=no_fetch)
        self.assertEqual(result['sources'], old['sources'])
        result = catalog.resolve(item, old, refresh=True, fetch=self.fake([('2','A',2000)]))
        self.assertEqual(result['sources']['huaren']['id'], '2')

    def test_original_fallback_and_failure_isolation(self):
        result = catalog.resolve({'title':'中文名','original':'Original','year':2001}, fetch=self.fake([('3','Original',2001)]))
        self.assertEqual(len(result['sources']), 2)
        def partial(url):
            if 'huaren' in url:
                raise OSError('offline')
            return self.fake([('3','Original',2001)])(url)
        result = catalog.resolve({'title':'中文名','original':'Original','year':2001}, fetch=partial)
        self.assertIn('ikanbot', result['sources'])
        self.assertIn('huaren', result['errors'])

    def test_tv_manual_per_season_and_oscar_order(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d)/'catalog.json', Path(d)/'data/catalog.json'
            src.write_text(json.dumps({'tabs':[
                {'key':'us','name':'美剧','kind':'tv','items':[{'title':'A','seasons':2,'huaren':{'1':11,'2':22}}]},
                {'key':'oscar','name':'奥斯卡','kind':'movie','items':[{'title':'B','year':2000,'ceremony':1},{'title':'C','year':2001,'ceremony':2}]}]}))
            result = catalog.run(src,out,fetch=lambda u:'')
            seasons = result['tabs'][0]['items'][0]['season_items']
            self.assertEqual([s['sources']['huaren']['id'] for s in seasons],['11','22'])
            self.assertEqual([i['ceremony'] for i in result['tabs'][1]['items']],[2,1])

    def test_aliases_keep_season_constraint(self):
        result = catalog.resolve({'title':'绝望的主妇','original':'Desperate Housewives','season':2}, fetch=self.fake([('1','绝望主妇第一季',2004),('2','绝望主妇第二季',2005)]))
        self.assertEqual([s['id'] for s in result['sources'].values()],['2','2'])
        result = catalog.resolve({'title':'A','aliases':['Alternate'],'year':1999},fetch=self.fake([('3','Alternate',1999)]))
        self.assertEqual(len(result['sources']),2)

    def test_original_query_can_return_chinese_title(self):
        def fetch(url):
            if 'Original' in url:
                return search_page('huaren' if 'huaren' in url else 'ikanbot',[('7','中文名',2000)])
            return ''
        result=catalog.resolve({'title':'中文名','original':'Original','year':2000},fetch=fetch)
        self.assertEqual(len(result['sources']),2)

    def test_tv_rejects_same_name_older_adaptation(self):
        item={'title':'纸牌屋','season':2,'start':2013,'end':2018}
        result=catalog.resolve(item,fetch=self.fake([('1','纸牌屋第二季',1993),('2','纸牌屋第二季',2014)]))
        self.assertEqual([s['id'] for s in result['sources'].values()],['2','2'])
        self.assertFalse(catalog.year_matches({'year':2013},1990))

    def test_failed_primary_cover_uses_other_source(self):
        item={'title':'A','huaren':1,'ikanbot':2}
        def fetch(url):
            return '<meta property="og:image" content="https://img/' + ('bad.jpg' if 'huaren' in url else 'good.jpg') + '">'
        saved=[]
        def saver(url,docs):
            saved.append(url)
            return url if 'bad' in url else 'covers/good.jpg'
        result=catalog.resolve(item,fetch=fetch,saver=saver)
        self.assertEqual(result['cover'],'covers/good.jpg')
        self.assertEqual(len(saved),2)

    def test_legacy_douban_cover_keeps_image_id(self):
        urls=catalog.cover_variants('https://img3.doubanio.com/view/movie_poster_cover/lpst/public/p123.jpg')
        self.assertEqual(urls[-1],'https://img3.doubanio.com/view/photo/s_ratio_poster/public/p123.jpg')

    def test_alternate_cover_still_requires_same_year(self):
        sources={'ikanbot':{'id':'1','url':catalog.page_url('ikanbot','1')}}
        def fetch(url):
            if 'search' in url:
                return search_page('ikanbot',[('2','A',1999),('3','A',2000)])
            self.assertTrue(url.endswith('/3'))
            return '<meta property="og:image" content="https://img/good.jpg">'
        result=catalog.alternate_cover({'title':'A','year':2000},sources,fetch,lambda u,d:'covers/good.jpg',Path('.'),set())
        self.assertEqual(result,('covers/good.jpg','https://img/good.jpg'))
        self.assertTrue(sources['ikanbot']['cover_page'].endswith('/3'))

    def test_only_missing_source_is_searched(self):
        item = {'title':'A','year':2000}
        old = catalog.resolve(item, fetch=self.fake([('1','A',2000)]))
        del old['sources']['ikanbot']
        urls = []
        def fetch(url):
            urls.append(url)
            return self.fake([('2','A',2000)])(url)
        result = catalog.resolve(item, old, fetch=fetch)
        self.assertTrue(all('ikanbot' in u for u in urls))
        self.assertEqual(result['sources']['huaren']['id'], '1')
        self.assertEqual(result['sources']['ikanbot']['id'], '2')

    def test_interruption_preserves_future_cache(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d)/'input.json', Path(d)/'data/catalog.json'
            spec = {'tabs':[{'key':'us','kind':'tv','name':'美剧','items':[
                {'title':'A','seasons':2,'huaren':{'1':11,'2':22},'ikanbot':{'1':33,'2':44}},
                {'title':'B','seasons':1,'huaren':55,'ikanbot':66}]}]}
            src.write_text(json.dumps(spec))
            catalog.run(src,out,fetch=lambda u:'')
            calls = []
            def interrupted(url):
                calls.append(url)
                if len(calls) == 3:
                    raise KeyboardInterrupt()
                return ''
            with self.assertRaises(KeyboardInterrupt):
                catalog.run(src,out,refresh=True,fetch=interrupted)
            cached = json.loads(out.read_text())
            self.assertEqual(len(cached['tabs'][0]['items']),2)
            self.assertEqual(len(cached['tabs'][0]['items'][0]['season_items']),2)
            self.assertEqual(cached['tabs'][0]['items'][1]['season_items'][0]['sources']['huaren']['id'],'55')


if __name__ == '__main__':
    unittest.main()
