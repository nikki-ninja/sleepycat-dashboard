"""Month-on-month blocks (SC_DATA.MOM) for every non-daily dashboard tab.
Standard window: the last 4 calendar months, the current one month-to-date.
Volumes are compared per day, rates in percentage points. Used by build_data.py."""
import datetime, calendar
from collections import defaultdict

SQL = {
 "ord_utm": "with gd as (select ID, max(GOKWIK_UTM_SOURCE) gs, max(GOKWIK_UTM_MEDIUM) gm from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_GOKWIK_SOURCE group by 1),\no as (select ID, SOURCE_NAME, TOTAL_PRICE::float p, to_char(date(convert_timezone('Asia/Kolkata',CREATED_AT)),'YYYY-MM') m from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_ORDERS where SOURCE_NAME in ('256945782785','web','326345687041') and CANCELLED_AT is null and date(convert_timezone('Asia/Kolkata',CREATED_AT)) between '{S}' and '{T}')\nselect o.m, upper(coalesce(nullif(trim(gd.gs),''), nullif(trim(c.CHECKOUT_UTM_SOURCE),''),'UNATTRIB'))||'/'||upper(coalesce(nullif(trim(gd.gm),''), nullif(trim(c.CHECKOUT_UTM_MEDIUM),''),'')) k, (o.SOURCE_NAME='326345687041')::int gk, count(*) n, round(sum(p)) r\nfrom o left join SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_CHECKOUT_SOURCE c on c.ID=o.ID left join gd on gd.ID=o.ID group by 1,2,3 order by 1,4 desc",
 "ga4_month": "select substr(DATE,1,6) m, count(distinct DATE) days, sum(SESSIONS) s, sum(ENGAGEDSESSIONS) eng, sum(ADDTOCARTS) atc, sum(CHECKOUTS) ck, round(sum(AVERAGESESSIONDURATION*SESSIONS)/nullif(sum(SESSIONS),0)) dur,\nsum(iff(SESSIONSOURCEMEDIUM='google / cpc',SESSIONS,0)) g_s, sum(iff(SESSIONSOURCEMEDIUM='google / cpc',ADDTOCARTS,0)) g_atc,\nsum(iff(SESSIONSOURCEMEDIUM ilike 'facebook / bofu',SESSIONS,0)) b_s, sum(iff(SESSIONSOURCEMEDIUM ilike 'facebook / bofu',ADDTOCARTS,0)) b_atc,\nsum(iff(SESSIONSOURCEMEDIUM ilike 'facebook / tofu',SESSIONS,0)) t_s, sum(iff(SESSIONSOURCEMEDIUM ilike 'facebook / tofu',ADDTOCARTS,0)) t_atc\nfrom SLEEPYCAT_DB.MAPLEMONK.GA4_SC_GA4_SESSIONS_BY_DATE_SOURCE where DATE between '{GS}' and '{GT}' group by 1 order by 1",
 "pdp": "with t as (select substr(DATE,1,6) m, ITEMNAME n, sum(ITEMSVIEWED) v, sum(ITEMSADDEDTOCART) a, sum(ITEMSCHECKEDOUT) c from SLEEPYCAT_DB.MAPLEMONK.GA4_SC_GA4_PRODUCTS_FUNNEL_METRICS where DATE between '{GS}' and '{GT}' group by 1,2),\ntop as (select n from t group by n order by sum(v) desc limit 14)\nselect t.* from t join top using(n) order by n, m",
 "pay_method": "select to_char(date(convert_timezone('Asia/Kolkata',to_timestamp(CREATED_AT))),'YYYY-MM') m, METHOD, STATUS, count(*) n, round(sum(AMOUNT)/100) amt\nfrom SLEEPYCAT_DB.MAPLEMONK.RAZORPAY_PAYMENTS where date(convert_timezone('Asia/Kolkata',to_timestamp(CREATED_AT))) between '{S}' and '{T}' group by 1,2,3 order by 1,2,3",
 "pay_band": "with p as (select ORDER_ID, min(date(convert_timezone('Asia/Kolkata',to_timestamp(CREATED_AT)))) d, max(AMOUNT)/100 amt, count(*) att, max(iff(STATUS in ('captured','refunded'),1,0)) paid\nfrom SLEEPYCAT_DB.MAPLEMONK.RAZORPAY_PAYMENTS where ORDER_ID is not null and date(convert_timezone('Asia/Kolkata',to_timestamp(CREATED_AT))) between '{S}' and '{T}' group by 1)\nselect to_char(d,'YYYY-MM') m, case when amt<5000 then '1' when amt<15000 then '2' when amt<30000 then '3' else '4' end band, count(*) ck, sum(paid) paid, sum(att) att, round(avg(amt)) avg_t, round(sum(iff(paid=0,amt,0))) aband from p group by 1,2 order by 1,2",
 "emi_reason": "select to_char(date(convert_timezone('Asia/Kolkata',to_timestamp(CREATED_AT))),'YYYY-MM') m, coalesce(ERROR_REASON,'(none)') r, count(*) n\nfrom SLEEPYCAT_DB.MAPLEMONK.RAZORPAY_PAYMENTS where METHOD='cardless_emi' and STATUS='failed' and date(convert_timezone('Asia/Kolkata',to_timestamp(CREATED_AT))) between '{S}' and '{T}' group by 1,2 order by 1,3 desc",
 "mask": "with li as (select ORDER_ID, to_char(date(ORDER_TIMESTAMP),'YYYY-MM') m, SHOPIFY_NEW_CUSTOMER_FLAG f, TOTAL_SALES s,\n case when PRODUCT_CATEGORY in ('MATTRESS','MATTRESSES') then 1 when PRODUCT_SUB_CATEGORY='DOG BED COVER' or PRODUCT_CATEGORY in ('PET BED','PET MAT') then 16 when PRODUCT_CATEGORY in ('BEDDING','COVER') then 2 when PRODUCT_CATEGORY='PILLOW' then 4 when PRODUCT_CATEGORY='CASE' then 8 when PRODUCT_CATEGORY in ('BED','RECLINER') then 32 else 64 end b\n from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_SHOPIFY_FACT_ITEMS where APP_ID in (256945782785,580111,326345687041) and ORDER_STATUS<>'CANCELLED' and date(ORDER_TIMESTAMP) between '{S}' and '{T}'),\no as (select ORDER_ID, max(m) m, max(f) f, sum(s) s, bitor_agg(b) mask, count(distinct b) ncat from li group by 1)\nselect m, mask, f, count(*) n, round(sum(s)) r from o group by 1,2,3 order by 1,2,3",
 "pos_state": "select to_char(date(ORDER_TIMESTAMP),'YYYY-MM') m, upper(trim(STATE)) st, count(distinct ORDER_ID) n, round(sum(TOTAL_SALES)) r\nfrom SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_SHOPIFY_FACT_ITEMS where APP_ID=266308321281 and ORDER_STATUS<>'CANCELLED' and date(ORDER_TIMESTAMP) between '{S}' and '{T}' group by 1,2 order by 1,4 desc",
 "prod": "select to_char(date(ORDER_TIMESTAMP),'YYYY-MM') m, PRODUCT_CATEGORY c, coalesce(nullif(PRODUCT_SUB_CATEGORY,''),PRODUCT_CATEGORY) p, count(distinct ORDER_ID) o, sum(QUANTITY) u, round(sum(TOTAL_SALES)) r, sum(REFUND_QUANTITY) rq\nfrom SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_SHOPIFY_FACT_ITEMS where APP_ID in (256945782785,580111,326345687041) and ORDER_STATUS<>'CANCELLED' and date(ORDER_TIMESTAMP) between '{S}' and '{T}' group by 1,2,3 order by 1,6 desc",
 "sku": "with b as (select to_char(date(ORDER_TIMESTAMP),'YYYY-MM') m, coalesce(nullif(SKU_CODE,''),SKU) sku, max(coalesce(nullif(PRODUCT_SUB_CATEGORY,''),PRODUCT_NAME_FINAL)) over (partition by coalesce(nullif(SKU_CODE,''),SKU)) p, ORDER_ID, QUANTITY, TOTAL_SALES\n from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_SHOPIFY_FACT_ITEMS where APP_ID in (256945782785,580111,326345687041) and ORDER_STATUS<>'CANCELLED' and date(ORDER_TIMESTAMP) between '{S}' and '{T}'),\na as (select m, sku, max(p) p, count(distinct ORDER_ID) o, sum(QUANTITY) u, round(sum(TOTAL_SALES)) r from b group by 1,2),\ntop as (select sku from a group by sku order by sum(r) desc limit 20)\nselect a.* from a join top using(sku) order by sku, m",
 "size": "select to_char(date(ORDER_TIMESTAMP),'YYYY-MM') m, case when regexp_like(upper(SKU_CODE),'.*-K-.*') then 'King' when regexp_like(upper(SKU_CODE),'.*-Q-.*') then 'Queen' when regexp_like(upper(SKU_CODE),'.*-D-.*') then 'Double' when regexp_like(upper(SKU_CODE),'.*-S-.*') then 'Single' when upper(SKU_CODE) like '%TFOLD%' then 'Tri-fold' else 'Other/unparsed' end sz, count(distinct ORDER_ID) o, sum(QUANTITY) u, round(sum(TOTAL_SALES)) r\nfrom SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_SHOPIFY_FACT_ITEMS where APP_ID in (256945782785,580111,326345687041) and ORDER_STATUS<>'CANCELLED' and PRODUCT_CATEGORY in ('MATTRESS','MATTRESSES') and date(ORDER_TIMESTAMP) between '{S}' and '{T}' group by 1,2 order by 1,3 desc",
 "meta": "with c as (select CAMPAIGN_NAME, to_char(DATE,'YYYY-MM') m, sum(SPEND) sp, sum(CONVERSIONS) pu, sum(CONVERSION_VALUE) rv, sum(CLICKS) cl, sum(IMPRESSIONS) im, sum(ADD_TO_CARTS) atc from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_FACEBOOK_CONSOLIDATED where DATE between '{S}' and '{T}' group by 1,2)\nselect m, round(sum(sp)) sp, sum(pu) pu, round(sum(rv)) rv, sum(cl) cl, sum(im) im, sum(atc) atc, count_if(sp>=10000) active,\ncount_if(sp>=10000 and rv/sp>=4) scale, count_if(sp>=10000 and rv/sp>=2.5 and rv/sp<4) working, count_if(sp>=10000 and rv/sp>=1 and rv/sp<2.5) watch, count_if(sp>=10000 and rv/sp<1) stop, round(sum(iff(sp>=10000 and rv/sp<1,sp,0))) stop_sp\nfrom c group by 1 order by 1",
 "chan": "with gd as (select ID, max(GOKWIK_UTM_SOURCE) gs, max(GOKWIK_UTM_MEDIUM) gm from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_GOKWIK_SOURCE group by 1),\nf as (select ORDER_ID, max(SHOPIFY_NEW_CUSTOMER_FLAG) fl from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_SHOPIFY_FACT_ITEMS where date(ORDER_TIMESTAMP) between '{S1}' and '{T1}' group by 1),\no as (select ID, TOTAL_PRICE::float p, to_char(date(convert_timezone('Asia/Kolkata',CREATED_AT)),'YYYY-MM') m from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_ORDERS where SOURCE_NAME in ('256945782785','web','326345687041') and CANCELLED_AT is null and date(convert_timezone('Asia/Kolkata',CREATED_AT)) between '{S}' and '{T}'),\nk as (select o.m, o.p, coalesce(f.fl,'?') fl, upper(coalesce(nullif(trim(gd.gs),''), nullif(trim(c.CHECKOUT_UTM_SOURCE),''),'UNATTRIB')) s, upper(coalesce(nullif(trim(gd.gm),''), nullif(trim(c.CHECKOUT_UTM_MEDIUM),''),'')) md\n from o left join SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_CHECKOUT_SOURCE c on c.ID=o.ID left join gd on gd.ID=o.ID left join f on f.ORDER_ID=o.ID)\nselect m, case when s='GOOGLE' and md in ('CPC','PRODUCT_SYNC') then 'Google Ads'\n when s='FACEBOOK' and md in ('TOFU','BOFU','PAID','CPC','MOFU','BOFU_PETBED') then 'Meta Ads'\n when s in ('UNATTRIB','DIRECT') then 'Direct / untagged'\n when s in ('WHATSAPP','EMAIL','OTCRM','SAGEPILOT-AI','SAGEPILOT','KWIKENGAGE','BISAE') or md in ('CLEVERTAP','CAMPAIGN','EMAIL','SMS','WHATSAPP','PUSH') then 'CRM (WhatsApp / email)'\n when s in ('INSTAGRAM','FACEBOOK','SOCIAL','IG','YOUTUBE','THREADS','REDDIT','YOUTUBER','INFLUENCER','PAID INFLUENCERS') then 'Social & influencer'\n when s in ('GOOGLE','BING','DUCKDUCKGO','BRAVE','SEARCH','CHATGPT.COM','CHATGPT','PERPLEXITY','GEMINI','REDIFF') then 'Search & AI (organic)'\n else 'Affiliate & other' end ch, fl, count(*) n, round(sum(p)) r from k group by 1,2,3 order by 1,2,3",
 "tierkind": "with li as (select ORDER_ID, date(ORDER_TIMESTAMP) d, upper(trim(CITY)) ct, TOTAL_SALES s, PRODUCT_CATEGORY c, PRODUCT_SUB_CATEGORY sc\n from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_SHOPIFY_FACT_ITEMS where APP_ID in (256945782785,580111,326345687041) and ORDER_STATUS<>'CANCELLED' and date(ORDER_TIMESTAMP) between '{S}' and '{T}'),\no as (select ORDER_ID, max(d) d, max(ct) ct, max(iff(c in ('MATTRESS','MATTRESSES'),1,0)) mat from li group by 1),\nref as (select ct, count(*) c from o where d between '{S}' and '{R}' group by 1),\nt as (select o.ORDER_ID, o.mat, to_char(o.d,'YYYY-MM') m, case when o.ct in ('BENGALURU','BANGALORE','MUMBAI','PUNE','HYDERABAD','CHENNAI','DELHI','NEW DELHI','GURGAON','GURUGRAM','KOLKATA','NOIDA') then 'Metro' when coalesce(ref.c,0)>=50 then 'Tier-1' when ref.c>=20 then 'Tier-2' when ref.c>=8 then 'Tier-3' else 'RoI' end tier from o left join ref on ref.ct=o.ct),\nk as (select t.m, t.tier, t.ORDER_ID, li.s,\n case when t.mat=1 and li.c in ('MATTRESS','MATTRESSES') then 'MT:'||case when li.sc ilike 'HYBRID%' then 'Hybrid Latex' when li.sc ilike 'ORIGINAL%' then 'Original' when li.sc ilike 'ULTIMA NATURAL%' then 'Ultima Natural Latex' when li.sc ilike '%LATEX-ORTHO%' then 'Latex Ortho' when li.sc ilike 'ULTIMA MEMORY%' then 'Ultima Memory Foam' when li.sc ilike 'TRI FOLD%' then 'Tri Fold' else 'Other mattress' end\n      when t.mat=0 then 'NM:'||case when li.c='PILLOW' then 'Pillow' when li.sc='MATTRESS PROTECTOR' then 'Protector' when li.sc ilike '%TOPPER%' then 'Topper' when li.c='CASE' then 'Pillow case' when li.c in ('PET BED','PET MAT') or li.sc='DOG BED COVER' then 'Pet' when li.sc ilike '%SHEET%' then 'Bedsheet' when li.sc ilike '%COMFORTER%' or li.sc ilike '%BLANKET%' or li.sc ilike '%THROW%' then 'Comforter/blanket' else 'Other' end end kind\n from t join li on li.ORDER_ID=t.ORDER_ID)\nselect m, tier, kind, count(distinct ORDER_ID) n, round(sum(s)) r from k where kind is not null group by 1,2,3 order by 1,2,3",
 "cities": "with li as (select ORDER_ID, date(ORDER_TIMESTAMP) d, upper(trim(CITY)) ct, upper(trim(STATE)) st, TOTAL_SALES s, PRODUCT_CATEGORY c\n from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_SHOPIFY_FACT_ITEMS where APP_ID in (256945782785,580111,326345687041) and ORDER_STATUS<>'CANCELLED' and date(ORDER_TIMESTAMP) between '{S}' and '{T}'),\no as (select ORDER_ID, max(d) d, max(ct) ct, max(st) st, sum(s) s, max(iff(c in ('MATTRESS','MATTRESSES'),1,0)) mat from li group by 1),\nref as (select ct, count(*) c from o where d between '{S}' and '{R}' group by 1),\nt as (select o.*, to_char(o.d,'YYYY-MM') m, case when o.ct in ('BENGALURU','BANGALORE','MUMBAI','PUNE','HYDERABAD','CHENNAI','DELHI','NEW DELHI','GURGAON','GURUGRAM','KOLKATA','NOIDA') then 'Metro' when coalesce(ref.c,0)>=50 then 'Tier-1' when ref.c>=20 then 'Tier-2' when ref.c>=8 then 'Tier-3' else 'RoI' end tier from o left join ref on ref.ct=o.ct),\ncities as (select 'CNT' kind, tier, null ct, null st, null m, count(distinct ct) n, null r from t where d<='{R}' group by 2),\nt3 as (select ct from t where tier in ('Tier-3') group by ct order by sum(s) desc limit 20),\nmetro as (select ct from t where tier in ('Metro','Tier-1') group by ct order by count(*) desc limit 10)\nselect * from cities\nunion all select 'T3', tier, ct, max(st), m, count(*), round(sum(s)) from t where ct in (select ct from t3) group by 2,3,5\nunion all select 'CITY', tier, ct, max(st), m, count(*), round(sum(s)) from t where ct in (select ct from metro) group by 2,3,5\nunion all select 'CITYMAT', tier, ct, max(st), m, sum(mat), null from t where ct in (select ct from metro) group by 2,3,5",
 "geo2": "with li as (select ORDER_ID, date(ORDER_TIMESTAMP) d, upper(trim(STATE)) st, upper(trim(CITY)) ct, TOTAL_SALES s,\n iff(PRODUCT_CATEGORY in ('MATTRESS','MATTRESSES'),1,0) mat, iff(PRODUCT_CATEGORY='PILLOW',1,0) pil, iff(PRODUCT_SUB_CATEGORY='MATTRESS PROTECTOR',1,0) prot, iff(PRODUCT_CATEGORY not in ('MATTRESS','MATTRESSES'),1,0) acc\n from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_SHOPIFY_FACT_ITEMS where APP_ID in (256945782785,580111,326345687041) and ORDER_STATUS<>'CANCELLED' and date(ORDER_TIMESTAMP) between '{S}' and '{T}'),\no as (select ORDER_ID, to_char(max(d),'YYYY-MM') m, max(d) d, max(st) st, max(ct) ct, sum(s) s, max(mat) mat, max(pil) pil, max(prot) prot, max(acc) acc from li group by 1),\nref as (select ct, count(*) c from o where d between '{S}' and '{R}' group by 1),\nt as (select o.*, case when o.ct in ('BENGALURU','BANGALORE','MUMBAI','PUNE','HYDERABAD','CHENNAI','DELHI','NEW DELHI','GURGAON','GURUGRAM','KOLKATA','NOIDA') then 'Metro' when coalesce(ref.c,0)>=50 then 'Tier-1' when ref.c>=20 then 'Tier-2' when ref.c>=8 then 'Tier-3' else 'RoI' end tier from o left join ref on ref.ct=o.ct)\nselect m, tier, st, mat, pil, prot, acc, count(*) n, round(sum(s)) r, count(distinct ct) ncity from t group by 1,2,3,4,5,6,7"
}

MIN_DAYS = 7   # a month with fewer days than this is too thin to compare; the tabs stay on the last closed month

def effective_through(through):
    """Early in a month (day < MIN_DAYS) the month-on-month tabs stop at the previous month-end."""
    if through.day < MIN_DAYS:
        return through.replace(day=1) - datetime.timedelta(days=1)
    return through

def window(through):
    """through: date of the last complete day. Returns months, labels, day counts and SQL params."""
    y, m = through.year, through.month
    months = []
    for k in range(3, -1, -1):
        mm = m - k; yy = y
        while mm <= 0: mm += 12; yy -= 1
        months.append((yy, mm))
    M = [f'{yy}-{mm:02d}' for yy, mm in months]
    LAB = [calendar.month_abbr[mm] for _, mm in months]
    if through.day != calendar.monthrange(y, m)[1]: LAB[-1] += '*'
    DAYS = [calendar.monthrange(yy, mm)[1] for yy, mm in months]; DAYS[-1] = through.day
    start = datetime.date(months[0][0], months[0][1], 1)
    ref_end = start + datetime.timedelta(days=89)
    p = {'S': start.isoformat(), 'T': through.isoformat(), 'R': ref_end.isoformat(),
         'GS': start.strftime('%Y%m%d'), 'GT': through.strftime('%Y%m%d'),
         'S1': (start - datetime.timedelta(days=1)).isoformat(), 'T1': (through + datetime.timedelta(days=1)).isoformat()}
    return M, LAB, DAYS, p

def sql(name, p):
    s = SQL[name]
    for k, v in p.items(): s = s.replace('{' + k + '}', v)
    return s

def build(rows, sess_days, utm_month, through, refreshed):
    """rows: {name: list of result tuples}; sess_days: {iso: (sessions, atc, bounce 0-1 or None)};
    utm_month: {YYYY-MM: {'SOURCE/MEDIUM': [sessions, atc], '__ALL__': [sessions, atc]}} (CHECKOUT medium excluded except in __ALL__)"""
    M, LAB, DAYS, p = window(through)
    THROUGH = through.isoformat(); START = p['S']
    L = lambda n: [[str(x) if x is not None else '' for x in r] for r in rows[n]]
    f = float
    mi = {m: i for i, m in enumerate(M)}
    z = lambda: [0, 0, 0, 0]
    def fmtd(d): return datetime.date.fromisoformat(d).strftime('%b %-d')
    OUT = {'meta': {'months': M, 'labels': LAB, 'days': DAYS, 'through': THROUGH, 'refreshed': refreshed, 'complete': not LAB[-1].endswith('*'),
                    'window': f"{fmtd(START)} – {fmtd(THROUGH)}, {through.year}", 'tierRef': f"{fmtd(START)} – {fmtd(p['R'])}"}}
    def row(k, v, fmt, d='vol', g=1, **kw):
        r = {'k': k, 'v': [None if x is None else (round(x, 4) if isinstance(x, float) else x) for x in v], 'f': fmt, 'd': d, 'g': g}
        r.update(kw); return r
    def per_day(v): return [None if x is None else x / DAYS[i] for i, x in enumerate(v)]
    # ---------------- sessions ----------------
    S, A, BS, NB = z(), z(), z(), z(); cnt = z()
    for d, (se, at, bo) in sess_days.items():
        if d[:7] in mi and START <= d <= THROUGH:
            i = mi[d[:7]]; S[i] += se; A[i] += at; cnt[i] += 1
            if bo is not None: BS[i] += se * bo; NB[i] += se
    for i, m in enumerate(M):   # month not fully covered by the daily sessions feed -> UTM feed total (same source)
        if cnt[i] < DAYS[i] and m in utm_month:
            S[i], A[i] = utm_month[m].get('__ALL__', [0, 0]); NB[i] = 0
    BOUNCE = [round(BS[i] / NB[i] * 100, 1) if NB[i] else None for i in range(4)]
    usm = utm_month
    GC_S = [usm.get(m, {}).get('GOOGLE/CPC', [0, 0])[0] for m in M]
    TOFU_S = [usm.get(m, {}).get('FACEBOOK/TOFU', [0, 0])[0] for m in M]

    # ---------------- orders by source ----------------
    O, R, GK = z(), z(), z(); key_o = defaultdict(z); key_r = defaultdict(z)
    for m, k, gk, n, r in L('ord_utm'):
        i = mi[m]; n = int(n); r = f(r)
        O[i] += n; R[i] += r
        if gk == '1': GK[i] += n
        kk = 'DIRECT / UNTAGGED' if k in ('UNATTRIB/', 'DIRECT/') else k
        key_o[kk][i] += n; key_r[kk][i] += r
    GC_O = key_o['GOOGLE/CPC']; TOFU_O = key_o['FACEBOOK/TOFU']
    ATC_PCT = [A[i] / S[i] * 100 for i in range(4)]
    C2O = [O[i] / A[i] * 100 for i in range(4)]
    CVR = [O[i] / S[i] * 100 for i in range(4)]
    CVRX = [(O[i] - GC_O[i] - TOFU_O[i]) / (S[i] - GC_S[i] - TOFU_S[i]) * 100 for i in range(4)]
    AOV = [R[i] / O[i] for i in range(4)]
    ga = {r[0]: r for r in L('ga4_month')}
    GA_CK = [int(ga[m.replace('-', '')][5]) for m in M]
    OUT['funnel'] = {
      'kpi': {'sess_day': per_day(S), 'atc': ATC_PCT, 'c2o': C2O, 'cvrx': CVRX, 'ord_day': per_day(O), 'aov': AOV, 'cvr': CVR},
      'table': [
        row('Sessions', S, 'int', b=1), row('↳ of which Google CPC', GC_S, 'int', g=0),
        row('↳ of which Facebook TOFU', TOFU_S, 'int', g=0),
        row('Add-to-cart sessions', A, 'int'), row('Add-to-cart rate', ATC_PCT, 'pct', 'rate', b=1),
        row('Orders (D2C online)', O, 'int', b=1), row('Cart → order', C2O, 'pct', 'rate'),
        row('CVR (orders ÷ sessions)', CVR, 'pct', 'rate', b=1),
        row('CVR ex-prospecting', CVRX, 'pct', 'rate', b=1, tip='Nets Google CPC and Facebook TOFU out of both orders and sessions — same rule as the Daily tab'),
        row('AOV', AOV, 'inr', 'rate'), row('Revenue', R, 'L'),
        row('GoKwik share of orders', [GK[i] / O[i] * 100 for i in range(4)], 'pct1', 'none', g=0)],
      'outcome': [{'m': LAB[i], 'ord': CVR[i], 'atc_no': ATC_PCT[i] - CVR[i], 'no_atc': 100 - ATC_PCT[i]} for i in range(4)],
      'water': {'s': S[3], 'a': A[3], 'o': O[3]},
      'dropoff': [100 - c for c in C2O],
      'ga4ck': GA_CK, 'orders': O,
      'bounce': BOUNCE}

    # ---------------- GA4 & CRO ----------------
    keys = sorted(key_r, key=lambda k: -sum(key_r[k]))
    top = [k for k in keys if k != 'DIRECT / UNTAGGED'][:11]
    oth_r, oth_o = z(), z()
    for k in keys:
        if k not in top and k != 'DIRECT / UNTAGGED':
            for i in range(4): oth_r[i] += key_r[k][i]; oth_o[i] += key_o[k][i]
    def nice(k):
        s, _, md = k.partition('/'); return (s.lower() + (' / ' + md.lower() if md else '')).replace('direct / untagged', '(direct / untagged)')
    utm_rows = [row(nice(k), key_r[k], 'L', tip=[f'{x:,} orders' for x in key_o[k]]) for k in top]
    utm_rows.insert(1, row('(direct / untagged)', key_r['DIRECT / UNTAGGED'], 'L', tip=[f'{x:,} orders' for x in key_o['DIRECT / UNTAGGED']]))
    utm_rows.append(row('All other sources', oth_r, 'L', g=0, tip=[f'{x:,} orders' for x in oth_o]))
    utm_rows.append(row('Total', R, 'L', b=1))
    ch = defaultdict(lambda: {'nO': z(), 'nR': z(), 'rO': z(), 'rR': z()})
    for m, c, fl, n, r in L('chan'):
        i = mi[m]; e = ch[c]
        if fl == 'New': e['nO'][i] += int(n); e['nR'][i] += f(r)
        else: e['rO'][i] += int(n); e['rR'][i] += f(r)
    CH_ORDER = ['Google Ads', 'Direct / untagged', 'Meta Ads', 'Search & AI (organic)', 'Social & influencer', 'CRM (WhatsApp / email)', 'Affiliate & other']
    ch_orders = [row(c, [ch[c]['nO'][i] + ch[c]['rO'][i] for i in range(4)], 'int') for c in CH_ORDER]
    ch_new = [row(c, [ch[c]['nR'][i] / (ch[c]['nR'][i] + ch[c]['rR'][i]) * 100 for i in range(4)], 'pct1', 'rate', g=0) for c in CH_ORDER]
    pdp = defaultdict(lambda: [z(), z(), z()])
    for n, m, v, a, c in L('pdp'):
        i = mi[m[:4] + '-' + m[4:]]; p = pdp[n]; p[0][i] = int(v); p[1][i] = int(a); p[2][i] = int(c)
    pdp_rows = [row(n, [p[1][i] / p[0][i] * 100 if p[0][i] else None for i in range(4)], 'pct', 'rate', tip=[f'{p[0][i]:,} views · {p[1][i]:,} adds' for i in range(4)])
                for n, p in sorted(pdp.items(), key=lambda x: -x[1][0][3])]
    gam = [ga[m.replace('-', '')] for m in M]
    eng = {'sess_day': [int(g[2]) / DAYS[i] for i, g in enumerate(gam)], 'dur': [f(g[6]) for g in gam],
           'nonEng': [(1 - int(g[3]) / int(g[2])) * 100 for g in gam]}
    cro = {'bofu_s': int(gam[3][9]), 'bofu_atc': int(gam[3][10]) / int(gam[3][9]) * 100,
           'tofu_s': int(gam[3][11]), 'tofu_atc': int(gam[3][12]) / int(gam[3][11]) * 100,
           'g_s': int(gam[3][7]), 'g_atc': int(gam[3][8]) / int(gam[3][7]) * 100,
           'bofu_atc_aug': int(gam[2][10]) / int(gam[2][9]) * 100, 'g_atc_aug': int(gam[2][8]) / int(gam[2][7]) * 100}
    OUT['ga4cro'] = {'utm': utm_rows, 'chOrders': ch_orders, 'chNew': ch_new, 'pdp': pdp_rows[:12], 'eng': eng, 'cro': cro}

    # ---------------- payments ----------------
    pm = defaultdict(lambda: defaultdict(z))
    for m, meth, st, n, amt in L('pay_method'):
        pm[meth][st][mi[m]] += int(n)
        pm[meth]['amt_' + st][mi[m]] += f(amt)
    MNAME = {'upi': 'UPI', 'card': 'Card', 'emi': 'Card EMI', 'cardless_emi': 'Cardless EMI', 'netbanking': 'Netbanking', 'wallet': 'Wallet'}
    def succ(meths):
        out = []; att = []
        for i in range(4):
            c = sum(pm[x]['captured'][i] + pm[x]['refunded'][i] for x in meths)
            t = sum(pm[x]['captured'][i] + pm[x]['refunded'][i] + pm[x]['failed'][i] + pm[x]['created'][i] for x in meths)
            out.append(c / t * 100 if t else None); att.append(t)
        return out, att
    meth_rows = []
    for k in ['upi', 'card', 'emi', 'cardless_emi', 'netbanking', 'wallet']:
        v, att = succ([k]); meth_rows.append(row(MNAME[k], v, 'pct1', 'rate', tip=[f'{a:,} attempts' for a in att]))
    v, att = succ(list(MNAME)); meth_rows.append(row('All methods', v, 'pct1', 'rate', b=1, tip=[f'{a:,} attempts' for a in att]))
    ATT_ALL = att
    band = defaultdict(lambda: {'ck': z(), 'paid': z(), 'att': z(), 'ab': z()})
    for m, b, ck, paid, at, avg, ab in L('pay_band'):
        e = band[b]; i = mi[m]; e['ck'][i] = int(ck); e['paid'][i] = int(paid); e['att'][i] = int(at); e['ab'][i] = f(ab)
    BN = {'1': 'Under ₹5k', '2': '₹5k – 15k', '3': '₹15k – 30k', '4': '₹30k+'}
    band_rows = [row(BN[b], [band[b]['paid'][i] / band[b]['ck'][i] * 100 for i in range(4)], 'pct1', 'rate',
                     tip=[f"{band[b]['ck'][i]:,} checkouts · {band[b]['att'][i]/band[b]['ck'][i]:.2f} attempts each" for i in range(4)]) for b in '1234']
    ck_all = [sum(band[b]['ck'][i] for b in '1234') for i in range(4)]
    band_rows.append(row('All checkouts', [sum(band[b]['paid'][i] for b in '1234') / ck_all[i] * 100 for i in range(4)], 'pct1', 'rate', b=1, tip=[f'{c:,} checkouts' for c in ck_all]))
    aband = [sum(band[b]['ab'][i] for b in '1234') for i in range(4)]
    emi = defaultdict(z)
    for m, r, n in L('emi_reason'):
        k = {'payment_timed_out': 'Timed out', 'payment_cancelled': 'Cancelled', 'payment_failed': 'Declined'}.get(r, 'Other')
        emi[k][mi[m]] += int(n)
    OUT['payments'] = {'method': meth_rows, 'band': band_rows, 'abandoned': aband, 'band34_ab': [band['3']['ab'][i] + band['4']['ab'][i] for i in range(4)],
                       'checkouts': ck_all, 'attempts': ATT_ALL, 'emiReasons': {k: emi[k] for k in ['Timed out', 'Cancelled', 'Declined', 'Other']},
                       'gkShare': [GK[i] / O[i] * 100 for i in range(4)]}

    # ---------------- order composition (mask) ----------------
    # bits: 1 mattress, 2 bedding, 4 pillow, 8 case, 16 pet, 32 furniture, 64 ergo/other
    CAT = [(1, 'Mattress'), (2, 'Bedding'), (4, 'Pillow'), (8, 'Pillow case'), (16, 'Pet'), (32, 'Furniture'), (64, 'Ergo & other')]
    mk = L('mask')
    def prim(mask):
        for b, n in CAT:
            if mask & b: return n
    nfl = {'New': {'o': z(), 'r': z()}, 'Repeat': {'o': z(), 'r': z()}}
    new_mix = defaultdict(z); pairs = defaultdict(z); matt = z(); att = z(); acc_n = defaultdict(z)
    for m, mask, fl, n, r in mk:
        i = mi[m]; mask = int(mask); n = int(n); r = f(r)
        nfl[fl]['o'][i] += n; nfl[fl]['r'][i] += r
        if fl == 'New': new_mix[prim(mask)][i] += n
        present = [nm for b, nm in CAT if mask & b]
        for a in range(len(present)):
            for b2 in range(a + 1, len(present)): pairs[present[a] + ' + ' + present[b2]][i] += n
        if mask & 1:
            matt[i] += n; k = bin(mask & 14).count('1'); acc_n[k][i] += n
            if mask & 14: att[i] += n
    tot_o = [nfl['New']['o'][i] + nfl['Repeat']['o'][i] for i in range(4)]
    assert all(abs(tot_o[i] - O[i]) <= max(5, O[i] * 0.005) for i in range(4)), ('order fact table does not reconcile with orders', tot_o, O)
    OUT['cohorts'] = {'newO': nfl['New']['o'], 'repO': nfl['Repeat']['o'], 'newR': nfl['New']['r'], 'repR': nfl['Repeat']['r'],
                      'newMix': {k: new_mix[k] for _, k in CAT}}
    pk = sorted(pairs, key=lambda k: -sum(pairs[k]))[:8]
    OUT['crosssell'] = {'pairs': [row(k, pairs[k], 'int') for k in pk], 'mattOrders': matt, 'attach': [att[i] / matt[i] * 100 for i in range(4)],
                        'accN': {str(k): acc_n[k] for k in range(4)}, 'sepPairs': [[k, pairs[k][3]] for k in sorted(pairs, key=lambda k: -pairs[k][3])[:8]]}

    # ---------------- products ----------------
    def pname(c, p):
        p = p.strip()
        if p == 'MATTRESSES': return 'Mattress (SKU not mapped)'
        if p == 'BEDDING': return 'Bedding (SKU not mapped)'
        if p == 'THE-LATEX-ORTHO-MATTRESS': return 'The Latex Ortho Mattress'
        return p.title().replace("'S", "'s").replace('Tc', 'TC').replace(' - ', ' ')
    pr = defaultdict(lambda: {'o': z(), 'u': z(), 'r': z(), 'c': ''})
    catr = defaultdict(z)
    CATMAP = {'MATTRESS': 'Mattress', 'MATTRESSES': 'Mattress', 'BEDDING': 'Bedding', 'COVER': 'Bedding', 'PILLOW': 'Pillow', 'CASE': 'Pillow case',
              'PET BED': 'Pet', 'PET MAT': 'Pet', 'BED': 'Furniture', 'RECLINER': 'Furniture'}
    for m, c, p, o, u, r, rq in L('prod'):
        i = mi[m]; n = pname(c, p); e = pr[n]; e['o'][i] += int(o); e['u'][i] += f(u or 0); e['r'][i] += f(r); e['c'] = c
        cat = 'Pet' if p == 'DOG BED COVER' else CATMAP.get(c, 'Ergo & other'); catr[cat][i] += f(r)
    ptop = sorted(pr, key=lambda k: -sum(pr[k]['r']))
    isM = lambda k: pr[k]['c'] in ('MATTRESS', 'MATTRESSES') and 'not mapped' not in k and 'Baby' not in k
    mtop = [k for k in ptop if isM(k)]
    OUT['products'] = {
      'rev': [row(k, pr[k]['r'], 'L', tip=[f"{x:,} orders" for x in pr[k]['o']]) for k in ptop[:15]],
      'orders': [row(k, pr[k]['o'], 'int') for k in sorted(pr, key=lambda k: -sum(pr[k]['o']))[:12]],
      'top3': [{'k': k, 'rpd': per_day(pr[k]['r'])} for k in mtop[:3]],
      'kpi': [{'k': k, 'r': pr[k]['r'], 'o': pr[k]['o']} for k in ptop[:4]],
      'asp': [{'k': k, 'v': [pr[k]['r'][i] / pr[k]['u'][i] if pr[k]['u'][i] else None for i in range(4)]} for k in mtop[:6]],
      'catMix': {k: catr[k] for k in ['Mattress', 'Bedding', 'Pillow', 'Pillow case', 'Pet', 'Furniture', 'Ergo & other']},
      'size': {}}
    for m, sz, o, u, r in L('size'):
        OUT['products']['size'].setdefault(sz, z())[mi[m]] = int(o)
    sku = defaultdict(lambda: {'o': z(), 'r': z(), 'p': ''})
    for s, m, p, o, u, r in L('sku'):
        e = sku[s]; e['o'][mi[m]] = int(o); e['r'][mi[m]] = f(r); e['p'] = pname('', p)
    st = sorted(sku, key=lambda k: -sum(sku[k]['r']))
    OUT['sku'] = {'rev': [row(s, sku[s]['r'], 'L', sub=sku[s]['p'], tip=[f"{x:,} orders" for x in sku[s]['o']]) for s in st],
                  'top5': [{'k': s, 'p': sku[s]['p'], 'opd': per_day(sku[s]['o']), 'rpd': per_day(sku[s]['r'])} for s in st[:5]]}

    # ---------------- geo ----------------
    SN = lambda s: {'NA': 'Unknown'}.get(s, s.title().replace(' And ', ' & '))
    stR = defaultdict(z); stO = defaultdict(z); stM = defaultdict(z); stA = defaultdict(z)
    tO = defaultdict(z); tR = defaultdict(z); tM = defaultdict(z); tA = defaultdict(z); tNM = defaultdict(z)
    for m, tier, s, mat, pil, prot, acc, n, r, nc in L('geo2'):
        i = mi[m]; n = int(n); r = f(r); s = SN(s)
        stR[s][i] += r; stO[s][i] += n; tO[tier][i] += n; tR[tier][i] += r
        if mat == '1':
            stM[s][i] += n; tM[tier][i] += n
            if acc == '1': stA[s][i] += n; tA[tier][i] += n
        else: tNM[tier][i] += n
    assert all(abs(sum(tO[t][i] for t in tO) - O[i]) <= max(5, O[i] * 0.005) for i in range(4)), 'geo does not reconcile'
    TIERS = ['Metro', 'Tier-1', 'Tier-2', 'Tier-3', 'RoI']
    TL = {'RoI': 'Rest of India'}
    sR = [s for s in sorted(stR, key=lambda k: -sum(stR[k])) if s != 'Unknown']
    sM = [s for s in sorted(stM, key=lambda k: -sum(stM[k])) if s != 'Unknown']
    pos = defaultdict(lambda: {'o': z(), 'r': z()})
    for m, s, n, r in L('pos_state'):
        pos[SN(s)]['o'][mi[m]] += int(n); pos[SN(s)]['r'][mi[m]] += f(r)
    POS_O = [sum(pos[s]['o'][i] for s in pos) for i in range(4)]; POS_R = [sum(pos[s]['r'][i] for s in pos) for i in range(4)]
    tk = defaultdict(lambda: defaultdict(z))
    for m, tier, kind, n, r in L('tierkind'):
        tk[tier][kind][mi[m]] += int(n)
    MT = ['Hybrid Latex', 'Original', 'Latex Ortho', 'Ultima Natural Latex', 'Ultima Memory Foam', 'Tri Fold', 'Other mattress']
    NM = ['Pillow', 'Protector', 'Topper', 'Pillow case', 'Pet', 'Bedsheet', 'Comforter/blanket', 'Other']
    cities = L('cities')
    cnt = {r[1]: int(r[5]) for r in cities if r[0] == 'CNT'}
    t3 = defaultdict(lambda: {'o': z(), 'r': z(), 's': ''}); cty = defaultdict(lambda: {'o': z(), 'm': z(), 't': ''})
    CITYN = {'BANGALORE': 'Bengaluru', 'BENGALURU': 'Bengaluru', 'GURGAON': 'Gurugram'}
    for kind, tier, ct, s, m, n, r in cities:
        if kind == 'T3': e = t3[ct.title()]; e['o'][mi[m]] += int(n); e['r'][mi[m]] += f(r); e['s'] = SN(s)
        if kind in ('CITY', 'CITYMAT'):
            e = cty[CITYN.get(ct, ct.title())]; e['t'] = tier
            e['o' if kind == 'CITY' else 'm'][mi[m]] += int(n)
    OUT['geo'] = {
      'stateRev': [row(s, stR[s], 'L', tip=[f'{x:,} orders' for x in stO[s]]) for s in sR[:15]],
      'stateOrders': [row(s, stO[s], 'int') for s in sorted(stO, key=lambda k: -sum(stO[k])) if s != 'Unknown'][:15],
      'sepRank': [{'s': s, 'r': stR[s][3], 'o': stO[s][3]} for s in sorted(stR, key=lambda k: -stR[k][3]) if s != 'Unknown'][:15],
      'pos': [row(s, pos[s]['r'], 'L', tip=[f"{x:,} orders" for x in pos[s]['o']]) for s in sorted(pos, key=lambda k: -sum(pos[k]['r'])) if s != 'Unknown'][:10],
      'stateAttach': [row(s, [stA[s][i] / stM[s][i] * 100 if stM[s][i] else None for i in range(4)], 'pct1', 'rate', tip=[f'{x:,} mattress orders' for x in stM[s]]) for s in sM[:12]],
      'top5': [{'s': s, 'opd': per_day(stO[s])} for s in sorted(stO, key=lambda k: -sum(stO[k]))[:5]],
      'tiers': TIERS, 'tierLabel': [TL.get(t, t) for t in TIERS],
      'tierOrders': [row(TL.get(t, t), tO[t], 'int') for t in TIERS],
      'tierMattPct': [row(TL.get(t, t), [tM[t][i] / tO[t][i] * 100 for i in range(4)], 'pct1', 'rate', g=0) for t in TIERS],
      'tierAttach': [row(TL.get(t, t), [tA[t][i] / tM[t][i] * 100 for i in range(4)], 'pct1', 'rate', tip=[f'{x:,} mattress orders' for x in tM[t]]) for t in TIERS],
      'tierNM': [row(TL.get(t, t), tNM[t], 'int') for t in TIERS],
      'tierRpd': {t: per_day(tR[t]) for t in TIERS}, 'tierOpd': {t: per_day(tO[t]) for t in TIERS}, 'tierNMpd': {t: per_day(tNM[t]) for t in TIERS},
      'tierAOV': {t: [tR[t][i] / tO[t][i] for i in range(4)] for t in TIERS},
      'mattType': {t: {k: tk[t]['MT:' + k] for k in MT} for t in TIERS},
      'nmMix': {t: {k: tk[t]['NM:' + k] for k in NM} for t in TIERS},
      'nmFull': [row(TL.get(t, t) + ' · ' + k, tk[t]['NM:' + k], 'int') for t in TIERS for k in NM],
      'cityCount': {t: cnt.get(t) for t in TIERS},
      'tierTot': {t: sum(tO[t]) for t in TIERS}, 'tierMattTot': {t: sum(tM[t]) for t in TIERS},
      't3': [row(c + ' <span class="sub">' + t3[c]['s'] + '</span>', t3[c]['o'], 'int', tip=[f'₹{x/1e5:.2f}L' for x in t3[c]['r']]) for c in sorted(t3, key=lambda k: -sum(t3[k]['r']))],
      'cityMatt': [row(c, cty[c]['m'], 'int', tip=[f'{cty[c]["o"][i]:,} orders in total' for i in range(4)]) for c in sorted(cty, key=lambda k: -sum(cty[k]['m']))],
      'posO': POS_O, 'posR': POS_R, 'MT': MT, 'NM': NM}

    # ---------------- ads ----------------
    ads = []
    for m, sp, pu, rv, cl, im, atc, act, sc, wk, wa, stp, stsp in L('meta'):
        sp, pu, rv = f(sp), f(pu), f(rv)
        ads.append({'m': LAB[mi[m]], 'spend': sp, 'purch': pu, 'rev': rv, 'roas': rv / sp, 'cpa': sp / pu, 'ctr': int(cl) / int(im) * 100,
                    'active': int(act), 'scale': int(sc), 'working': int(wk), 'watch': int(wa), 'stop': int(stp), 'stopSpend': f(stsp)})
    OUT['ads'] = ads

    # ---------------- health ----------------
    OUT['health'] = {'onlineRpd': per_day(R), 'posRpd': per_day(POS_R), 'onlineOpd': per_day(O), 'posOpd': per_day(POS_O)}

    return OUT


# ---------------- retention + cart recovery (phone-keyed, see sleepycat-retention-scope-decision.md) ----------------
_OWNED = """with w as (select right(regexp_replace(coalesce(nullif(PHONE,''), CUSTOMER:phone::string, SHIPPING_ADDRESS:phone::string, BILLING_ADDRESS:phone::string),'[^0-9]',''),10) p, date(convert_timezone('Asia/Kolkata',CREATED_AT)) d, 0 store
  from SLEEPYCAT_DB.MAPLEMONK.SHOPIFY_ALL_ORDERS where SOURCE_NAME in ('256945782785','web','326345687041') and CANCELLED_AT is null and date(convert_timezone('Asia/Kolkata',CREATED_AT)) <= '{T}'),
s1 as (select right(regexp_replace(coalesce(nullif(PHONE,''), CUSTOMER:phone::string, SHIPPING_ADDRESS:phone::string, BILLING_ADDRESS:phone::string),'[^0-9]',''),10) p, date(convert_timezone('Asia/Kolkata',CREATED_AT)) d, 1 store
  from SLEEPYCAT_DB.MAPLEMONK.SHOPIFY_ALL_ORDERS where SOURCE_NAME='266308321281' and CANCELLED_AT is null and date(convert_timezone('Asia/Kolkata',CREATED_AT)) <= '{T}'),
s2 as (select distinct right(regexp_replace(CONTACT_NUM,'[^0-9]',''),10) p, try_to_date(left(ORDER_DATE,10)) d, 1 store, ORDER_ID from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_EASYECOM_FACT_ITEMS where upper(MARKETPLACE) in ('QUEUEBUSTER','OFFLINE') and try_to_date(left(ORDER_DATE,10)) <= '{T}'),
o2 as (select p,d,store from (select p,d,store from w union all select p,d,store from s1 union all select p,d,store from s2) where length(p)=10 and p<>'9999999999' and d is not null),
first as (select p, min(d) fd, min_by(store, d) fstore from o2 group by 1),
coh as (select p, fd, date_trunc('month',fd) c from first where fstore=0)"""
SQL['ret_cohort'] = _OWNED + """,
x as (select coh.c, coh.p, datediff('month',coh.c,date_trunc('month',o2.d)) k, max(iff(o2.store=0,1,0)) web from o2 join coh on coh.p=o2.p where o2.d >= dateadd(day,3,coh.fd) group by 1,2,3)
select to_char(c,'YYYY-MM') m, (select count(*) from coh c2 where c2.c=x.c) size, listagg(w, ',') within group (order by k) web, listagg(a, ',') within group (order by k) owned
from (select c, k, sum(web) w, count(*) a from x group by 1,2) x where c >= '2025-08-01' group by c order by c"""
SQL['ret_120'] = _OWNED + """,
r as (select coh.p, coh.c, coh.fd, max(iff(o2.d between dateadd(day,3,coh.fd) and dateadd(day,120,coh.fd),1,0)) ra, max(iff(o2.store=0 and o2.d between dateadd(day,3,coh.fd) and dateadd(day,120,coh.fd),1,0)) rw from coh join o2 on o2.p=coh.p group by 1,2,3)
select to_char(c,'YYYY-MM') m, count(*) n, sum(ra) ra, sum(rw) rw from r where c >= '2025-08-01' and dateadd(day,120,last_day(c)) <= '{T}' group by 1 order by 1"""
SQL['ret_monthly'] = """with w as (select right(regexp_replace(coalesce(nullif(PHONE,''), CUSTOMER:phone::string, SHIPPING_ADDRESS:phone::string, BILLING_ADDRESS:phone::string),'[^0-9]',''),10) p, convert_timezone('UTC',CREATED_AT)::timestamp_ntz t
  from SLEEPYCAT_DB.MAPLEMONK.SHOPIFY_ALL_ORDERS where SOURCE_NAME in ('256945782785','web','326345687041') and CANCELLED_AT is null),
f as (select p, min(t) fwt from w where length(p)=10 and p<>'9999999999' group by 1)
select to_char(convert_timezone('UTC','Asia/Kolkata',w.t),'YYYY-MM') m, count(*) orders, count_if(dateadd(day,3,f.fwt) <= w.t) rep3, count_if(date(f.fwt) < date(w.t)) repday
from w left join f on f.p=w.p where convert_timezone('UTC','Asia/Kolkata',w.t)::date between '2025-08-01' and '{T}' group by 1 order by 1"""
SQL['recovery'] = """with ck as (select ORDER_ID, min(to_timestamp(CREATED_AT)) t, max(AMOUNT)/100 amt, max(iff(STATUS in ('captured','refunded'),1,0)) paid, right(regexp_replace(max(CONTACT),'[^0-9]',''),10) p
  from SLEEPYCAT_DB.MAPLEMONK.RAZORPAY_PAYMENTS where ORDER_ID is not null group by 1),
ab as (select * from ck where paid=0 and length(p)=10 and p<>'9999999999' and convert_timezone('UTC','Asia/Kolkata',t)::date between '{S}' and '{T}'),
so as (select right(regexp_replace(coalesce(nullif(PHONE,''), CUSTOMER:phone::string, SHIPPING_ADDRESS:phone::string, BILLING_ADDRESS:phone::string),'[^0-9]',''),10) p, convert_timezone('UTC', CREATED_AT)::timestamp_ntz t, TOTAL_PRICE::float v, SOURCE_NAME s
  from SLEEPYCAT_DB.MAPLEMONK.SHOPIFY_ALL_ORDERS where CANCELLED_AT is null and SOURCE_NAME in ('256945782785','web','326345687041','266308321281')),
rec as (select ab.ORDER_ID, min(so.t) rt, min_by(so.v, so.t) rv, min_by(so.s, so.t) rs from ab join so on so.p=ab.p and so.t > ab.t and so.t <= dateadd(day,14,ab.t) and so.s<>'266308321281' group by 1),
prior as (select distinct ab.ORDER_ID from ab join so on so.p=ab.p and so.t < ab.t),
x as (select ab.*, rec.rt, rec.rv, rec.rs, iff(prior.ORDER_ID is null,0,1) returning, datediff('minute', ab.t, rec.rt)/60 hrs from ab left join rec using(ORDER_ID) left join prior using(ORDER_ID))
select to_char(convert_timezone('UTC','Asia/Kolkata', t),'YYYY-MM') m, count(*) abandoned, count(rt) recovered, round(sum(amt)) ab_value, round(sum(iff(rt is not null, rv,0))) rec_value,
 count_if(hrs<1) h1, count_if(hrs>=1 and hrs<6) h6, count_if(hrs>=6 and hrs<24) h24, count_if(hrs>=24 and hrs<72) d3, count_if(hrs>=72 and hrs<168) d7, count_if(hrs>=168) d14,
 count_if(rt is not null and abs(rv-amt)<=0.05*amt) same_v, count_if(rt is not null and rv<0.95*amt) less_v, count_if(rt is not null and rv>1.05*amt) more_v,
 sum(returning) ret_ab, count_if(returning=1 and rt is not null) ret_rec, count_if(rs='326345687041') rec_gokwik,
 count_if(amt>=15000) big_ab, count_if(amt>=15000 and rt is not null) big_rec, count_if(amt<5000) small_ab, count_if(amt<5000 and rt is not null) small_rec
from x group by 1 order by 1"""

def build_extra(rows, through):
    """Retention (cohorts, monthly new vs repeat, 120-day) and cart recovery. through = last closed day."""
    M, LAB, DAYS, p = window(through)
    mi = {m: i for i, m in enumerate(M)}
    lab = lambda m: calendar.month_abbr[int(m[5:])] + ' ' + m[2:4]
    pad = lambda a: (a + [0] * 12)[:12]
    CD, M1 = [], []
    for m, size, web, own in rows['ret_cohort']:
        size = int(size); w = [int(x) for x in str(web).split(',')]; o = [int(x) for x in str(own).split(',')]
        y, mo = int(m[:4]), int(m[5:])
        ready = (through.year - y) * 12 + (through.month - mo) + (1 if through.day == calendar.monthrange(through.year, through.month)[1] else 0)
        CD.append({'m': lab(m), 'size': size, 'web': pad(w), 'owned': pad(o), 'ready': max(0, min(ready, 12))})
        if ready >= 1: M1.append({'m': lab(m), 'web': round(w[0] / size * 100, 2), 'owned': round(o[0] / size * 100, 2)})
    MR, RS = [], []
    for m, orders, rep3, repday in rows['ret_monthly']:
        o, r = int(orders), int(repday)
        MR.append({'m': lab(m), 'new': o - r, 'repeat': r}); RS.append({'m': lab(m), 'pct': round(r / o * 100, 1), 'repeat': r})
    R120 = [{'m': lab(m), 'n': int(n), 'all': int(ra), 'web': int(rw)} for m, n, ra, rw in rows['ret_120']]
    z = lambda: [0, 0, 0, 0]
    K = ['ab', 'rec', 'abv', 'recv', 'h1', 'h6', 'h24', 'd3', 'd7', 'd14', 'same', 'less', 'more', 'retab', 'retrec', 'recgk', 'bigab', 'bigrec', 'smab', 'smrec']
    R = {k: z() for k in K}
    for r in rows['recovery']:
        if r[0] not in mi: continue
        for k, v in zip(K, r[1:]): R[k][mi[r[0]]] = float(v or 0)
    rate = lambda a, b: [R[a][i] / R[b][i] * 100 if R[b][i] else None for i in range(4)]
    def row(k, v, fmt, d='vol', g=1, **kw):
        x = {'k': k, 'v': v, 'f': fmt, 'd': d, 'g': g}; x.update(kw); return x
    REC = {'table': [
        row('Abandoned checkouts (unpaid)', R['ab'], 'int', g=-1, b=1), row('Recovered within 14 days', R['rec'], 'int'),
        row('Recovery rate', rate('rec', 'ab'), 'pct1', 'rate', b=1),
        row('Value left unpaid', R['abv'], 'L', g=-1), row('Value recovered', R['recv'], 'L'),
        row('Recovery rate · carts ₹15k+', rate('bigrec', 'bigab'), 'pct1', 'rate'),
        row('Recovery rate · carts under ₹5k', rate('smrec', 'smab'), 'pct1', 'rate'),
        row('Recovery rate · returning customers', rate('retrec', 'retab'), 'pct1', 'rate'),
        row('↳ recovered through GoKwik', R['recgk'], 'int', g=0)],
        'raw': R}
    return {'RET': {'CD': CD[::-1], 'M1': M1, 'MR': MR, 'RS': RS, 'R120': R120, 'through': through.isoformat()}, 'recovery': REC}
