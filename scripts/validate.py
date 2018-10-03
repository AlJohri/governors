#!/usr/bin/env python3

import us
import json

from ap_id_finder import find as find_ap_id

STATES = {x.abbr for x in us.STATES} - {'DC'}

with open('raw.json') as f:
    governors = [json.loads(line) for line in f]

current_governors = [
    x for x in governors if not x['terms'][-1]['end'] if x['state'] in STATES
]

assert len(current_governors) == 50

print("Governors by States:")
for i, governor in enumerate(sorted(current_governors, key=lambda x: x['state'])):
    npid = find_ap_id(name=governor['name'])
    print(i, governor['state'], governor['name'], '\t', npid)
