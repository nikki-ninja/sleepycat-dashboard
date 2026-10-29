"""Merges an earlier checkout_data.js with newer GoKwik exports when the earlier raw files are no longer available.
days: earlier build for days before SPLIT, newer build (ck_new_all) from SPLIT on (fresher recovery counts).
breakdowns: earlier SALE totals + increment (ck_new_inc, days after the earlier build's last day). Counts are additive;
top-N lists keep the union of keys, so a key outside the earlier top-N is slightly understated."""
import json, sys
ld = lambda f: (lambda t: json.loads(t[t.index('{'):t.rindex('}') + 1]))(open(f).read())
old, new, inc, SPLIT, OUT = ld(sys.argv[1]), ld(sys.argv[2]), ld(sys.argv[3]), sys.argv[4], sys.argv[5]
assert inc['meta']['from'] > old['meta']['to'], 'increment overlaps the earlier build'
K = dict(old)
K['days'] = [d for d in old['days'] if d['d'] < SPLIT] + [d for d in new['days'] if d['d'] >= SPLIT]
for k in ('pay', 'stage'):
    s = dict(old[k]['SALE'])
    for kk, v in inc[k]['SALE'].items(): s[kk] = s.get(kk, 0) + v
    K[k] = {'BAU': old[k]['BAU'], 'SALE': s}
for k in ('hourO', 'hourC'):
    K[k] = {'BAU': old[k]['BAU'], 'SALE': [a + b for a, b in zip(old[k]['SALE'], inc[k]['SALE'])]}
for k in ('src', 'lp', 'band', 'cust', 'risk', 'prod', 'code', 'matt'):
    m = {r[0]: list(r) for r in old[k]['SALE']}
    for r in inc[k]['SALE']:
        e = m.setdefault(r[0], [r[0], 0, 0, 0]); e[1] += r[1]; e[2] += r[2]; e[3] += r[3]
    K[k] = {'BAU': old[k]['BAU'], 'SALE': sorted(m.values(), key=lambda r: -(r[1] + r[2]))}
K['meta'] = dict(old['meta'], cut=new['meta']['cut'], partial=new['meta']['partial'], to=new['meta']['to'],
                 saleDays=[d['d'] for d in K['days'] if d['per'] == 'SALE'])
for k in ('fun', 'txn'): K.pop(k, None)
blob = json.dumps(K, separators=(',', ':'), ensure_ascii=False)
for bad in ('@', '+91'): assert bad not in blob
open(OUT, 'w').write('// Generated from GoKwik exports (sale/build_checkout.py + sale/merge_ck.py) — aggregates only.\nwindow.SC_CK = ' + blob + ';\n')
print('days', len(K['days']), K['meta']['to'], 'sale orders', sum(d.get('o', 0) for d in K['days'] if d['per'] == 'SALE'))
