#!/usr/bin/env python3
"""Resolve catalog.json to docs/data/catalog.json. Standard library only."""
import argparse
import html
import json
import re
import time
import urllib.parse
from pathlib import Path
import check


def chinese(n):
    if n < 10:
        return '零一二三四五六七八九'[n]
    return ('十' if n < 20 else chinese(n // 10) + '十') + (chinese(n % 10) if n % 10 else '')


def normalize(s):
    s = html.unescape(s).casefold()
    for n in range(99, 0, -1):
        s = s.replace('第' + chinese(n) + '季', '第' + str(n) + '季')
    return re.sub(r'[\s·:：\-–—。！!，,（）()\[\]]', '', s)


# Common regional title variants; explicit input aliases can extend this list.
ALIASES = {
    '绝望的主妇': ['绝望主妇'], '老爸老妈的浪漫史': ['老爸老妈浪漫史'],
    '良相佐国': ['日月精忠'], '公寓春光': ['桃色公寓'],
    '八十天环游地球': ['环游世界八十天'], '马蒂': ['君子好逑'],
    '翡翠谷': ['青山翠谷'], '白夜追凶': ['失眠症'],
    '火战车': ['烈火战车'], '戏中之王': ['戏王之王'],
    '哈姆雷特': ['王子复仇记'], '随我而行': ['与我同行'],
    '壮志凌云': ['壮志千秋'], '百老汇的旋律': ['百老汇旋律'],
}


def names_for(item):
    return list(dict.fromkeys([item['title'], *item.get('aliases', []),
                              *ALIASES.get(item['title'], []), item.get('original')]))


def matches(title, wanted, season=None):
    a, b = normalize(title), normalize(wanted)
    if season is None:
        return a == b
    return a == b + f'第{season}季' or a == b + f'season{season}'


def year_matches(item, year):
    if item.get('year'):
        return year == item['year']
    if item.get('season') and item.get('start'):
        return year is not None and item['start'] <= year <= (item.get('end') or 9999)
    return True


class Client:
    """One rate limiter for HTML and cover requests; memoize successful HTML."""
    def __init__(self):
        self.last = 0
        self.cache = {}

    def wait(self):
        time.sleep(max(0, .55 - (time.monotonic() - self.last)))
        self.last = time.monotonic()

    def fetch(self, url):
        if url not in self.cache:
            self.wait()
            self.cache[url] = check.fetch_text(url)
        return self.cache[url]

    def cover(self, url, docs):
        self.wait()
        return check.save_cover(url, docs)


def candidates(site, query, fetch):
    if site == 'huaren':
        url = 'https://huaren.live/vodsearch/-------------.html?wd=' + urllib.parse.quote(query)
        body = fetch(url)
        rows = check.huaren_search(query, fetch=lambda _: body)
        out = []
        for block in body.split('class="public-list-exp"')[1:]:
            m = re.search(r'href="/voddetail/(\d+)\.html"', block)
            y = re.search(r'/vodsearch/year/(\d{4})', block)
            if m:
                row = next((r for r in rows if r[0] == m[1]), None)
                if row:
                    out.append((row[0], html.unescape(row[1]), int(y[1]) if y else None))
        return out
    body = fetch('https://www.ikanbot.com/search?q=' + urllib.parse.quote(query))
    out = []
    for pid, title in re.findall(r'href="/play/(\d+)" class="title-text">([^<]*)<', body):
        m = re.search(r'\s+(\d{4})\s*$', title)
        out.append((pid, html.unescape(title[:m.start()] if m else title).strip(), int(m[1]) if m else None))
    return out


def page_url(site, pid):
    return f'https://huaren.live/voddetail/{pid}.html' if site == 'huaren' else f'https://www.ikanbot.com/play/{pid}'


def cover_variants(url):
    urls = [html.unescape(url)]
    if re.match(r'https?://img\d+\.doubanio\.com/view/movie_poster_cover/', url):
        urls.append(re.sub(r'/view/movie_poster_cover/[^/]+/', '/view/photo/s_ratio_poster/', urls[0]))
    return urls


def alternate_cover(item, sources, fetch, saver, docs, attempted):
    """Try another exact title/year/season entry when a site's poster has expired."""
    seen = {s['url'] for s in sources.values()}
    for site, source in sources.items():
        for name in names_for(item):
            if not name:
                continue
            query = name + ('第' + chinese(item['season']) + '季' if item.get('season') and site == 'huaren' else '')
            try:
                rows = candidates(site, query, fetch)
            except Exception:
                continue
            for pid, title, year in rows:
                url = page_url(site, pid)
                if url in seen or not year_matches(item, year) or not any(matches(title, n, item.get('season')) for n in names_for(item) if n):
                    continue
                if len(seen) >= 10:
                    return None
                seen.add(url)
                try:
                    cover = check.og_image(fetch(url))
                except Exception:
                    continue
                if not cover:
                    continue
                for candidate in cover_variants(cover):
                    if candidate in attempted:
                        continue
                    attempted.add(candidate)
                    saved = saver(candidate, docs)
                    if not saved.startswith('http'):
                        source['cover'], source['cover_page'] = cover, url
                        return saved, candidate
    return None


def resolve(item, old=None, refresh=False, fetch=check.fetch_text, saver=check.save_cover, docs=check.ROOT / 'docs'):
    old = old or {}
    identity = {k: item.get(k) for k in ('title', 'original', 'year', 'season', 'aliases')}
    if {k: old.get('identity', {}).get(k) for k in identity} != identity:
        old = {}
    out = dict(item, identity=identity)
    out['sources'] = {}
    errors = {}
    for site in ('huaren', 'ikanbot'):
        manual = item.get(site)
        cached = old.get('sources', {}).get(site)
        valid_cached = cached and not (old.get(site) and not manual) and (manual or any(matches(cached.get('title', ''), name, item.get('season'))
                    for name in names_for(item) if name) and year_matches(item, cached.get('year')))
        if valid_cached and not refresh and (not manual or str(manual) == str(cached['id'])):
            out['sources'][site] = dict(cached)
            if 'cover' not in cached:
                try:
                    out['sources'][site]['cover'] = check.og_image(fetch(cached['url']))
                except Exception as e:
                    errors[site + '_detail'] = str(e)
            continue
        try:
            pid, title, year = str(manual) if manual else None, item['title'], item.get('year')
            if not pid:
                for name in names_for(item):
                    if not name:
                        continue
                    season = item.get('season')
                    queries = [name + '第' + chinese(season) + '季'] if season and site == 'huaren' else [name]
                    if season and site == 'ikanbot':
                        queries += [name + ' 第' + chinese(season) + '季', name + '第' + chinese(season) + '季']
                    for query in queries:
                        rows = candidates(site, query, fetch)
                        choices = [r for r in rows if any(matches(r[1], allowed, season) for allowed in names_for(item) if allowed) and year_matches(item, r[2])]
                        if choices:
                            pid, title, year = choices[0]
                            break
                    if pid:
                        break
            if not pid:
                continue
            url = page_url(site, pid)
            source = {'id': pid, 'url': url, 'title': title, 'year': year}
            # The catalog only needs detail links, not episode/API resources.
            try:
                body = fetch(url)
                source['cover'] = check.og_image(body)
            except Exception as e:
                errors[site + '_detail'] = str(e)
            out['sources'][site] = source
        except Exception as e:
            errors[site] = str(e)
    cover_urls = list(dict.fromkeys(v for u in
                     [item.get('cover'), *(s.get('cover') for s in out['sources'].values())] if u for v in cover_variants(u)))
    old_url = old.get('cover_url') or old.get('cover_input') or next((s.get('cover') for s in old.get('sources', {}).values() if s.get('cover')), None)
    if old_url in cover_urls and old.get('cover') and not old['cover'].startswith('http') and (Path(docs) / old['cover']).is_file() and not refresh and old.get('cover_input') == item.get('cover'):
        out['cover'], out['cover_url'] = old['cover'], old_url
    else:
        for url in cover_urls:
            saved = saver(url, docs)
            if not saved.startswith('http'):
                out['cover'], out['cover_url'] = saved, url
                break
        else:
            if cover_urls:
                recovered = alternate_cover(item, out['sources'], fetch, saver, docs, set(cover_urls))
                out['cover'], out['cover_url'] = recovered or (cover_urls[0], cover_urls[0])
    out['cover_input'] = item.get('cover')
    if errors:
        out['errors'] = errors
    return out


def run(source, output, refresh=False, fetch=check.fetch_text, saver=check.save_cover):
    data = json.loads(Path(source).read_text())
    dest = Path(output)
    old = json.loads(dest.read_text()) if dest.exists() else {'tabs': []}
    index = {}
    for tab in old['tabs']:
        for item in tab['items']:
            for entry in item.get('season_items', [item]):
                index[(entry['title'], entry.get('year'), entry.get('season'))] = entry
    result = {'tabs': []}
    def checkpoint():
        # Preserve unvisited cached rows if interrupted; final output prunes removed input rows.
        merged = {'tabs': []}
        for spec in data['tabs']:
            current = next((t for t in result['tabs'] if t['key'] == spec['key']), None)
            prior = next((t for t in old['tabs'] if t['key'] == spec['key']), None)
            items = list(current['items']) if current else []
            if spec['kind'] == 'tv' and prior:
                items = [dict(i, season_items=i['season_items'] + [e for e in next((p for p in prior['items'] if p['title'] == i['title']), {}).get('season_items', [])
                        if e['season'] not in {s['season'] for s in i['season_items']}]) for i in items]
            seen = {(i['title'], i.get('year')) for i in items}
            items += [i for i in (prior or {}).get('items', []) if (i['title'], i.get('year')) not in seen]
            merged['tabs'].append(dict(spec, items=items))
        write(merged)

    def write(value):
        temp = dest.with_suffix('.tmp')
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        temp.replace(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    for tab in data['tabs']:
        newtab = dict(tab, items=[])
        result['tabs'].append(newtab)
        items = sorted(tab['items'], key=lambda i: -i.get('ceremony', 0)) if tab['key'] == 'oscar' else tab['items']
        for item in items:
            entries = []
            for n in range(1, item.get('seasons', 1) + 1):
                entry = dict(item)
                if tab['kind'] == 'tv':
                    entry['season'] = n
                    if n == 1 and item.get('start'):
                        entry['year'] = item['start']
                    # Optional per-season manual overrides; a scalar ID applies only to season 1.
                    for site in ('huaren', 'ikanbot', 'cover'):
                        value = item.get(site)
                        if isinstance(value, dict):
                            entry[site] = value.get(str(n))
                        elif n > 1:
                            entry.pop(site, None)
                key = (entry['title'], entry.get('year'), entry.get('season'))
                resolved = resolve(entry, index.get(key), refresh, fetch, saver, dest.parent.parent)
                index[key] = resolved
                entries.append(resolved)
                if tab['kind'] == 'tv':
                    show = dict(item, season_items=list(entries), cover=next((e.get('cover') for e in entries if e.get('cover')), None))
                    if n == 1:
                        newtab['items'].append(show)
                    else:
                        newtab['items'][-1] = show
                    checkpoint()
            if tab['kind'] != 'tv':
                newtab['items'].append(entries[0])
            # Checkpoint every item so interrupted runs can resume.
            checkpoint()
            print(f"{tab['key']}: {item['title']} ({sum(bool(e['sources']) for e in entries)}/{len(entries)})", flush=True)
    write(result)
    summary(result)
    return result


def summary(data):
    print('\n=== Catalog summary ===')
    for tab in data['tabs']:
        entries = [e for i in tab['items'] for e in i.get('season_items', [i])]
        missing = [e['title'] + (f" 第{e['season']}季" if e.get('season') else '') for e in entries if not e['sources']]
        print(f"{tab['name']}: 找到 {len(entries)-len(missing)}/{len(entries)}，缺 {len(missing)}")
        if missing:
            print('缺失：' + '、'.join(missing))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    client = Client()
    run(check.ROOT / 'catalog.json', check.ROOT / 'docs/data/catalog.json', args.refresh, client.fetch, client.cover)


if __name__ == '__main__':
    main()
