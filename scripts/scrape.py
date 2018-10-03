#!/usr/bin/env python3

import us
import tqdm
import requests
import datetime
import lxml.html
import urllib.parse as urlparse

from requests.adapters import HTTPAdapter
from requests_futures.sessions import FuturesSession
from concurrent.futures import as_completed

session = FuturesSession()
session.mount('https://classic.nga.org', HTTPAdapter(max_retries=15))

KNOWN_EXCEPTIONS = {
    'https://classic.nga.org/cms/sam-brownback':
        [{'start': '2011-01-10', 'end': '2015-01-12'},
        {'start': '2015-01-12', 'end': '2018-01-31'}]
}

def parse_date(text):
    if not text: return None
    return datetime.datetime.strptime(text, '%b %d, %Y').date().isoformat()

def parse_term(text):
    start, end = [parse_date(x.strip()) for x in text.split('-')]
    return {'start': start, 'end': end}

def parse_terms(text):
    return [parse_term(x.strip()) for x in text.split('\t, ')]

def parse_bio_page(doc, row):
    birthday = None
    if doc.cssselect('article .col-md-7 address p strong')[0].text == 'Born:':
        birthday = parse_date(doc.cssselect('article .col-md-7 address p strong')[0].tail.strip())

    terms = []

    if row['url'] in KNOWN_EXCEPTIONS:
        terms = KNOWN_EXCEPTIONS[row['url']]
    else:
        if doc.cssselect('article .col-md-3 address p strong'):
            terms = parse_terms(doc.cssselect('article .col-md-3 address p strong')[0].tail.strip())
        else:
            raise Exception(f"NO TERMS FOUND for {row['url']} !!!!!!!!!!!!!!!!!!!!!")
    
    terms.sort(key=lambda x: x['start'])

    return {
        **row,
        'picture': 'https://classic.nga.org' + doc.cssselect('img.feature-img')[0].get('src'),
        'terms': terms,
        'birthday': birthday,
    }

def parse_search_page(doc):
    for row in doc.cssselect('table tbody tr'):
        cells = row.cssselect('td')
        yield {
            'name': cells[0].cssselect('a')[0].text.replace('Gov. ', ''),
            'url': 'https://classic.nga.org' + cells[0].cssselect('a')[0].get('href'),
            'state': us.states.lookup(cells[1].text).abbr,
            # 'time_in_office': cells[2].text_content().strip(), # not needed
            'party': cells[3].text
        }

def parse_cursor(doc):
    href = doc.cssselect('a[aria-label="Next"]')[0].get('href')
    qs = urlparse.urlparse(href).query
    query = urlparse.parse_qs(qs)
    begin_param = next(param for param in query if param.startswith('begin'))
    return begin_param[len('begin'):]

def get_pagination_cursor():
    response = requests.get("https://classic.nga.org/cms/FormerGovBios?submit=Search")
    doc = lxml.html.fromstring(response.content)
    cursor = parse_cursor(doc)
    return cursor

def scrape_page(cursor, offset, pagesize):
    params = {
        'begin'+cursor: offset,
        'pagesize'+cursor: pagesize,
        'end'+cursor: offset+pagesize-1,
        'submit': 'Search'
    }
    response = requests.get("https://classic.nga.org/cms/home/governors/past-governors-bios.default.html", params=params)
    doc = lxml.html.fromstring(response.content)
    rows = {x['url']:x for x in parse_search_page(doc)}
    futures = {session.get(url, timeout=10):url for url in rows}
    for future in tqdm.tqdm(as_completed(futures), total=len(rows)):
        url = futures[future]
        row = rows[url]
        response = future.result()
        doc = lxml.html.fromstring(response.content)
        detailed_row = parse_bio_page(doc, row)
        yield detailed_row

def scrape(offset=0, pagesize=1000):
    print("Making initial query to find pagination cursor...")
    cursor = get_pagination_cursor()
    print(f"Cursor Found: {cursor}")

    while True:
        print(f"Downloading Page {offset//pagesize+1} (offset: {offset}, pagesize: {pagesize})...")
        num_rows = 0
        for row in scrape_page(cursor, offset, pagesize):
            num_rows += 1
            yield row
        if num_rows < pagesize: break
        offset += pagesize

if __name__ == "__main__":
    import json

    start = 0
    with open('raw.json', 'w') as f:
        for row in scrape(offset=start):
            f.write(json.dumps(row) + "\n")
