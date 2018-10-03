#!/usr/bin/env python3

import logging
import json
import oyaml as yaml
from votesmart_id_finder import find as find_votesmart_id
from ap_id_finder import find as find_ap_id
from nameparser import HumanName

def date2year(date):
    return int(date.split('-')[0]) if date else None

MIN_YEAR = 2012

logging.basicConfig(level='DEBUG')

with open('raw.json') as f:
    governors = [json.loads(line) for line in f]

rows = []

for governor in governors:
    last_term = governor['terms'][-1]
    last_term_start = date2year(last_term['start'])
    last_term_end = date2year(last_term['end'])

    if last_term_end is None or last_term_start >= MIN_YEAR:
        row = {
            'id': {
                'nga': governor['url']
            },
            'name': {
                'official_full': str(HumanName(governor['name']))
            },
            'bio': {
                'birthday': governor['birthday']
            },
            'terms': [
                {
                    'type': 'gov',
                    'start': term['start'],
                    'end': term['end'],
                    'party': governor['party'],
                    'state': governor['state'],
                }
                for term in governor['terms']
            ]
        }

        print("finding votesmart id for governor", governor['name'], governor['terms'][-1])
        currently_in_office = not bool(governor['terms'][-1]['end'])
        row['id']['votesmart'] = find_votesmart_id(
            name=governor['name'],
            currently_in_office=currently_in_office,
            term_start=date2year(governor['terms'][-1]['start']),
            term_end=date2year(governor['terms'][-1]['end']),
            valid_office_types=['Governor'])

        row['id']['ap'] = find_ap_id(name=governor['name'])

        rows.append(row)

with open('governors.json', 'w') as f:
    for row in rows:
        f.write(json.dumps(row) + "\n")

with open('governors.yaml', 'w') as f:
    yaml.dump(rows, f, default_flow_style=False)
