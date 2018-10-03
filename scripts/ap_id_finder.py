import csv

from unidecode import unidecode as u
from nameparser import HumanName

def format_name(n, string_format):
    old = n.string_format
    n.string_format = string_format
    ret = str(n)
    n.string_format = old
    return ret

def get_potential_names(n):
    potential_names = [
        n.full_name,
        format_name(n, '{title} {first} {middle} {last} {suffix} ({nickname})'),
        format_name(n, '{first} {middle} {last}'),
        format_name(n, '{first} {last}'),
        # format_name(n, '{nickname} {middle} {last}'),
        # format_name(n, '{nickname} {last}'),
    ]
    return potential_names

def match(name1, name2):
    n1, n2 = HumanName(name1), HumanName(name2)
    return (any(u(x) == u(y) for x in get_potential_names(n1)
                             for y in get_potential_names(n2)))

with open('ap_candidates.csv') as f:
    reader = csv.DictReader(f)
    ap_candidates = [row for row in reader]
    for row in ap_candidates:
        n = HumanName()
        n.first = row['first_name']
        n.middle = row['middle_name']
        n.last = row['last_name']
        n.suffix = row['suffix']
        row['name'] = str(n)

with open('ap_historical_ids.csv') as f:
    reader = csv.DictReader(f)
    ap_candidates2 = [row for row in reader]

def find(name):
    for row in ap_candidates:
        if match(name, row['name']):
            # print(f'found match for {name} with', row['name'])
            return int(row['pol_id'])
