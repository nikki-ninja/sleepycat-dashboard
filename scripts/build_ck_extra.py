"""Adds GoKwik funnel steps + payment success/failure (aggregates only) to repo/data/checkout_data.js.
usage: THROUGH=YYYY-MM-DD python3 build_ck_extra.py <funnel.csv> <transaction.csv>"""
import csv, sys, json, os, datetime
from collections import defaultdict, Counter
TH = os.environ.get('THROUGH', '2099-01-01'); F0 = '2026-10-08'
n = lambda s: int(float(str(s or 0).replace(',', '') or 0))
K = ['Checkout Started', 'Address Landed', 'Payment Step Reached', 'Payment Method Selected', 'Sessions Converted']
def lp(p):
    p = (p or '').split('?')[0].rstrip('/') or '/'
    return p if p not in ('blank', '') else '(unknown)'
def src(s, m):
    s = (s or '').strip().lower(); m = (m or '').strip().lower()
    return 'direct / untagged' if s in ('', 'na', 'direct') and m in ('', 'na') else f'{s or "?"} / {m or "—"}'
day, bylp, bysrc = defaultdict(lambda: [0]*5), defaultdict(lambda: [0]*5), defaultdict(lambda: [0]*5)
for x in csv.DictReader(open(sys.argv[1], encoding='utf-8-sig')):
    d = x['Date']
    if d > TH: continue
    v = [n(x[k]) for k in K]
    for i in range(5): day[d][i] += v[i]
    if d >= F0:
        for agg, key in ((bylp, lp(x['Landing Page'])), (bysrc, src(x['UTM Source'], x['UTM Medium']))):
            for i in range(5): agg[key][i] += v[i]
top = lambda a, k: [[key] + v for key, v in sorted(a.items(), key=lambda kv: -kv[1][0])[:k]]
PM = {'upi': 'UPI', 'snapmint': 'Snapmint', 'cc': 'Credit card', 'emi-cc': 'Card EMI', 'dc': 'Debit card', 'netbanking': 'Netbanking'}
meth, fail = defaultdict(lambda: [0, 0, 0, 0]), Counter()   # success, failed, dropped (initiated), success value
for x in csv.DictReader(open(sys.argv[2], encoding='utf-8-sig')):
    d = datetime.datetime.strptime(x['Created At'].strip(), '%d/%m/%Y %I:%M %p').date().isoformat()
    if d < F0 or d > TH: continue
    m = PM.get(x['Payment Method'], 'Wallet' if x['Payment Method'].startswith('wallet') else 'Other'); s = x['Status']
    if s in ('success', 'refunded'): meth[m][0] += 1; meth[m][3] += float(x['Amount'] or 0)
    elif s == 'failed': meth[m][1] += 1; fail[(x['Failure Bucket 2'] or x['Failure Bucket 1'] or 'Unknown').strip().upper()] += 1
    else: meth[m][2] += 1
path = '/home/claude/sc/repo/data/checkout_data.js'
txt = open(path).read(); pre = 'window.SC_CK = '; i = txt.index(pre) + len(pre)
ck = json.loads(txt[i:txt.rindex(';')])
ck['fun'] = {'steps': ['Checkout', 'Address', 'Payment page', 'Method picked', 'Paid'],
             'days': [[d] + day[d] for d in sorted(day)], 'lp': top(bylp, 12), 'src': top(bysrc, 10), 'to': max(day)}
ck['txn'] = {'meth': sorted([[k] + v[:3] + [round(v[3])] for k, v in meth.items()], key=lambda r: -(r[1] + r[2] + r[3])),
             'fail': fail.most_common(7), 'from': F0, 'to': TH}
blob = json.dumps(ck, separators=(',', ':'), ensure_ascii=False)
for bad in ('@', '+91'): assert bad not in blob, bad
open(path, 'w').write(txt[:i] + blob + ';\n')
print('days', len(day), 'lp', ck['fun']['lp'][:4]); print(ck['txn']); print([r for r in ck['fun']['days'] if r[0] >= '2026-10-20'])
