import json
import os
import sys
from datetime import datetime

from scholarly import ProxyGenerator, scholarly
from scholarly import _proxy_generator

AUTHOR_ID = 'Qi2PSmEAAAAJ'

# Papers that get their own shields.io badge: output suffix -> author_pub_id
BADGE_PUBS = {
    'mtl': f'{AUTHOR_ID}:Tyk-4Ss8FVUC',
    'mnemonics': f'{AUTHOR_ID}:UeHWp8X0CEIC',
    'aanets': f'{AUTHOR_ID}:u-x6o8ySG0sC',
    'e3bm': f'{AUTHOR_ID}:d1gkVwhDpl0C',
    'lst': f'{AUTHOR_ID}:2osOgNQ5qMEC',
}


def _fail_fast_on_captcha(self, url):
    # scholarly's default handler opens a browser and waits up to a week for a
    # human to solve the CAPTCHA. In CI nobody can, so the job hangs until the
    # 6-hour limit kills it. Raising here makes scholarly rotate to the next
    # proxy/session instead, and give up after set_retries() attempts.
    raise RuntimeError(f'Got a CAPTCHA from Google Scholar for {url}')


_proxy_generator.ProxyGenerator._handle_captcha2 = _fail_fast_on_captcha


def setup_proxy():
    pg = ProxyGenerator()
    api_key = os.environ.get('SCRAPERAPI_KEY')
    if api_key:
        if pg.ScraperAPI(api_key):
            print('Using ScraperAPI proxy', file=sys.stderr)
            # Use it for every request (author pages too), not just the primary ones.
            scholarly.use_proxy(pg, pg)
            return
        print('ScraperAPI setup failed, falling back to free proxies', file=sys.stderr)
        pg = ProxyGenerator()
    if pg.FreeProxies():
        print('Using free rotating proxies', file=sys.stderr)
        scholarly.use_proxy(pg, pg)
    else:
        print('No working proxy found, trying without one', file=sys.stderr)


scholarly.set_retries(5)
setup_proxy()

author: dict = scholarly.search_author_id(AUTHOR_ID)
scholarly.fill(author, sections=['basics', 'indices', 'counts', 'publications'])
author['updated'] = str(datetime.now())
author['publications'] = {v['author_pub_id']: v for v in author['publications']}
print(json.dumps(author, indent=2))

os.makedirs('results', exist_ok=True)
with open('results/gs_data.json', 'w') as outfile:
    json.dump(author, outfile, ensure_ascii=False)


def write_badge(suffix, count):
    data = {
        'schemaVersion': 1,
        'label': 'citations',
        'message': f'{count}',
    }
    name = f'results/gs_data_shieldsio{suffix}.json'
    with open(name, 'w') as outfile:
        json.dump(data, outfile, ensure_ascii=False)


write_badge('', author['citedby'])
for suffix, pub_id in BADGE_PUBS.items():
    pub = author['publications'].get(pub_id)
    if pub is None:
        print(f'Warning: publication {pub_id} not found, skipping {suffix} badge', file=sys.stderr)
        continue
    write_badge(f'_{suffix}', pub['num_citations'])
