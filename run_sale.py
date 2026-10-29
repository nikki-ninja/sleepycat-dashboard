"""Collects the sale extracts from the Snowflake cache into <dfolder>; writes pending/*.sql for anything uncached."""
import sys, os, json, glob
sys.path.insert(0, '/home/claude/sc/build'); sys.path.insert(0, '/home/claude/sc/sale')
import sfcache, sale_sql
T, DF = sys.argv[1], sys.argv[2].rstrip('/') + '/'
os.makedirs(DF, exist_ok=True); pend = []
for f in glob.glob('/home/claude/sc/build/pending/*.sql'): os.remove(f)
for name, sqls in sale_sql.get(T).items():
    rows = []
    for s in sqls:
        r = sfcache.get(s)
        if r is None: pend.append(s); open(f'/home/claude/sc/build/pending/{sfcache.key(s)}.sql', 'w').write(s); continue
        if len(r) >= 4000: sys.exit(f'{name}: 4000-row cap hit — split the query')
        rows += r
    json.dump({'rows': rows}, open(DF + name + '.json', 'w'))
print('pending', len(pend)); print(' '.join(sfcache.key(s) + '.sql' for s in pend))
