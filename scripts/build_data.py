#!/usr/bin/env python3
"""
Regenerate data/data.js (and data.json) for the Sleepycat dashboard, straight from Snowflake.

Reads two schemas:
  RAW_SHOPIFY_SLEEPYCAT.SESSIONS_DAILY / SESSIONS_BY_UTM   -- Shopify sessions + ATC
  SLEEPYCAT_DB.MAPLEMONK.*                                 -- orders, attribution, GA4

Credentials come from environment variables (GitHub Actions secrets), never from the repo:
  SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
  SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE

Run locally:  pip install snowflake-connector-python && python scripts/build_data.py
"""
import os, json, datetime, sys
import snowflake.connector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mom   # month-on-month tabs

WINDOW_DAYS   = 75    # daily funnel table depth
UTM_WEEKS     = 8     # weekly per-source table depth
MIN_SESS      = 500   # below this a per-source CVR is not trustworthy
# SESSIONS_BY_UTM grain is DAY+SOURCE+MEDIUM+CAMPAIGN. SESSIONS_DAILY is confirmed one row
# per day (upsert); the UTM table has NOT been confirmed, so every read of it carries a
# QUALIFY dedupe. Duplicates there would inflate sessions and understate CVR. Once this
# returns nothing, the QUALIFY lines can go:
#   SELECT DAY,UTM_SOURCE,UTM_MEDIUM,UTM_CAMPAIGN,COUNT(*) FROM RAW_SHOPIFY_SLEEPYCAT.SESSIONS_BY_UTM
#   WHERE DAY >= DATEADD(day,-90,CURRENT_DATE) GROUP BY 1,2,3,4 HAVING COUNT(*)>1;
D2C   = "('256945782785','web','326345687041')"
GOKWIK = "'326345687041'"
POS    = "'266308321281'"

TRACKED = ('GOOGLE/CPC','FACEBOOK/TOFU','FACEBOOK/PAID','FACEBOOK/BOFU','SOCIAL/INSTAGRAM',
           'CHATGPT.COM/','WHATSAPP/CAMPAIGN','EMAIL/CLEVERTAP','GOOGLE/PRODUCT_SYNC')
TRACKED_SQL = ",".join(f"'{k}'" for k in TRACKED)

# Bucketing is defined once and injected into both the sessions and the orders query,
# because a CVR is only valid if numerator and denominator are bucketed identically.
def bucket_case(src_col, med_col):
    return f"""CASE
      WHEN UPPER({med_col}) IN ('CPC','TOFU','BOFU','PAID','MOFU','PRODUCT_SYNC','AFFILIATE','RETARGETING') THEN 'PAID'
      WHEN UPPER({med_col}) IN ('CLEVERTAP','CAMPAIGN','EMAIL','SMS','WHATSAPP','PUSH')
        OR UPPER({src_col}) IN ('EMAIL','WHATSAPP','OTCRM') THEN 'OWNED'
      ELSE 'ORGANIC' END"""

ORD_SRC = "UPPER(COALESCE(NULLIF(TRIM(gd.gs),''), NULLIF(TRIM(c.CHECKOUT_UTM_SOURCE),''),''))"
ORD_MED = "UPPER(COALESCE(NULLIF(TRIM(gd.gm),''), NULLIF(TRIM(c.CHECKOUT_UTM_MEDIUM),''),''))"
GD_CTE  = """gd AS (
  SELECT ID, MAX(GOKWIK_UTM_SOURCE) gs, MAX(GOKWIK_UTM_MEDIUM) gm
  FROM SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_GOKWIK_SOURCE GROUP BY 1)"""   # dupe IDs: must pre-aggregate

def utm_dedup(where):
    """SESSIONS_BY_UTM rows, one per DAY+SOURCE+MEDIUM+CAMPAIGN (latest extract). The dedupe must sit in a
    subquery: QUALIFY runs after GROUP BY, so putting it next to a GROUP BY is invalid SQL."""
    return f"""(SELECT * FROM RAW_SHOPIFY_SLEEPYCAT.SESSIONS_BY_UTM WHERE {where}
      QUALIFY ROW_NUMBER() OVER (PARTITION BY DAY, UTM_SOURCE, UTM_MEDIUM, UTM_CAMPAIGN ORDER BY EXTRACTED_AT DESC) = 1)"""

def q(cur, sql):
    cur.execute(sql)
    return cur.fetchall()

def main():
    cn = snowflake.connector.connect(
        account   = os.environ['SNOWFLAKE_ACCOUNT'],
        user      = os.environ['SNOWFLAKE_USER'],
        password  = os.environ['SNOWFLAKE_PASSWORD'],
        role      = os.environ.get('SNOWFLAKE_ROLE'),
        warehouse = os.environ.get('SNOWFLAKE_WAREHOUSE'),
    )
    cur = cn.cursor()

    # ---------- 1. daily funnel ----------
    rows = q(cur, f"""
    WITH s AS (
      SELECT DAY d, SESSIONS sessions, SESSIONS_WITH_CART_ADDITIONS atc
      FROM RAW_SHOPIFY_SLEEPYCAT.SESSIONS_DAILY
      WHERE DAY >= DATEADD(day, -{WINDOW_DAYS}, CURRENT_DATE)
    ), o AS (
      SELECT DATE(CONVERT_TIMEZONE('Asia/Kolkata', CREATED_AT)) d,
             COUNT_IF(SOURCE_NAME IN {D2C})                                  orders,
             SUM(IFF(SOURCE_NAME IN {D2C}, TOTAL_PRICE, 0))                   sales,
             COUNT_IF(SOURCE_NAME = {GOKWIK})                                 gk_orders,
             SUM(IFF(SOURCE_NAME = {GOKWIK}, TOTAL_PRICE, 0))                 gk_sales,
             COUNT_IF(SOURCE_NAME = {POS})                                    pos_orders,
             SUM(IFF(SOURCE_NAME = {POS}, TOTAL_PRICE, 0))                    pos_sales
      FROM SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_ORDERS
      WHERE CANCELLED_AT IS NULL
        AND DATE(CONVERT_TIMEZONE('Asia/Kolkata', CREATED_AT)) >= DATEADD(day, -{WINDOW_DAYS}, CURRENT_DATE)
      GROUP BY 1)
    SELECT TO_VARCHAR(s.d), s.sessions, s.atc,
           COALESCE(o.orders,0), ROUND(COALESCE(o.sales,0)),
           COALESCE(o.pos_orders,0), ROUND(COALESCE(o.pos_sales,0)),
           COALESCE(o.gk_orders,0), ROUND(COALESCE(o.gk_sales,0))
    FROM s LEFT JOIN o ON o.d = s.d ORDER BY s.d DESC""")

    DAILY = []
    for d, se, atc, o, sales, po, ps, gk, gks in rows:
        se, atc, o = int(se), int(atc), int(o)
        DAILY.append({"date": d, "sessions": se, "atc": atc, "orders": o, "sales": int(sales),
                      "atc_pct": round(atc/se*100, 2) if se else 0,
                      "c2o_pct": round(o/atc*100, 2) if atc else 0,
                      "cvr_pct": round(o/se*100, 2) if se else 0,
                      "pos_orders": int(po), "pos_sales": int(ps),
                      "gk_orders": int(gk), "gk_sales": int(gks)})
    if not DAILY:
        sys.exit("no daily rows returned — refusing to write an empty dashboard")

    # ---------- 2. paid / organic / owned, day-wise ----------
    sess_b = q(cur, f"""
      SELECT TO_VARCHAR(DAY), {bucket_case('UTM_SOURCE','UTM_MEDIUM')}, SUM(SESSIONS)
      FROM {utm_dedup(f"DAY >= DATEADD(day, -{WINDOW_DAYS}, CURRENT_DATE) AND UPPER(UTM_MEDIUM) <> 'CHECKOUT'")}
      GROUP BY 1,2""")
    ord_b = q(cur, f"""
      WITH {GD_CTE}
      SELECT TO_VARCHAR(DATE(CONVERT_TIMEZONE('Asia/Kolkata', o.CREATED_AT))),
             {bucket_case(ORD_SRC, ORD_MED)}, COUNT(*), ROUND(SUM(o.TOTAL_PRICE))
      FROM SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_ORDERS o
      LEFT JOIN SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_CHECKOUT_SOURCE c ON c.ID = o.ID
      LEFT JOIN gd ON gd.ID = o.ID
      WHERE o.SOURCE_NAME IN {D2C} AND o.CANCELLED_AT IS NULL
        AND DATE(CONVERT_TIMEZONE('Asia/Kolkata', o.CREATED_AT)) >= DATEADD(day, -{WINDOW_DAYS}, CURRENT_DATE)
      GROUP BY 1,2""")

    days = {}
    for d, b, s in sess_b:
        days.setdefault(d, {}).setdefault(b, {"s": 0, "o": 0, "r": 0})["s"] = int(s)
    for d, b, n, rev in ord_b:
        days.setdefault(d, {}).setdefault(b, {"s": 0, "o": 0, "r": 0}).update(o=int(n), r=int(rev))
    UTM_daily = [{"date": d, **{b: days[d].get(b, {"s": 0, "o": 0, "r": 0})
                                for b in ("PAID", "ORGANIC", "OWNED")}} for d in sorted(days)]

    # ---------- 3. weekly by source ----------
    sess_w = q(cur, f"""
      SELECT TO_VARCHAR(DATE_TRUNC('WEEK', DAY)::DATE),
             UPPER(COALESCE(NULLIF(TRIM(UTM_SOURCE),''),'UNATTRIB'))||'/'||UPPER(COALESCE(TRIM(UTM_MEDIUM),'')),
             SUM(SESSIONS)
      FROM {utm_dedup(f"DAY >= DATEADD(week, -{UTM_WEEKS}, DATE_TRUNC('WEEK', CURRENT_DATE)) AND UPPER(UTM_MEDIUM) <> 'CHECKOUT'")}
      GROUP BY 1,2""")
    ord_w = q(cur, f"""
      WITH {GD_CTE}
      SELECT TO_VARCHAR(DATE_TRUNC('WEEK', CONVERT_TIMEZONE('Asia/Kolkata', o.CREATED_AT))::DATE),
             CASE WHEN {ORD_SRC}||'/'||{ORD_MED} IN ({TRACKED_SQL})
                  THEN {ORD_SRC}||'/'||{ORD_MED} ELSE 'OTHER_POOL' END,
             COUNT(*), ROUND(SUM(o.TOTAL_PRICE))
      FROM SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_ORDERS o
      LEFT JOIN SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_CHECKOUT_SOURCE c ON c.ID = o.ID
      LEFT JOIN gd ON gd.ID = o.ID
      WHERE o.SOURCE_NAME IN {D2C} AND o.CANCELLED_AT IS NULL
        AND DATE(CONVERT_TIMEZONE('Asia/Kolkata', o.CREATED_AT))
            >= DATEADD(week, -{UTM_WEEKS}, DATE_TRUNC('WEEK', CURRENT_DATE))
      GROUP BY 1,2""")

    ws = {}
    for w, k, s in sess_w:
        ws.setdefault(w, {})[k] = float(s)
    wo = {}
    for w, k, n, rev in ord_w:
        wo.setdefault(w, {})[k] = [int(n), int(rev)]

    UTM_weekly = {}
    for w in sorted(ws):
        sess, ords = ws[w], wo.get(w, {})
        rows_, pool_o, pool_r = [], 0, 0
        for k in set(list(sess) + list(ords)):
            s = sess.get(k, 0.0); n, rev = ords.get(k, [0, 0])
            # untagged sessions, and any order key too thin to pair, go to one labelled blend
            if k == 'UNATTRIB/' or s < MIN_SESS:
                pool_o += n; pool_r += rev
                if k != 'UNATTRIB/':
                    continue
            else:
                rows_.append({"k": k, "s": int(round(s)), "o": n, "r": rev}); continue
        rows_.append({"k": "UNTAGGED (organic, direct & untracked)",
                      "s": int(round(sess.get('UNATTRIB/', 0))), "o": pool_o, "r": pool_r, "pool": 1})
        UTM_weekly[w] = sorted(rows_, key=lambda x: -x["o"])[:14]

    # ---------- 4. Facebook TOFU sessions, and GA4 weekly checkouts ----------
    TOFU = {d: int(s) for d, s in q(cur, f"""
      SELECT TO_VARCHAR(DAY), SUM(SESSIONS)
      FROM {utm_dedup(f"UPPER(UTM_SOURCE)='FACEBOOK' AND UPPER(UTM_MEDIUM)='TOFU' AND DAY >= DATEADD(day, -{WINDOW_DAYS+30}, CURRENT_DATE)")}
      GROUP BY 1""")}
    CK = {d: int(c) for d, c in q(cur, f"""
      SELECT TO_VARCHAR(DATE_TRUNC('WEEK', TO_DATE(DATE,'YYYYMMDD'))::DATE), SUM(CHECKOUTS)
      FROM SLEEPYCAT_DB.MAPLEMONK.GA4_SC_GA4_SESSIONS_BY_DATE_SOURCE
      WHERE TO_DATE(DATE,'YYYYMMDD') >= DATEADD(week, -{UTM_WEEKS}, DATE_TRUNC('WEEK', CURRENT_DATE))
      GROUP BY 1""")}

    # ---------- 5. source-wise CVR, last 21 days (feeds the table under the daily funnel) ----------
    src_days = 21
    ss = q(cur, f"""
      SELECT TO_VARCHAR(DAY),
             CASE WHEN k IN ({TRACKED_SQL}) THEN k WHEN k='UNATTRIB/' THEN 'UNATTRIB/' ELSE '_other' END,
             SUM(SESSIONS)
      FROM (SELECT DAY, SESSIONS,
                   UPPER(COALESCE(NULLIF(TRIM(UTM_SOURCE),''),'UNATTRIB'))||'/'||UPPER(COALESCE(TRIM(UTM_MEDIUM),'')) k
            FROM RAW_SHOPIFY_SLEEPYCAT.SESSIONS_BY_UTM
            WHERE DAY >= DATEADD(day, -{src_days}, CURRENT_DATE)
              AND UPPER(UTM_MEDIUM) <> 'CHECKOUT'
            QUALIFY ROW_NUMBER() OVER (PARTITION BY DAY, UTM_SOURCE, UTM_MEDIUM, UTM_CAMPAIGN
                                       ORDER BY EXTRACTED_AT DESC) = 1)
      GROUP BY 1,2""")
    so = q(cur, f"""
      WITH {GD_CTE}
      SELECT TO_VARCHAR(DATE(CONVERT_TIMEZONE('Asia/Kolkata', o.CREATED_AT))),
             CASE WHEN {ORD_SRC}||'/'||{ORD_MED} IN ({TRACKED_SQL})
                  THEN {ORD_SRC}||'/'||{ORD_MED} ELSE 'OTHER_POOL' END,
             COUNT(*)
      FROM SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_ORDERS o
      LEFT JOIN SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_CHECKOUT_SOURCE c ON c.ID = o.ID
      LEFT JOIN gd ON gd.ID = o.ID
      WHERE o.SOURCE_NAME IN {D2C} AND o.CANCELLED_AT IS NULL
        AND DATE(CONVERT_TIMEZONE('Asia/Kolkata', o.CREATED_AT)) >= DATEADD(day, -{src_days}, CURRENT_DATE)
      GROUP BY 1,2""")
    dss, dso = {}, {}
    for d, k, s in ss: dss.setdefault(d, {})[k] = int(s)
    for d, k, n in so: dso.setdefault(d, {})[k] = int(n)
    sdays = sorted(dss)[-src_days:]
    SRC = {"days": sdays, "rows": {k: [[dss[d].get(k, 0), dso.get(d, {}).get(k, 0)] for d in sdays] for k in TRACKED}}
    # untagged sessions pair with every order outside the tracked list — the same blend as the weekly table
    SRC["rows"]["UNTAGGED (organic, direct & untracked)"] = \
        [[dss[d].get('UNATTRIB/', 0), dso.get(d, {}).get('OTHER_POOL', 0)] for d in sdays]


    # ---------- 6. month-on-month blocks for every non-daily tab ----------
    # Window: last 4 calendar months, current one to date. Logic + SQL live in scripts/mom.py.
    through = mom.effective_through(datetime.date.fromisoformat(max(r["date"] for r in DAILY)))
    M, _, _, prm = mom.window(through)
    mrows = {name: q(cur, mom.sql(name, prm)) for name in mom.SQL}
    for name in ('ord_utm', 'mask', 'geo2', 'prod', 'meta'):
        if not mrows[name]: sys.exit(f"month-on-month query '{name}' returned nothing — refusing to write")
    sess_days = {}
    for d, se, at, bo in q(cur, f"""
      SELECT TO_VARCHAR(DAY), SESSIONS, SESSIONS_WITH_CART_ADDITIONS, TRY_TO_DOUBLE(TO_VARCHAR(BOUNCE_RATE))
      FROM RAW_SHOPIFY_SLEEPYCAT.SESSIONS_DAILY
      WHERE DAY BETWEEN '{prm['S']}' AND '{prm['T']}'"""):
        bo = None if bo is None else (bo / 100 if bo > 1 else bo)
        sess_days[d] = (int(se), int(at), bo)
    utm_month = {}
    for m, k, se, at in q(cur, f"""
      SELECT TO_CHAR(DAY, 'YYYY-MM'),
             UPPER(COALESCE(NULLIF(TRIM(UTM_SOURCE),''),'UNATTRIB'))||'/'||UPPER(COALESCE(TRIM(UTM_MEDIUM),'')),
             SUM(SESSIONS), SUM(SESSIONS_WITH_CART_ADDITIONS)
      FROM {utm_dedup(f"DAY BETWEEN '{prm['S']}' AND '{prm['T']}'")}
      GROUP BY 1,2"""):
        e = utm_month.setdefault(m, {'__ALL__': [0, 0]})
        e['__ALL__'][0] += int(se); e['__ALL__'][1] += int(at or 0)
        if not k.endswith('/CHECKOUT'): e[k] = [int(se), int(at or 0)]
    MOM = mom.build(mrows, sess_days, utm_month, through, datetime.date.today().isoformat())
    # the order fact table must reconcile with the orders table month by month (asserted inside build too)
    assert sum(MOM['funnel']['table'][5]['v']) > 0

    cur.close(); cn.close()

    today = datetime.date.today().isoformat()
    payload = {"generated_on": today, "as_of": today,
               "as_of_data": max(r["date"] for r in DAILY),
               "DAILY": DAILY, "UTM": {"daily": UTM_daily, "weekly": UTM_weekly, "minSess": MIN_SESS},
               "TOFU": TOFU, "CK_WEEKLY": CK, "SRC_CVR": SRC, "MOM": MOM}

    blob = json.dumps(payload, separators=(',', ':'))
    with open('data/data.js', 'w') as f:
        f.write("// Generated by scripts/build_data.py — do not edit by hand.\nwindow.SC_DATA = " + blob + ";\n")
    with open('data/data.json', 'w') as f:
        f.write(blob)
    print(f"wrote {len(DAILY)} days through {payload['as_of_data']} ({round(len(blob)/1024)} KB)")

if __name__ == '__main__':
    main()
