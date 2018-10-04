#!/usr/bin/env python3

import us
import yaml

STATES = {x.abbr for x in us.STATES} - {'DC'}

with open('governors.yaml') as f:
    governors = yaml.load(f)

current_governors = [
    x for x in governors if not x['terms'][-1]['end'] if x['terms'][-1]['state'] in STATES
]

assert len(current_governors) == 50

print("Governors by States:")
for i, governor in enumerate(sorted(current_governors, key=lambda x: x['terms'][-1]['state'])):
    print(i, governor['terms'][-1]['state'], governor['name']['full'], '\t', governor['id']['ap'])
