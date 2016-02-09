#!/usr/bin/env python

import argparse
from datetime import date
import csv
import urllib3

urllib3.disable_warnings()

try:
    from opendata import OpendataClient
except ImportError:
    import requests
    import sys
    r = requests.get('https://raw.githubusercontent.com/diavgeia/opendata-client-samples-python/master/opendata.py')
    if r.status_code != requests.codes.ok:
        print 'Cannot find diavgeia opendata client.'    
        sys.exit(1)
    with open('opendata.py', 'w') as f:
        f.write(r.content)
    from opendata import OpendataClient

oc = OpendataClient('https://diavgeia.gov.gr/opendata')

def getafmbyname(name):
    afmlist = {}

    res = oc.get_advanced_search_results('receiverName:"' + name + '"', size = 50)
    for dec in res['decisions']:
        if 'sponsor' not in dec['extraFieldValues']:
            continue

        for sp in dec['extraFieldValues']['sponsor']:
            if sp['sponsorAFMName']['afm'] not in afmlist:
                afmlist[sp['sponsorAFMName']['afm']] = [sp['sponsorAFMName']['name']]
            else:
                if sp['sponsorAFMName']['name'] not in afmlist[sp['sponsorAFMName']['afm']]:
                    afmlist[sp['sponsorAFMName']['afm']].append(sp['sponsorAFMName']['name'])

    return afmlist

def getpaymentsbyafm(afm, year = 2015, page = 0):
    payments = []

    q = 'receiverAFM:"%s" AND issueDate:[DT(%i-01-01T00:00:00) TO DT(%i-12-31T23:59:59)]' % (afm, year, year)
    res = oc.get_advanced_search_results(q, page = page, size = 50)
    for dec in res['decisions']:
        if 'sponsor' not in dec['extraFieldValues']:
            continue

        entry = {}
        for sp in dec['extraFieldValues']['sponsor']:
            if sp['sponsorAFMName']['afm'] == afm:
                entry['amount'] = sp['expenseAmount']['amount']
                break

        if 'amount' not in entry:
            continue

        entry['ada'] = dec['ada']
        entry['org'] = dec['extraFieldValues']['org']['name']
        entry['orgafm'] = dec['extraFieldValues']['org']['afm']
        entry['subject'] = dec['subject']
        entry['date'] = date.fromtimestamp(dec['issueDate'] / 1000).strftime('%d-%m-%Y')
        entry['url'] = dec['documentUrl']
        payments.append(entry)

    if 50 * page + res['info']['actualSize'] < res['info']['total']:
        payments.extend(getpaymentsbyafm(afm, year, page + 1))

    return payments

parser = argparse.ArgumentParser(description = 'Public expenses downloader')

group = parser.add_mutually_exclusive_group(required = True)
group.add_argument('-n', '--name', help = 'Name of the person to search for')
group.add_argument('-a', '--afm', help = 'AFM of the person to search for')

parser.add_argument('-y', '--year', help = 'Search for specific year', type = int, default = 2015)
parser.add_argument('-c', '--csv', help = 'Save results to CSV file', type = argparse.FileType('w'))
parser.add_argument('-q', '--quiet', help = 'Do not print results to output', action = 'store_true', default = False)
parser.add_argument('-t', '--totals', help = 'Calculate totals', action = 'store_true', default = False)

args = parser.parse_args()

if args.name is not None:
    afmlist = getafmbyname(args.name)
    print 'AFM\tName(s):'
    for afm in afmlist.keys():
        print afm + '\t' + ', '.join(afmlist[afm])

    afm = raw_input('Please enter correct AFM: ')
else:
    afm = args.afm

payments = getpaymentsbyafm(afm, year = args.year)

if args.csv is not None:
    args.csv.write(u'\ufeff'.encode('utf8'))
    fieldnames = ['ada', 'org', 'orgafm', 'subject', 'date', 'amount', 'url']
    writer = csv.DictWriter(args.csv, fieldnames = fieldnames)
    writer.writeheader()
else:
    writer = None

paymentsbyorg = {}
orgbyafm = {}
total = 0
for payment in payments:
    if args.quiet == False:
        print '%i\t%s (%s)\t%s\t%s' % (payment['amount'], payment['org'], payment['orgafm'], payment['subject'], payment['url'])
    if writer is not None:
        writer.writerow({k:unicode(v).encode('utf8') for k,v in payment.items()})

    if payment['orgafm'] not in paymentsbyorg:
        paymentsbyorg[payment['orgafm']] = 0
    paymentsbyorg[payment['orgafm']] += payment['amount']
    total += payment['amount']
    orgbyafm[payment['orgafm']] = payment['org']

if args.totals:
    print 'Totals by organization'
    print 'Organization\tTotal'
    for org in paymentsbyorg.keys():
        print '%s\t%i' % (orgbyafm[org], paymentsbyorg[org])

    print 'Total payments: %i' % (total)

if writer is not None:
    args.csv.close()
