"""GoKwik checkout behaviour -> repo/data/checkout_data.js (window.SC_CK). Aggregates only: no names, phones,
emails, addresses or order IDs leave this script (the repo is public).
usage: python3 build_checkout.py <orders.csv> <carts.csv> [<orders.csv> <carts.csv> ...]   (pairs; later files win on overlap)
Periods: BAU = Sep 1-21 + Oct 1-6 (whatever days the files cover), EVE = Oct 7, SALE = Oct 8 onward.
The newest day is usually partial and the two exports stop at different times, so both are cut at the
earlier of the two last timestamps for that day before any rate is computed."""
import csv, sys, re, json, datetime
from collections import defaultdict, Counter

pairs = [(sys.argv[i], sys.argv[i + 1]) for i in range(1, len(sys.argv), 2)]
P = lambda s: datetime.datetime.strptime(s.strip(), '%d/%m/%Y %I:%M %p')
num = lambda s: float(str(s or 0).replace(',', '') or 0)
ph = lambda s: re.sub(r'\D', '', s or '')[-10:]

orders, carts = {}, {}
def load(path, store, key):
    # a newer export replaces every day it covers (GoKwik drops carts from the list once they convert)
    rows = list(csv.DictReader(open(path, encoding='utf-8-sig')))
    days = {P(x['Created At']).date() for x in rows}
    for k in [k for k, x in store.items() if P(x['Created At']).date() in days]: del store[k]
    for x in rows: store[x[key]] = x
for of, cf in pairs:
    load(of, orders, 'Order Number'); load(cf, carts, 'ID')
O = [x for x in orders.values() if x['Merchant Order Status'] != 'cancelled']
C = list(carts.values())
for x in O: x['_t'] = P(x['Created At'])
for x in C: x['_t'] = P(x['Created At'])
import os
if os.environ.get('THROUGH'):   # align with the rest of the dashboard: drop anything after the data-through date
    lim = datetime.datetime.fromisoformat(os.environ['THROUGH']) + datetime.timedelta(days=1)
    O = [x for x in O if x['_t'] < lim]; C = [x for x in C if x['_t'] < lim]
if os.environ.get('FROM'):      # lower bound, used to build an increment that is added to an earlier build
    lo = datetime.datetime.fromisoformat(os.environ['FROM'])
    O = [x for x in O if x['_t'] >= lo]; C = [x for x in C if x['_t'] >= lo]
# cut the newest day at the earlier export's last timestamp
last_day = max(x['_t'] for x in O).date()
cut = min(max(x['_t'] for x in O if x['_t'].date() == last_day), max(x['_t'] for x in C if x['_t'].date() == last_day))
O = [x for x in O if x['_t'] <= cut]; C = [x for x in C if x['_t'] <= cut]
partial = cut.time() < datetime.time(23, 30)

def per(d):
    s = d.isoformat()
    if s >= '2026-10-08': return 'SALE'
    if s == '2026-10-07': return 'EVE'
    if '2026-09-22' <= s <= '2026-09-30': return 'X'
    return 'BAU'

def norm_src(s, m):
    s = (s or '').strip().lower(); m = (m or '').strip().lower()
    if s in ('', 'na', 'direct') and m in ('', 'na'): return 'direct / untagged'
    return f'{s or "?"} / {m or "—"}'
def norm_lp(p):
    p = (p or '').split('?')[0].rstrip('/') or '/'
    return p if p != 'blank' else '(unknown)'
def band(v):
    return '< ₹2k' if v < 2000 else '₹2–5k' if v < 5000 else '₹5–15k' if v < 15000 else '₹15–30k' if v < 30000 else '₹30k+'
def oprods(x): return [p.split(' - ')[0].strip() for p in (x['Product Name'] or '').split(' | ') if p.strip()]
def cprods(x): return [m.strip() for m in re.findall(r'#([^(#]+)\(', x['Line items'] or '')]
is_matt = lambda names: any('Mattress' in n and 'Topper' not in n and 'Protector' not in n for n in names)
PAY = {'upiintent': 'UPI', 'cc': 'Credit card', 'dc': 'Debit card', 'emi-cc': 'Card EMI', 'snapmint': 'Snapmint (pay later)', 'cod': 'COD'}

# recovery: a cart counts as recovered if the same phone placed an order after the cart (up to the cut-off)
otimes = defaultdict(list)
for x in O: otimes[ph(x['Customer Phone'])].append(x['_t'])

days = defaultdict(lambda: defaultdict(float))
br = {k: defaultdict(lambda: defaultdict(lambda: [0, 0, 0.0])) for k in ('src', 'lp', 'band', 'cust', 'risk', 'prod', 'code', 'matt')}
mix = {k: defaultdict(Counter) for k in ('pay', 'stage', 'hour_o', 'hour_c')}
for x in O:
    d = x['_t'].date(); p = per(d); e = days[d.isoformat()]
    v = num(x['Grand Total']); e['o'] += 1; e['rev'] += v; e['items'] += num(x['Total Qty Ordered'])
    code = (x['Coupon Code'] or '').strip().upper()
    if code: e['oCode'] += 1
    if x.get('Address Pre-filled') == 'TRUE': e['prefill'] += 1
    if x.get('Customer Type - Merchant') == 'repeat': e['oRep'] += 1
    names = oprods(x); m = is_matt(names)
    if m: e['oM'] += 1
    mix['pay'][p][PAY.get(x['Payment Method'].lower(), 'Other')] += 1
    mix['hour_o'][p][x['_t'].hour] += 1
    for k, key in (('src', norm_src(x['Utm Source'], x['Utm Medium'])), ('lp', norm_lp(x['Landing Page'])), ('band', band(v)),
                   ('cust', x.get('Customer Type - Merchant') or '?'), ('risk', x.get('RTO Risk') or '?'), ('code', code or '(no code)'), ('matt', 'Has a mattress' if m else 'No mattress')):
        b = br[k][p][key]; b[0] += 1; b[2] += v
    for n in set(names): br['prod'][p][n][0] += 1
for x in C:
    d = x['_t'].date(); p = per(d); e = days[d.isoformat()]
    v = num(x['Amount']); e['ab'] += 1; e['abVal'] += v
    stage = (x['Drop Stage'] or '').strip() or 'Unknown'
    mix['stage'][p][stage.capitalize() if stage == 'payment failed' else stage] += 1
    mix['hour_c'][p][x['_t'].hour] += 1
    code = (x['Discount Code'] or '').strip().upper()
    if code: e['abCode'] += 1
    t = otimes.get(ph(x['Phone Number']), [])
    if any(t0 > x['_t'] for t0 in t): e['rec'] += 1
    if x.get('Customer Type - Merchant') == 'repeat': e['abRep'] += 1
    names = cprods(x); m = is_matt(names)
    if m: e['abM'] += 1
    for k, key in (('src', norm_src(x['Utm Source'], x['Utm Medium'])), ('lp', norm_lp(x['Landing Page'])), ('band', band(v)),
                   ('cust', x.get('Customer Type - Merchant') or '?'), ('risk', x.get('Risk Flag') or '?'), ('code', code or '(no code)'), ('matt', 'Has a mattress' if m else 'No mattress')):
        b = br[k][p][key]; b[1] += 1
    for n in set(names): br['prod'][p][n][1] += 1

def pack(k, top=None, minn=0):
    out = {}
    for p in ('BAU', 'SALE'):
        rows = [[key, v[0], v[1], round(v[2])] for key, v in br[k][p].items() if v[0] + v[1] >= minn]
        rows.sort(key=lambda r: -(r[1] + r[2]))
        out[p] = rows[:top] if top else rows
    return out
dl = []
for d in sorted(days):
    e = days[d]; dd = datetime.date.fromisoformat(d)
    dl.append({'d': d, 'per': per(dd), **{k: round(v) for k, v in e.items()}})
res = {'meta': {'cut': cut.strftime('%Y-%m-%d %H:%M'), 'partial': partial, 'from': min(dl, key=lambda x: x['d'])['d'], 'to': max(dl, key=lambda x: x['d'])['d'],
                'bauDays': [x['d'] for x in dl if x['per'] == 'BAU'], 'saleDays': [x['d'] for x in dl if x['per'] == 'SALE']},
       'days': dl,
       'pay': {p: dict(mix['pay'][p]) for p in ('BAU', 'SALE')}, 'stage': {p: dict(mix['stage'][p]) for p in ('BAU', 'SALE')},
       'hourO': {p: [mix['hour_o'][p][h] for h in range(24)] for p in ('BAU', 'SALE')}, 'hourC': {p: [mix['hour_c'][p][h] for h in range(24)] for p in ('BAU', 'SALE')},
       'src': pack('src', 15, 10), 'lp': pack('lp', 15, 10), 'band': pack('band'), 'cust': pack('cust'), 'risk': pack('risk'), 'prod': pack('prod', 20, 10),
       'code': pack('code', 12, 5), 'matt': pack('matt')}
blob = json.dumps(res, separators=(',', ':'), ensure_ascii=False)
for bad in ('@', '+91'):   # privacy guard: no emails / phone numbers in the output
    assert bad not in blob, bad
open(os.environ.get('OUT', '/home/claude/sc/repo/data/checkout_data.js'), 'w').write('// Generated by sale/build_checkout.py from GoKwik exports — aggregates only.\nwindow.SC_CK = ' + blob + ';\n')
print('checkout_data.js', len(blob) // 1024, 'KB; orders', len(O), 'carts', len(C), 'cut', cut, 'partial', partial)
for x in dl: print(x['d'], x['per'], x.get('o', 0), x.get('ab', 0), round(x.get('o', 0) / max(1, x.get('o', 0) + x.get('ab', 0)) * 100, 1), 'rec', x.get('rec', 0))
