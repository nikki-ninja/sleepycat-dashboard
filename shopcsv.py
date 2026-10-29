"""Emulates the RAW_SHOPIFY_SLEEPYCAT queries in scripts/build_data.py from the two Shopify CSV exports
(my Snowflake role cannot read that schema). Dedupe: latest _extracted_at per DAY(+SOURCE+MEDIUM+CAMPAIGN)."""
import csv, json, datetime, re
from collections import defaultdict
D = lambda s: datetime.date.fromisoformat(s)
class Shop:
    def __init__(self, sess_csv, utm_csv, today, null_medium_excluded=True):
        self.today = today; self.nme = null_medium_excluded
        best = {}
        for r in csv.DictReader(open(sess_csv, encoding='utf-8-sig')):
            j = json.loads(r['VALUE']); d = j['day']
            if d not in best or j['_extracted_at'] > best[d]['_extracted_at']: best[d] = j
        self.daily = {d: (int(j['sessions']), int(j['sessions_with_cart_additions']), float(j['bounce_rate'])) for d, j in best.items()}
        bu = {}
        for r in csv.DictReader(open(utm_csv, encoding='utf-8-sig')):
            j = json.loads(r['VALUE']); k = (j['day'], j.get('utm_source'), j.get('utm_medium'), j.get('utm_campaign'))
            if k not in bu or j['_extracted_at'] > bu[k]['_extracted_at']: bu[k] = j
        self.utm = [(k[0], k[1], k[2], k[3], int(j['sessions']), int(j['sessions_with_cart_additions'])) for k, j in bu.items()]
    def rows(self, a=None, b=None, excl_checkout=False):
        for d, s, m, c, se, at in self.utm:
            if a and d < a: continue
            if b and d > b: continue
            if excl_checkout:
                if m is None and self.nme: continue          # NULL <> 'CHECKOUT' is NULL -> filtered in Snowflake
                if (m or '').upper() == 'CHECKOUT': continue
            yield d, s, m, c, se, at
    @staticmethod
    def k(s, m): return ((s or '').strip().upper() or 'UNATTRIB') + '/' + (m or '').strip().upper()
    @staticmethod
    def bucket(s, m):
        s, m = (s or '').upper(), (m or '').upper()
        if m in ('CPC','TOFU','BOFU','PAID','MOFU','PRODUCT_SYNC','AFFILIATE','RETARGETING'): return 'PAID'
        if m in ('CLEVERTAP','CAMPAIGN','EMAIL','SMS','WHATSAPP','PUSH') or s in ('EMAIL','WHATSAPP','OTCRM'): return 'OWNED'
        return 'ORGANIC'
    def answer(self, sql):
        T = self.today; ad = lambda n: (T + datetime.timedelta(days=n)).isoformat()
        wk0 = T - datetime.timedelta(days=T.weekday())
        if "THEN 'PAID'" in sql:
            n = int(re.search(r'DATEADD\(day, -(\d+), CURRENT_DATE\)', sql).group(1)); out = defaultdict(int)
            for d, s, m, c, se, at in self.rows(ad(-n), None, True): out[(d, self.bucket(s, m))] += se
            return [[d, b, v] for (d, b), v in out.items()]
        if "DATE_TRUNC('WEEK', DAY)" in sql:
            n = int(re.search(r'DATEADD\(week, -(\d+)', sql).group(1)); a = (wk0 - datetime.timedelta(weeks=n)).isoformat(); out = defaultdict(int)
            for d, s, m, c, se, at in self.rows(a, None, True):
                w = D(d) - datetime.timedelta(days=D(d).weekday()); out[(w.isoformat(), self.k(s, m))] += se
            return [[w, k, v] for (w, k), v in out.items()]
        if "UPPER(UTM_MEDIUM)='TOFU'" in sql:
            n = int(re.search(r'DATEADD\(day, -(\d+), CURRENT_DATE\)', sql).group(1)); out = defaultdict(int)
            for d, s, m, c, se, at in self.rows(ad(-n)):
                if (s or '').upper() == 'FACEBOOK' and (m or '').upper() == 'TOFU': out[d] += se
            return [[d, v] for d, v in out.items()]
        if "'_other'" in sql:
            n = int(re.search(r'DATEADD\(day, -(\d+), CURRENT_DATE\)', sql).group(1))
            tracked = re.search(r"WHEN k IN \(([^)]*)\)", sql).group(1).replace("'", '').split(','); out = defaultdict(int)
            for d, s, m, c, se, at in self.rows(ad(-n), None, True):
                k = self.k(s, m); kk = k if k in tracked else 'UNATTRIB/' if k == 'UNATTRIB/' else '_other'; out[(d, kk)] += se
            return [[d, k, v] for (d, k), v in out.items()]
        if 'BOUNCE_RATE' in sql:
            a, b = re.search(r"BETWEEN '([\d-]+)' AND '([\d-]+)'", sql).groups()
            return [[d, v[0], v[1], v[2]] for d, v in self.daily.items() if a <= d <= b]
        if "TO_CHAR(DAY, 'YYYY-MM')" in sql:
            a, b = re.search(r"BETWEEN '([\d-]+)' AND '([\d-]+)'", sql).groups(); out = defaultdict(lambda: [0, 0])
            for d, s, m, c, se, at in self.rows(a, b):
                e = out[(d[:7], self.k(s, m))]; e[0] += se; e[1] += at
            return [[mo, k, v[0], v[1]] for (mo, k), v in out.items()]
        raise ValueError('unhandled shopify query: ' + sql[:200])
