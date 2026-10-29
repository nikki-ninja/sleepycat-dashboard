"""Runs repo/scripts/build_data.py unchanged, with a cursor that answers MAPLEMONK SQL from the Snowflake
cache (sfcache) and RAW_SHOPIFY SQL from the CSV exports (shopcsv). CURRENT_DATE is pinned to TODAY.
usage: python3 run_main.py <sessions.csv> <utm.csv> <today YYYY-MM-DD>   -> pending/*.sql if anything is uncached"""
import sys, os, re, json, datetime, types, glob
sys.path.insert(0, '/home/claude/sc/build'); sys.path.insert(0, '/home/claude/sc/repo/scripts')
import sfcache, shopcsv
SESS, UTM, TODAY = sys.argv[1], sys.argv[2], datetime.date.fromisoformat(sys.argv[3])
shop = shopcsv.Shop(SESS, UTM, TODAY, null_medium_excluded=os.environ.get('NME', '0') == '1')
pending = []
def conv(v):
    if v is None or not isinstance(v, str): return v
    if re.fullmatch(r'-?\d+', v): return int(v)
    if re.fullmatch(r'-?\d*\.\d+(e-?\d+)?', v): return float(v)
    return v
def pin(sql): return sql.replace('CURRENT_DATE', f"'{TODAY.isoformat()}'::DATE")
def mapl(sql):
    sql = pin(sql); r = sfcache.get(sql)
    if r is None: pending.append(sql); return []
    return [[conv(x) for x in row] for row in r]
class Cur:
    def execute(self, sql):
        if 'RAW_SHOPIFY_SLEEPYCAT' in sql:
            if 'SLEEPYCAT_DB_ORDERS' in sql:       # daily funnel: sessions (CSV) LEFT JOIN orders (Snowflake)
                o = re.search(r'\), o AS \((.*?)GROUP BY 1\)', sql, re.S).group(1) + 'GROUP BY 1'
                orows = {str(r[0]): r for r in mapl("SELECT TO_VARCHAR(d), orders, ROUND(sales), pos_orders, ROUND(pos_sales), gk_orders, ROUND(gk_sales) FROM (" + o + ")")}
                n = int(re.search(r'DATEADD\(day, -(\d+), CURRENT_DATE\)', sql).group(1)); a = (TODAY - datetime.timedelta(days=n)).isoformat()
                out = []
                for d in sorted(shop.daily, reverse=True):
                    if d < a: continue
                    se, at, _ = shop.daily[d]; r = orows.get(d, [d, 0, 0, 0, 0, 0, 0])
                    out.append([d, se, at, r[1] or 0, r[2] or 0, r[3] or 0, r[4] or 0, r[5] or 0, r[6] or 0])
                self.r = out
            else: self.r = shop.answer(sql)
        else: self.r = mapl(sql)
    def fetchall(self): return self.r
    def close(self): pass
class Cn:
    def cursor(self): return Cur()
    def close(self): pass
sys.modules['snowflake'] = types.ModuleType('snowflake'); conn = types.ModuleType('snowflake.connector'); conn.connect = lambda **k: Cn()
sys.modules['snowflake.connector'] = conn; sys.modules['snowflake'].connector = conn
for k in ('SNOWFLAKE_ACCOUNT', 'SNOWFLAKE_USER', 'SNOWFLAKE_PASSWORD'): os.environ.setdefault(k, 'x')
import builtins, datetime as _dt
class FD(_dt.date):
    @classmethod
    def today(cls): return TODAY
_dt.date = FD
os.chdir('/home/claude/sc/repo')
import build_data
try:
    build_data.main()
except SystemExit as e: print('exit:', e)
except Exception as e:
    if not pending: raise
    print('stopped early:', type(e).__name__, e)
if pending:
    for f in glob.glob('/home/claude/sc/build/pending/*.sql'): os.remove(f)
    seen = set()
    for i, s in enumerate(pending):
        k = sfcache.key(s)
        if k in seen: continue
        seen.add(k); open(f'/home/claude/sc/build/pending/{k}.sql', 'w').write(s)
    print('PENDING', len(seen))
