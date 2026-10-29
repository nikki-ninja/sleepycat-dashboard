"""Builds repo/data/sale_data.js (window.SC_SALE) for sale.html — the Diwali sale analytics dashboard.

Inputs (one folder per build):  python3 build_sale_dash.py <dfolder> <utm_csv> <through YYYY-MM-DD>
  <dfolder>/s_*.json        Snowflake extracts (see sale_sql.md / the q_s_*.sql files)
  sale/shop/all.json        ShopifyQL results (landing pages, regions, cities, devices)
  sessions.json             Shopify daily sessions/ATC/bounce (from the sessions CSV)
  repo/data/data.json       main dashboard data (DAILY = orders/revenue, D2C + stores)

Periods
  BAU   = Sep 1-21 + Oct 1-6, 2026 (27 days). Sep 22-30 is left out: a Google CPC surge inflated sessions ~5x.
  EVE   = Oct 7 (launch eve; the sale went live at midnight). Shown in day tables, not in sale totals.
  SALE  = Oct 8 onward (full sale days). All "sale" totals, per-day averages and uplifts use these days.
  Sale weeks run Wednesday-Tuesday from Oct 7: W1 = Oct 7-13, W2 = Oct 14-20, ...
"""
import json, csv, sys, datetime, re
from collections import defaultdict

DF, UTM_CSV, THROUGH = sys.argv[1].rstrip('/') + '/', sys.argv[2], sys.argv[3]
ROOT = '/home/claude/sc/'
T = datetime.date.fromisoformat(THROUGH)
EVE, START, END, DIWALI = datetime.date(2026, 10, 7), datetime.date(2026, 10, 8), datetime.date(2026, 11, 21), datetime.date(2026, 11, 8)
TARGET = 8_000_000
iso = lambda d: d.isoformat()
def drange(a, b):
    while a <= b: yield a; a += datetime.timedelta(days=1)
BAU = [iso(d) for d in drange(datetime.date(2026, 9, 1), datetime.date(2026, 9, 21))] + [iso(d) for d in drange(datetime.date(2026, 10, 1), datetime.date(2026, 10, 6))]
BAUS = set(BAU); NB = len(BAU)
SALE = [iso(d) for d in drange(START, min(T, END))]; SALES = set(SALE); NS = len(SALE)
def per(d):
    if d in BAUS: return 'BAU'
    if d == iso(EVE): return 'EVE'
    if d in SALES: return 'SALE'
    return 'X'
def week(d):
    k = (datetime.date.fromisoformat(d) - EVE).days // 7
    return 'W%d' % (k + 1) if k >= 0 else None
L = lambda n: json.load(open(DF + n + '.json'))['rows']
f = lambda x: float(x or 0)
num = lambda s: float(str(s).replace(',', '').strip() or 0)

main = json.load(open(ROOT + 'repo/data/data.json'))
DAILY = {r['date']: r for r in main['DAILY']}
sess = json.load(open(ROOT + 'sessions.json'))
ALL_DAYS = [iso(d) for d in drange(datetime.date(2026, 9, 1), T)]

# ---------- UTM sessions by source/medium and campaign (Shopify export) ----------
src_s = defaultdict(lambda: defaultdict(lambda: [0, 0]))      # d -> 'SRC/MED' -> [sessions, atc]
camp_s = defaultdict(lambda: defaultdict(lambda: [0, 0]))     # per -> campaign -> [sessions, atc]
for raw in csv.DictReader(open(UTM_CSV, encoding='utf-8-sig')):
    try: d = datetime.datetime.strptime(raw['DAY'].strip(), '%B %d, %Y').strftime('%Y-%m-%d')
    except Exception: continue
    if d < '2026-09-01' or d > THROUGH: continue
    us = (raw['UTM_SOURCE'] or '').strip().upper() or 'UNATTRIB'; um = (raw['UTM_MEDIUM'] or '').strip().upper()
    if um == 'CHECKOUT': continue
    s, a = num(raw['SESSIONS']), num(raw['SESSIONS_WITH_CART_ADDITIONS'])
    k = us + '/' + um; e = src_s[d][k]; e[0] += s; e[1] += a
    c = (raw['UTM_CAMPAIGN'] or '').strip()
    if c: e2 = camp_s[per(d)][c]; e2[0] += s; e2[1] += a

# ---------- orders by source/medium/campaign ----------
src_o = defaultdict(lambda: defaultdict(lambda: [0, 0]))      # d -> key -> [orders, rev]
camp_o = defaultdict(lambda: defaultdict(lambda: [0, 0]))     # per -> campaign -> [orders, rev]
for d, s, m, c, n, r in L('s_utm'):
    k = s + '/' + m; e = src_o[d][k]; e[0] += int(n); e[1] += f(r)
    if c: e2 = camp_o[per(d)][c.strip()]; e2[0] += int(n); e2[1] += f(r)
for p_, s_, m_, c, n, r in L('s_utm_camp'):           # campaign level, pre-aggregated by period
    if c: e2 = camp_o[p_][c.strip()]; e2[0] += int(n); e2[1] += f(r)

def keymap(k):
    if k in ('UNATTRIB/', 'DIRECT/', 'UNATTRIB/(NONE)'): return 'Direct / untagged'
    return k
PROS = ('GOOGLE/CPC', 'FACEBOOK/TOFU')

# ---------- GA4 ----------
ga = {datetime.datetime.strptime(r[0], '%Y%m%d').strftime('%Y-%m-%d'): r for r in L('s_ga4')}

# ---------- day-level payments / cancellations / discounts ----------
dd = defaultdict(lambda: defaultdict(float))
for d, ch, gw, n, canc, r, disc, coded in L('s_day'):
    e = dd[d]; n = int(n)
    if ch in ('G', 'R'):
        e['canc'] += int(canc); e['disc'] += f(disc); e['coded'] += int(coded)
        g = gw.lower()
        if ch == 'G':      # only GoKwik records the payment method on the order; Razorpay orders just say "Razorpay"
            kind = 'UPI' if 'upi' in g else 'Card EMI' if 'emi' in g else 'Cards' if 'card' in g else 'Pay later (Snapmint)' if 'snapmint' in g else 'COD' if 'cod' in g or 'cash' in g else 'Wallets & other'
        else:
            kind = 'Razorpay'
        e['pay:' + kind] += n
    else:
        e['s_canc'] += int(canc)
codes = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))   # per -> code -> [orders, discount, revenue] (website only)
for d, ch, code, n, disc, r in L('s_disc'):
    if ch != 'W' or not code: continue
    e = codes[d if d in ('BAU', 'SALE', 'EVE', 'X') else per(d)][code]; e[0] += int(n); e[1] += f(disc); e[2] += f(r)
nr = defaultdict(lambda: defaultdict(int))
for d, ch, fl, n, r in L('s_nr'):
    nr[d][ch + ':' + fl] += int(n); nr[d][ch + ':' + fl + ':r'] += f(r)
mk = defaultdict(lambda: defaultdict(float))
for d, ch, sp, im, cl, cv, cvv, srev in L('s_mkt_day'):
    mk[d][ch + ':sp'] += f(sp); mk[d][ch + ':cvv'] += f(cvv); mk[d][ch + ':cl'] += f(cl); mk[d][ch + ':im'] += f(im)

# ---------- basket masks ----------
B = {'Mattress': 1, 'Bedding': 2, 'Pillow': 4, 'Pillow case': 8, 'Pet': 16, 'Furniture': 32, 'Ergo & other': 64, 'Protector': 128, 'Topper': 256}
ACC = 2 | 4 | 8 | 128 | 256
bk = defaultdict(lambda: defaultdict(float))
for d, ch, n, u, r, m, m_acc, m_acc_xp, acc_only in L('s_basket'):   # aggregated in SQL per day x channel
    e = bk[d + ':' + ch]
    e['orders'] += int(n); e['units'] += f(u); e['rev'] += f(r); e['m'] += int(m); e['m_acc'] += int(m_acc)
    e['m_acc_xp'] += int(m_acc_xp); e['acc_only'] += int(acc_only)

# ---------- days ----------
days = []
for d in ALL_DAYS:
    r = DAILY.get(d); s = sess.get(d)
    if not r or not s: continue
    g = ga.get(d)
    so = src_o.get(d, {}); ss = src_s.get(d, {})
    ps = sum(ss.get(k, [0, 0])[0] for k in PROS); po = sum(so.get(k, [0, 0])[0] for k in PROS)
    w, st = bk.get(d + ':W', {}), bk.get(d + ':S', {})
    e = {'d': d, 'per': per(d), 'wk': week(d),
         'sess': s['sessions'], 'atc': s['atc'], 'bounce': round(s.get('bounce', 0) * 100, 1),
         'gaS': int(g[1]) if g else None, 'gaAtc': int(g[3]) if g else None, 'gaCk': int(g[4]) if g else None,
         'wo': r['orders'], 'wr': r['sales'], 'so': r['pos_orders'], 'sr': r['pos_sales'], 'gk': r['gk_orders'],
         'proS': round(ps), 'proO': po,
         'wm': int(w.get('m', 0)), 'sm': int(st.get('m', 0)), 'wmAcc': int(w.get('m_acc', 0)), 'wmAccXp': int(w.get('m_acc_xp', 0)),
         'smAcc': int(st.get('m_acc', 0)), 'wAccOnly': int(w.get('acc_only', 0)), 'wUnits': int(w.get('units', 0)),
         'canc': int(dd[d]['canc']), 'disc': round(dd[d]['disc']), 'coded': int(dd[d]['coded']),
         'pay': {k[4:]: int(v) for k, v in dd[d].items() if k.startswith('pay:')},
         'wNew': nr[d].get('W:New', 0), 'wRep': nr[d].get('W:Repeat', 0), 'sNew': nr[d].get('S:New', 0), 'sRep': nr[d].get('S:Repeat', 0),
         'meta': round(mk[d]['FACEBOOK:sp']), 'google': round(mk[d]['GOOGLE:sp']), 'metaVal': round(mk[d]['FACEBOOK:cvv']), 'googleVal': round(mk[d]['GOOGLE:cvv'])}
    days.append(e)

# ---------- hourly ----------
hr = defaultdict(lambda: [0] * 24)
for d, h, ch, n, r in L('s_hour'):
    if ch == 'W': hr[d][int(h)] += int(n)
hourly = {'bau': [round(sum(hr[d][h] for d in BAU) / NB, 1) for h in range(24)], 'days': {d: hr[d] for d in [iso(x) for x in drange(EVE, T)]}}

# ---------- products ----------
def pnorm(p):
    p = p.replace('\xa0', ' ').strip()
    fix = {'THE-LATEX-ORTHO-MATTRESS': 'LATEX ORTHO MATTRESS', 'THE LATEX ORTHO': 'LATEX ORTHO MATTRESS', "THE FOUNDER'S MATTRESS": "FOUNDER'S MATTRESS",
           '2 INCH MEMORY FOAM MATTRESS TOPPER': 'MEMORY FOAM MATTRESS TOPPER - 2 INCH', 'TRI FOLD MATTRESS ': 'TRI FOLD MATTRESS', 'MATTRESSES': 'MATTRESS (UNMAPPED SKU)'}
    p = fix.get(p, p)
    return p.title().replace("'S", "'s").replace('Tc ', 'TC ').replace(' - ', ' · ')
def gnorm(g, p):
    return 'Protector' if 'PROTECTOR' in p.upper() else g
prod = defaultdict(lambda: {'g': '', 'bau': [0, 0, 0, 0], 'sale': [0, 0, 0, 0], 'days': defaultdict(lambda: [0, 0, 0, 0])})
for d, ch, g, p, o, u, r in L('s_prod'):           # BAU rows come pre-aggregated (d == 'BAU')
    pr = d if d in ('BAU', 'SALE', 'EVE', 'X') else per(d)
    if pr == 'X': continue
    name = pnorm(p); e = prod[name]; e['g'] = gnorm(g, p)
    i = 0 if ch == 'W' else 2; vals = (int(o), f(r))
    if pr == 'BAU': e['bau'][i] += vals[0]; e['bau'][i + 1] += vals[1]
    if pr == 'SALE': e['sale'][i] += vals[0]; e['sale'][i + 1] += vals[1]
    if pr in ('SALE', 'EVE'): x = e['days'][d]; x[i] += vals[0]; x[i + 1] += vals[1]
products = []
for k, e in prod.items():
    products.append({'p': k, 'g': e['g'], 'bau': [round(x / NB, 2) for x in e['bau']], 'sale': [round(x / max(NS, 1), 2) for x in e['sale']],
                     'saleTot': [round(x) for x in e['sale']], 'days': {d: [round(v) for v in x] for d, x in e['days'].items()}})
products.sort(key=lambda x: -(x['saleTot'][1] + x['saleTot'][3]))

# ---------- geography ----------
SREG = {'National Capital Territory of Delhi': 'DELHI', 'Jammu and Kashmir': 'JAMMU AND KASHMIR'}
shop = json.load(open(ROOT + 'sale/shop/all.json'))
def sq(dim, a, b):
    for q, v in shop.items():
        if f'GROUP BY {dim} ' in q + ' ' and f'SINCE {a} UNTIL {b}' in q and 'landing' not in q: return v['rows']
    return None
def sq_lp(a, b):
    for q, v in shop.items():
        if 'landing_page_path' in q and f'SINCE {a} UNTIL {b}' in q and 'completed' not in q: return v['rows']
    return None
BAU_WIN = [('2026-09-01', '2026-09-21'), ('2026-10-01', '2026-10-06')]
import re as _re
_until = sorted({_re.search(r'UNTIL (\S+)', q).group(1) for q in shop if 'SINCE 2026-10-08 UNTIL' in q and 'session_region' in q})
SHOP_TO = _until[-1] if _until else THROUGH
SALE_WIN = ('2026-10-08', SHOP_TO)
NSH = (datetime.date.fromisoformat(SHOP_TO) - START).days + 1          # days covered by Shopify session data
LP_DAYS = [d for d in SALE if sq_lp(d, d)]; NLP = max(len(LP_DAYS), 1)
def sessions_by(dim, norm=lambda x: x):
    out = {'bau': defaultdict(lambda: [0, 0]), 'sale': defaultdict(lambda: [0, 0])}
    for a, b in BAU_WIN:
        for k, s, at in (sq(dim, a, b) or []):
            if k: e = out['bau'][norm(k)]; e[0] += int(s); e[1] += int(at)
    for k, s, at in (sq(dim, *SALE_WIN) or []):
        if k: e = out['sale'][norm(k)]; e[0] += int(s); e[1] += int(at)
    return out
reg = sessions_by('session_region', lambda k: SREG.get(k, k.upper()))
st = defaultdict(lambda: {'bau': [0, 0, 0], 'sale': [0, 0, 0], 'so': [0, 0]})
for d, ch, s, n, r, m in L('s_geo_state'):
    pr = d if d in ('BAU', 'SALE', 'EVE', 'X') else per(d)
    if pr not in ('BAU', 'SALE'): continue
    if ch == 'W':
        e = st[s][pr.lower()]; e[0] += int(n); e[1] += f(r); e[2] += int(m)
    elif pr == 'SALE': st[s]['so'][0] += int(n); st[s]['so'][1] += f(r)
states = []
for s, e in st.items():
    if s in ('NA', ''): continue
    bs, ss = reg['bau'].get(s), reg['sale'].get(s)
    states.append({'s': s.title().replace(' And ', ' & '), 'bau': [round(e['bau'][0] / NB, 2), round(e['bau'][1] / NB), round(e['bau'][2] / NB, 2)],
                   'sale': [round(e['sale'][0] / max(NS, 1), 2), round(e['sale'][1] / max(NS, 1)), round(e['sale'][2] / max(NS, 1), 2)],
                   'saleTot': [e['sale'][0], round(e['sale'][1])], 'store': [round(e['so'][0] / max(NS, 1), 2), round(e['so'][1] / max(NS, 1))],
                   'sessB': [round(bs[0] / NB), round(bs[1] / NB)] if bs else None, 'sessS': [round(ss[0] / NSH), round(ss[1] / NSH)] if ss else None})
states.sort(key=lambda x: -x['saleTot'][1])
CITYN = {'BANGALORE': 'Bengaluru', 'BENGALURU': 'Bengaluru', 'GURGAON': 'Gurugram', 'GAUTAM BUDDHA NAGAR': 'Noida (G.B. Nagar)'}
ct = defaultdict(lambda: {'st': '', 'bau': [0, 0, 0], 'sale': [0, 0, 0]})
for p_, ch, c, s, n, r, m in L('s_geo_city'):
    if ch != 'W' or p_ not in ('BAU', 'SALE'): continue
    name = CITYN.get(c, c.title()); e = ct[name]; e['st'] = s.title()
    x = e[p_.lower()]; x[0] += int(n); x[1] += f(r); x[2] += int(m)
cities = [{'c': c, 'st': e['st'], 'bau': [round(e['bau'][0] / NB, 2), round(e['bau'][1] / NB)], 'sale': [round(e['sale'][0] / max(NS, 1), 2), round(e['sale'][1] / max(NS, 1)), e['sale'][2]], 'saleTot': e['sale'][0]}
          for c, e in ct.items() if e['sale'][0] >= 3]
cities.sort(key=lambda x: -x['saleTot'])
cs = sessions_by('session_city')
city_sess = [{'c': k, 'bau': [round(v[0] / NB), round(v[1] / NB)] if (v := cs['bau'].get(k)) else None, 'sale': [round(s[0] / NSH), round(s[1] / NSH)]}
             for k, s in sorted(cs['sale'].items(), key=lambda x: -x[1][0])]
dev = sessions_by('session_device_type')
devices = [{'k': k, 'bau': [round(dev['bau'][k][0] / NB), round(dev['bau'][k][1] / NB)], 'sale': [round(v[0] / NSH), round(v[1] / NSH)]} for k, v in dev['sale'].items() if k in ('mobile', 'desktop', 'tablet')]

# ---------- landing pages ----------
lp = {'bau': defaultdict(lambda: [0, 0, 0]), 'sale': defaultdict(lambda: [0, 0, 0])}
for a, b in BAU_WIN:
    for k, s, at, ck in (sq_lp(a, b) or []):
        e = lp['bau'][k.rstrip('/') or '/']; e[0] += int(s); e[1] += int(at); e[2] += int(ck)
for d in LP_DAYS:
    for k, s, at, ck in (sq_lp(d, d) or []):
        e = lp['sale'][k.rstrip('/') or '/']; e[0] += int(s); e[1] += int(at); e[2] += int(ck)
HANDLE = {'/products/latex-mattress': 'Hybrid Latex Mattress', '/products/original-mattress': 'Original Mattress', '/products/carbon-mattress': 'Carbon Mattress',
          '/products/ultima-natural-latex-mattress': 'Ultima Natural Latex Mattress', '/products/the-latex-ortho-mattress': 'Latex Ortho Mattress',
          '/products/tri-fold-mattress': 'Tri Fold Mattress', '/products/cloud-mattress': 'Cloud Mattress',
          '/products/founders-mattress': "Founder's Mattress", '/products/microfiber-mattress-topper': 'Microfiber Mattress Topper',
          '/products/memory-foam-mattress-topper': 'Memory Foam Mattress Topper · 2 Inch', '/products/latex-mattress-topper': 'Natural Latex Mattress Topper',
          '/products/aeroflow-foam-mattress-topper': 'Aeroflow Mattress Topper', '/products/pregnancy-body-pillow': 'Cuddle Pillow',
          '/products/memory-foam-pillow': 'Softtouch Memory Foam Pillow', '/products/contour-softtouch-memory-foam-pillow': 'Contour Softtouch Memory Foam Pillow',
          '/products/150-gsm-cotton-soft-microfiber-sheet-set': '150 Gsm Cotton-Soft Microfiber Sheet Set', '/products/percale-fitted-bedsheet-set': '200 TC Percale Fitted Bedsheet Set',
          '/products/mattress-protector': 'Mattress Protector', '/products/noa-recliner': 'Noa Recliner', '/products/ohayo-bed-with-storage': 'Ohayo Bed',
          '/products/katachi-bed-with-storage': 'Katachi Bed'}
pidx = {x['p']: x for x in products}
pages = []
for k in set(lp['sale']) | set(lp['bau']):
    sv, bv = lp['sale'].get(k), lp['bau'].get(k)
    if not sv: continue
    pm = pidx.get(HANDLE.get(k, ''))
    pages.append({'k': k, 'sale': [round(sv[0] / NLP), round(sv[1] / NLP, 1)], 'bau': [round(bv[0] / NB), round(bv[1] / NB, 1)] if bv else None,
                  'prod': HANDLE.get(k), 'pO': pm['sale'][0] if pm else None, 'pR': pm['sale'][1] if pm else None, 'pOb': pm['bau'][0] if pm else None})
pages.sort(key=lambda x: -x['sale'][0])

# ---------- sources & campaigns ----------
def agg_src(dset, n):
    s, o = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for d in dset:
        for k, v in src_s.get(d, {}).items(): e = s[keymap(k)]; e[0] += v[0]; e[1] += v[1]
        for k, v in src_o.get(d, {}).items(): e = o[keymap(k)]; e[0] += v[0]; e[1] += v[1]
    return {k: [round(s[k][0] / n), round(s[k][1] / n, 1), round(o[k][0] / n, 2), round(o[k][1] / n)] for k in set(s) | set(o)}
sb, ssale = agg_src(BAU, NB), agg_src(SALE, max(NS, 1))
srcs = [{'k': k, 'sale': ssale[k], 'bau': sb.get(k)} for k in ssale if ssale[k][2] >= 1 or ssale[k][0] >= 1000]
srcs.sort(key=lambda x: -x['sale'][3])
top_keys = [x['k'] for x in srcs[:8]]
src_daily = {k: [] for k in top_keys}
for d in ALL_DAYS:
    for k in top_keys:
        o = sum(v[0] for kk, v in src_o.get(d, {}).items() if keymap(kk) == k)
        s = sum(v[0] for kk, v in src_s.get(d, {}).items() if keymap(kk) == k)
        src_daily[k].append([o, round(s)])
camp_sp = defaultdict(lambda: {'sp': 0, 'pv': 0, 'ch': '', 'name': ''})   # key: campaign id AND upper-case name; sale window only (SQL)
for ch, cid, name, sp, cvv in L('s_mkt_camp'):
    for key in {cid, (name or '').strip().upper()}:
        if not key: continue
        e = camp_sp[key]; e['sp'] += f(sp); e['pv'] += f(cvv); e['ch'] = ch; e['name'] = name or cid
def cnorm(c): return c.strip().upper()
cs_sale = defaultdict(lambda: [0, 0])
for c, v in camp_s['SALE'].items(): e = cs_sale[cnorm(c)]; e[0] += v[0]; e[1] += v[1]
co_sale, co_bau = defaultdict(lambda: [0, 0]), defaultdict(int)
for c, v in camp_o['SALE'].items(): e = co_sale[cnorm(c)]; e[0] += v[0]; e[1] += v[1]
for c, v in camp_o['BAU'].items(): co_bau[cnorm(c)] += v[0]
camps = []
for c, v in co_sale.items():
    s = cs_sale.get(c, [0, 0]); sp = camp_sp.get(c)
    label = sp['name'] if sp and c.isdigit() else c
    camps.append({'c': label, 'id': c if c.isdigit() else None, 'o': v[0], 'r': round(v[1]), 's': round(s[0]), 'a': round(s[1]),
                  'sp': round(sp['sp']) if sp else None, 'pv': round(sp['pv']) if sp else None, 'ch': sp['ch'] if sp else None, 'oB': round(co_bau.get(c, 0) / NB, 2)})
camps.sort(key=lambda x: -x['o'])
# spend by campaign for the whole sale (incl. campaigns with no tracked orders)
spend_camps = sorted([{'c': v['name'], 'ch': v['ch'], 'sp': round(v['sp']), 'pv': round(v['pv'])} for k, v in camp_sp.items() if k.isdigit()], key=lambda x: -x['sp'])
code_rows = []
for c, v in codes['SALE'].items():
    b = codes['BAU'].get(c, [0, 0, 0])
    code_rows.append({'c': c, 'o': v[0], 'disc': round(v[1]), 'r': round(v[2]), 'oB': round(b[0] / NB, 2)})
code_rows.sort(key=lambda x: -x['o'])

out = {'meta': {'eve': iso(EVE), 'start': iso(START), 'end': iso(END), 'diwali': iso(DIWALI), 'through': THROUGH, 'target': TARGET, 'nBau': NB, 'nSale': NS,
                'bauLabel': 'Sep 1–21 + Oct 1–6 (27 days; Sep 22–30 Google CPC surge excluded)', 'generated': datetime.date.today().isoformat(), 'shopTo': SHOP_TO, 'lpTo': LP_DAYS[-1] if LP_DAYS else None},
       'days': days, 'hourly': hourly, 'products': products, 'states': states, 'cities': cities[:40], 'citySess': city_sess[:30], 'devices': devices,
       'pages': pages[:40], 'sources': srcs[:20], 'srcDaily': {'keys': top_keys, 'days': ALL_DAYS, 'v': src_daily}, 'campaigns': camps[:30], 'spendCamps': spend_camps[:25], 'codes': code_rows[:15]}
blob = json.dumps(out, separators=(',', ':'), ensure_ascii=False)
open(ROOT + 'repo/data/sale_data.js', 'w').write('// Generated by sale/build_sale_dash.py — do not edit by hand.\nwindow.SC_SALE = ' + blob + ';\n')
print('sale_data.js', len(blob) // 1024, 'KB', '| days', len(days), '| products', len(products), '| states', len(states), '| pages', len(pages), '| camps', len(camps))
