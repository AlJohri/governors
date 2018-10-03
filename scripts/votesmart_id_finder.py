#!/usr/bin/env python3

import os
import json
import logging

import us
from unidecode import unidecode as u
from votesmart import votesmart, VotesmartApiError
from nameparser import HumanName

votesmart.apikey = os.environ['VOTESMART_API_KEY']

STATES = {x.abbr for x in us.STATES} - {'DC'}

# fix nick name
def get_vc_display_name(vc):
    return " ".join(x for x in [vc.firstName, "(%s)" % vc.nickName if vc.nickName else "", vc.middleName, vc.lastName, vc.suffix] if x)
    # vc.preferredName, vc.ballotName

alternative_firstnames = {
    'Philip': 'Phil',
    'Matthew': 'Matt',
}

alternative_firstnames.update({v:k for k,v in alternative_firstnames.items()})

def get_votesmart_potential_names(v):
    potential_names = []

    first_names = [x for x in [v.firstName, v.nickName, v.preferredName, alternative_firstnames.get(v.firstName)] if x]
    for first_name in first_names:
        potential_name = " ".join(x for x in [first_name, v.middleName, v.lastName, v.suffix] if x)
        potential_names.append(potential_name)

        potential_name = " ".join(x for x in [first_name, v.lastName, v.suffix] if x)
        potential_names.append(potential_name)

        potential_name = " ".join(x for x in [first_name, v.lastName] if x)
        potential_names.append(potential_name)

    if v.ballotName:
        potential_names.append(v.ballotName)

    return list(set(potential_names))

def format_name(n, string_format):
    old = n.string_format
    n.string_format = string_format
    ret = str(n)
    n.string_format = old
    return ret

def get_input_potential_names(n):
    potential_names = [
        n.full_name,
        format_name(n, '{title} {first} {middle} {last} {suffix} ({nickname})'),
        format_name(n, '{first} {middle} {last}'),
        format_name(n, '{first} {last}'),
        format_name(n, '{nickname} {middle} {last}'),
        format_name(n, '{nickname} {last}'),
    ]
    return potential_names

def get_officials_by_last_name(last_name, valid_office_types=None):
    try:
        results = votesmart.officials.getByLastname(u(last_name))
        # votesmart.officials.getByLevenstein
    except VotesmartApiError:
        # print("\t", t.red(str(e)))
        results = []
    
    if valid_office_types:
        results = [x for x in results if x.electionOffice in valid_office_types or x.officeName in valid_office_types]
    
    return results

def get_candidates_by_last_name(last_name, election_year, valid_office_types):
    try:
        results = votesmart.candidates.getByLastname(u(last_name), electionYear=election_year)
    except VotesmartApiError:
        # print("\t", t.red(str(e)))
        results = []

    if valid_office_types:
        results = [x for x in results if x.electionOffice in valid_office_types or x.officeName in valid_office_types]

    return results

def find(name, currently_in_office, term_start=None, term_end=None, valid_office_types=None):
    n = HumanName(name)
    votesmart_results = []

    if currently_in_office:
        logging.debug(f"searching for officials by last name {n.last} with office types {valid_office_types}")
        votesmart_results += get_officials_by_last_name(n.last, valid_office_types)

    if term_start: 
        if len(votesmart_results) == 0:
            for year in range(term_start-1, term_end or 2018):
                logging.debug(f"searching for candidates by last name {n.last}, election year {year}, with office types {valid_office_types}")
                votesmart_results += get_candidates_by_last_name(n.last, year, valid_office_types)

    if len(votesmart_results) == 0:
        return
    else:
        logging.debug(f"found {len(votesmart_results)} votesmart_results before filtering by name heuristics")

    filtered_votesmart_results = [v for v in votesmart_results if
        (u(v.firstName) == u(n.first) and u(v.lastName) == u(n.last)) or
        (u(v.firstName) == u(n.first) and u(n.last) in u(v.lastName)) or # iffy?
        (u(v.middleName) == u(n.middle) and u(v.lastName) == u(n.last) and u(n.first) in u(v.firstName)) or # iffy?
        (v.nickName and u(v.nickName) == u(n.first) and u(v.lastName) == u(n.last)) or
        (v.nickName and u(v.nickName) == u(n.nickname) and u(v.lastName) == u(n.last)) or
        (v.preferredName and u(v.preferredName) == u(n.first) and u(v.lastName) == u(n.last)) or
        (any(u(x) == u(y) for x in get_votesmart_potential_names(v)
                          for y in get_input_potential_names(n)))
    ]

    num_results = len({v.candidateId for v in filtered_votesmart_results})

    logging.debug(f"filtered to {num_results} votesmart_results after filtering")
    
    if num_results == 1:
        v = filtered_votesmart_results[0]
        votesmart_id = v.candidateId
        return votesmart_id

    logging.debug(f"failed to find votesmart id for {name}")