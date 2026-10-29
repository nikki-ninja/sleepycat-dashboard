"""GoKwik deep dive -> repo/data/gk_deep.js (window.SC_GK). Aggregates only (public repo).
usage: FROM=YYYY-MM-DD THROUGH=YYYY-MM-DD python3 build_gk_deep.py <orders.csv> <carts.csv> <funnel.csv> <transactions.csv>"""
import csv, sys, os, re, json, datetime as dt, statistics as st
from collections import Counter, defaultdict
O_F, C_F, F_F, T_F = sys.argv[1:5]
A, B = dt.date.fromisoformat(os.environ['FROM']), dt.date.fromisoformat(os.environ['THROUGH'])
P = lambda s: dt.datetime.strptime(s.strip(), '%d/%m/%Y %I:%M %p')
num = lambda s: float(str(s or 0).replace(',', '') or 0)
ph = lambda s: re.sub(r'\D', '', s or '')[-10:]
pc = lambda a, b: round(a / b * 100, 1) if b else None
rd = lambda r: list(csv.DictReader(open(r, encoding='utf-8-sig')))
O = rd(O_F); C = rd(C_F)
for x in O + C: x['_t'] = P(x['Created At'])
inw = lambda x: A <= x['_t'].date() <= B
OS = [x for x in O if inw(x)]; CS = [x for x in C if inw(x)]
ok = [x for x in OS if x['Merchant Order Status'] != 'cancelled']
PM = {'upiintent': 'UPI (app)', 'upi': 'UPI (other)', 'cc': 'Credit card', 'snapmint': 'Snapmint', 'emi-cc': 'Card EMI', 'dc': 'Debit card', 'netbanking': 'Netbanking'}
pm = defaultdict(list)
for x in ok:
    m = x['Payment Method'].lower(); pm[PM.get(m, 'Wallet' if m.startswith('wallet') else 'Other')].append(num(x['Grand Total']))
pay = sorted([[k, len(v), round(st.mean(v)), round(st.median(v))] for k, v in pm.items()], key=lambda r: -r[1])
def prods(x): return sorted({p.split(' - ')[0].strip() for p in x['Product Name'].split(' | ') if p.strip()})
ism = lambda n: 'Mattress' in n and 'Topper' not in n and 'Protector' not in n
mo = [x for x in ok if any(ism(n) for n in prods(x))]
items = Counter(min(int(num(x['Total Item Count'])), 4) for x in ok)
basket = {'matt': len(mo), 'withAny': pc(sum(len(prods(x)) > 1 for x in mo), len(mo)), 'withPillow': pc(sum(any('Pillow' in n for n in prods(x)) for x in mo), len(mo)),
          'withProtector': pc(sum(any('Protector' in n for n in prods(x)) for x in mo), len(mo)), 'mattAov': round(st.mean(num(x['Grand Total']) for x in mo)) if mo else 0,
          'items': [items[i] for i in (1, 2, 3, 4)]}
combos = [[k, n] for k, n in Counter(' + '.join(prods(x)) for x in ok if len(prods(x)) > 1).most_common(8)]
ct = Counter(x['Customer Type - Merchant'] for x in ok); cg = Counter(x['Customer Type - Gokwik'] for x in ok)
cust = {'newM': ct['new'], 'repM': ct['repeat'], 'repGk': cg['repeat'], 'prefill': pc(sum(x['Address Pre-filled'] == 'TRUE' for x in ok), len(ok)),
        'multi': sum(v > 1 for v in Counter(ph(x['Customer Phone']) for x in ok).values())}
rto_n = sum('rto' in x['Order Shipment Status'] for x in ok)
rto = {'rate': pc(rto_n, len(ok)), 'n': len(ok), 'rtoN': rto_n, 'delivered': sum(x['Order Shipment Status'] in ('delivered', 'partial delivered') for x in ok)}
# carts
bands = [('< ₹2k', 0, 2000), ('₹2–5k', 2000, 5000), ('₹5–15k', 5000, 15000), ('₹15–30k', 15000, 30000), ('₹30k+', 30000, 1e12)]
bandrows = [[l, sum(a <= num(x['Amount']) < b for x in CS), sum(a <= num(x['Grand Total']) < b for x in ok)] for l, a, b in bands]
ot = defaultdict(list)
for x in O:
    if x['Merchant Order Status'] != 'cancelled': ot[ph(x['Customer Phone'])].append(x['_t'])
rec, lag = [], []
for x in CS:
    t = [t0 for t0 in ot.get(ph(x['Phone Number']), []) if t0 > x['_t']]; rec.append(bool(t))
    if t: lag.append((min(t) - x['_t']).total_seconds() / 3600)
SN = {'Payment Page': 'Payment page', 'Payment Pending': 'Payment pending', 'payment failed': 'Payment failed', 'Address Page': 'Address page', 'Login OTP Page': 'Login OTP'}
g = defaultdict(list)
for x, r in zip(CS, rec): g[x['Drop Stage']].append(r)
recd = {'rate': pc(sum(rec), len(CS)),
        'lag': [['Within 1 hour', pc(sum(l <= 1 for l in lag), len(lag))], ['1–24 hours', pc(sum(1 < l <= 24 for l in lag), len(lag))],
                ['1–3 days', pc(sum(24 < l <= 72 for l in lag), len(lag))], ['After 3 days', pc(sum(l > 72 for l in lag), len(lag))]],
        'stage': [[SN[k], len(g[k]), pc(sum(g[k]), len(g[k]))] for k in SN if g.get(k)]}
cp = {}; never = {}
for x in CS:
    p = ph(x['Phone Number'])
    if p and p not in ot: never[p] = max(never.get(p, 0), num(x['Amount']))
pool = {'shoppers': len({ph(x['Phone Number']) for x in CS}), 'never': len(never), 'neverVal': round(sum(never.values()) / 1e7, 2),
        'big': sum(v >= 15000 for v in never.values()), 'bigVal': round(sum(v for v in never.values() if v >= 15000) / 1e7, 2)}
# funnel by source
K = ['Checkout Started', 'Address Landed', 'Payment Step Reached', 'Payment Method Selected', 'Sessions Converted']
fs = defaultdict(lambda: [0] * 5)
for x in csv.DictReader(open(F_F, encoding='utf-8-sig')):
    if not (A.isoformat() <= x['Date'] <= B.isoformat()): continue
    s, m = x['UTM Source'].strip().lower(), x['UTM Medium'].strip().lower()
    k = 'direct / untagged' if s in ('', 'na', 'direct') and m in ('', 'na') else (s + ' / ' + m if m and m != 'na' else s)
    if k == 'whatsapp / kwikpass_abc': k += ' (cart recovery)'
    for i, kk in enumerate(K): fs[k][i] += int(num(x[kk]))
fun = [[k, v[0], pc(v[1], v[0]), pc(v[2], v[0]), pc(v[3], v[2]), pc(v[4], v[0])] for k, v in sorted(fs.items(), key=lambda kv: -kv[1][0]) if v[0] >= 250][:10]
# transactions
T = [x for x in csv.DictReader(open(T_F, encoding='utf-8-sig'))]
for x in T: x['_t'] = P(x['Created At'])
T = [x for x in T if inw(x)]
okT = lambda x: x['Status'] in ('success', 'refunded')
byo = defaultdict(list)
for x in T: byo[x['Order Number']].append(x)
fails = [o for o, v in byo.items() if any(x['Status'] == 'failed' for x in v)]
saved = [o for o in fails if any(okT(x) for x in byo[o])]
TM = {'snapmint': 'Snapmint', 'cc': 'Credit card', 'upi': 'UPI', 'emi-cc': 'Card EMI', 'dc': 'Debit card'}
dead = Counter(TM.get(sorted(byo[o], key=lambda x: x['_t'])[-1]['Payment Method'], 'Other') for o in fails if o not in saved)
amt = []
for l, a, b in [('< ₹5k', 0, 5000), ('₹5–15k', 5000, 15000), ('₹15–30k', 15000, 30000), ('₹30k+', 30000, 1e12)]:
    s = [x for x in T if a <= num(x['Amount']) < b]; amt.append([l, len(s), pc(sum(okT(x) for x in s), len(s)), pc(sum(x['Status'] == 'failed' for x in s), len(s))])
cards = [x for x in T if x['Payment Method'] in ('cc', 'emi-cc', 'dc') and x['Status'] in ('success', 'refunded', 'failed')]
def rate_by(f, n):
    g = defaultdict(lambda: [0, 0])
    for x in cards: g[f(x)][0 if okT(x) else 1] += 1
    return [[k, sum(v), pc(v[0], sum(v))] for k, v in sorted(g.items(), key=lambda kv: -sum(kv[1])) if sum(v) >= 20][:n]
BANK = {'AUSF': 'AU SFB', 'UNKNOWN': 'Unknown issuer', 'AXIS': 'Axis', 'KOTAK': 'Kotak', 'AMEX': 'Amex', 'HSBC': 'HSBC', 'BOB': 'BoB', 'IDFC': 'IDFC First', 'INDUS': 'IndusInd', 'YES': 'Yes Bank', 'RBL': 'RBL'}
def bname(x):
    b = (x['Bank/Issuer'] or x['Card Issuer'] or 'UNKNOWN').strip().upper()[:20]
    return BANK.get(b, b if len(b) <= 5 else b.title())
bank = rate_by(bname, 8)
NET = {'MAST': 'Mastercard', 'VISA': 'Visa', 'RUPAYCC': 'RuPay credit', 'DINR': 'Diners', 'AMEX': 'Amex', 'RUPAY': 'RuPay debit'}
net = rate_by(lambda x: NET.get(x['Card Network'], x['Card Network'] or '?'), 6)
upi = [x for x in T if x['Payment Method'] == 'upi']
upi_open = sum(x['Status'] == 'initiated' and not x['Payment Mode'] for x in upi)
upi_mode = [x for x in upi if x['Payment Mode']]
emi = Counter(x['EMI tenure'] for x in T if x['Payment Method'] == 'emi-cc' and okT(x))
# Snapmint, attempt-level vs order-level
sn = [x for x in T if x['Payment Method'] == 'snapmint']; sno = defaultdict(list)
for x in sn: sno[x['Order Number']].append(x)
sn_paid_sn = sum(any(okT(x) for x in v) for v in sno.values())
sn_paid_any = sum(any(okT(x) for x in byo[o]) for o in sno)
sn_failed_only = sum(any(x['Status'] == 'failed' for x in v) and not any(okT(x) for x in v) for v in sno.values())
sn_init_only = sum(all(x['Status'] == 'initiated' for x in v) for v in sno.values())
snap = {'attempts': len(sn), 'status': dict(Counter(x['Status'] for x in sn)), 'orders': len(sno), 'paidSnap': sn_paid_sn, 'paidAny': sn_paid_any,
        'failedOnly': sn_failed_only, 'initOnly': sn_init_only, 'attemptsPerOrder': round(len(sn) / max(1, len(sno)), 2),
        'failDesc': Counter((x['Status Description'] or '?')[:40] for x in sn if x['Status'] == 'failed').most_common(3),
        'amtMed': round(st.median([num(x['Amount']) for x in sn])) if sn else 0}
txn = {'orderIds': len(byo), 'paidPct': pc(sum(any(okT(x) for x in v) for v in byo.values()), len(byo)), 'failedOrders': len(fails), 'savedPct': pc(len(saved), len(fails)),
       'upiOpenedLeft': upi_open, 'upiDone': pc(sum(okT(x) for x in upi_mode), len(upi_mode)), 'deadByMethod': dead.most_common(5), 'amt': amt, 'net': net, 'bank': bank,
       'emi': [[f'{k} months', v] for k, v in emi.most_common(4)]}
# PPCOD
ncr = ('GURUGRAM', 'GURGAON', 'NOIDA', 'GHAZIABAD', 'FARIDABAD', 'GREATER NOIDA', 'GAUTAM BUDDHA NAGAR')
def reg(x):
    s, c = x['Billing State'].upper(), x['Billing City'].upper()
    if 'WEST BENGAL' in s: return 'WB'
    if s == 'DELHI' or any(n in c for n in ncr): return 'NCR'
def elig(x):
    r, v = reg(x), num(x['Grand Total'])
    return (r == 'WB' and 2000 <= v <= 20000) or (r == 'NCR' and 5000 <= v <= 20000)
pp = [x for x in ok if x['Payment Status'] == 'Partial Paid']; pre = [x for x in ok if elig(x) and x['Payment Status'] != 'Partial Paid']
rows = []
for r, lab in (('WB', 'West Bengal (₹2–20k)'), ('NCR', 'Delhi NCR (₹5–20k)')):
    e = [x for x in ok if reg(x) == r and elig(x)]; p = [x for x in e if x['Payment Status'] == 'Partial Paid']; q = [x for x in e if x not in p]
    rows.append([lab, len(e), len(p), round(st.mean(num(x['Grand Total']) for x in p)) if p else 0, round(st.mean(num(x['Grand Total']) for x in q)) if q else 0])
rt = lambda s: sum('rto' in x['Order Shipment Status'] for x in s)
ppcod = {'n': len(pp), 'rows': rows, 'rto': pc(rt(pp), len(pp)), 'rtoN': rt(pp), 'rtoPre': pc(rt(pre), len(pre)), 'rtoPreN': f'{rt(pre)} / {len(pre)}',
         'pending': sum(x['Merchant Order Status'] == 'pending' for x in pp), 'noShip': sum(not x['Order Shipment Status'] for x in pp),
         'delivered': sum(x['Order Shipment Status'] in ('delivered', 'partial delivered') for x in pp)}
out = {'meta': {'from': A.isoformat(), 'to': B.isoformat(), 'orders': len(OS), 'carts': len(CS), 'checkouts': sum(v[0] for v in fs.values()), 'txns': len(T)},
       'pay': pay, 'basket': basket, 'combos': combos, 'cust': cust, 'rto': rto, 'bands': bandrows, 'rec': recd, 'pool': pool, 'fun': fun, 'txn': txn, 'snap': snap, 'ppcod': ppcod}
blob = json.dumps(out, separators=(',', ':'), ensure_ascii=False)
for bad in ('@', '+91'): assert bad not in blob, bad
open(os.environ.get('OUT', '/home/claude/sc/repo/data/gk_deep.js'), 'w').write('// GoKwik deep dive — generated by sale/build_gk_deep.py from GoKwik exports. Aggregates only, no customer data.\nwindow.SC_GK = ' + blob + ';\n')
print(json.dumps(out, ensure_ascii=False)[:6000])
