#!/usr/bin/env python3

import us
import logging
import requests
import datetime
import lxml.html
import itertools
import urllib.parse as urlparse

from nameparser import HumanName
from requests.adapters import HTTPAdapter
from requests_futures.sessions import FuturesSession
from concurrent.futures import as_completed

session = FuturesSession(max_workers=10)
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

    page = offset//pagesize+1

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
    for i, future in enumerate(as_completed(futures)):
        url = futures[future]
        row = rows[url]
        logging.info(f'[Page {page}: {i+1} of {len(rows)}] downloaded {url}')
        response = future.result()
        doc = lxml.html.fromstring(response.content)
        detailed_row = parse_bio_page(doc, row)
        yield detailed_row

def scrape(offset=0, pagesize=1000, limit=None):

    def inner(offset, pagesize, limit):
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

    yield from itertools.islice(inner(offset, pagesize, limit), limit)

def date2year(date):
    return int(date.split('-')[0]) if date else None

def transform(row):
    """
    transforms the raw row into a row that looks like the congress legislators data
    """
    parsed_name = HumanName(row['name'])
    return {
        'id': {
            'nga': row['url']
        },
        'name': {
            'original': row['name'],
            'full': str(parsed_name),
            **parsed_name.as_dict(include_empty=False),
        },
        'bio': {
            'birthday': row['birthday']
        },
        'terms': [
            {
                'type': 'gov',
                'start': term['start'],
                'end': term['end'],
                'party': row['party'],
                'state': row['state'],
            }
            for term in row['terms']
        ]
    }

def touch(filename):
    open(filename, 'a').close()

# https://stackoverflow.com/questions/7204805/dictionaries-of-dictionaries-merge/7205107#7205107
def merge(a, b, path=None):
    "merges b into a"
    if path is None: path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:
                pass # same leaf value
            else:
                raise Exception('Conflict at %s' % '.'.join(path + [str(key)]))
        else:
            a[key] = b[key]
    return a

if __name__ == "__main__":

    logging.basicConfig(level='INFO')

    from votesmart_id_finder import find as find_votesmart_id
    from ap_id_finder import find as find_ap_id

    import oyaml as yaml

    touch('governors.yaml')
    with open('governors.yaml') as f:
        data = yaml.load(f)
        governors = {x['id']['nga']:x for x in data} if data else {}

    for row in scrape(pagesize=1000):
        row = transform(row)
        id_ = row['id']['nga']
        if id_ in governors:
            governors[id_] = merge(governors[id_], row)
        else:
            governors[id_] = row
        gov = governors[id_]

        currently_in_office = not bool(gov['terms'][-1]['end'])
        if currently_in_office or date2year(gov['terms'][-1]['start']) >= 1995:
            if 'votesmart' not in gov['id']:
                logging.debug(f'finding votesmart for {id_}')
                gov['id']['votesmart'] = find_votesmart_id(
                    name=gov['name']['original'],
                    currently_in_office=currently_in_office,
                    term_start=date2year(gov['terms'][-1]['start']),
                    term_end=date2year(gov['terms'][-1]['end']),
                    valid_office_types=['Governor'])
            if 'ap' not in gov['id']:
                gov['id']['ap'] = find_ap_id(name=gov['name']['original'])

    output_rows = sorted(governors.values(), key=lambda x: (x['terms'][-1]['end'] or '9999', x['terms'][-1]['state']), reverse=True)
    with open('governors.yaml', 'w') as f:
        yaml.dump(output_rows, f, default_flow_style=False)
