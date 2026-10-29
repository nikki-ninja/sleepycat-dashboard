"""Snowflake extracts for sale.html (build_sale_dash.py reads <dfolder>/s_<name>.json). {T} = data-through date.
Each entry is a list of SQL strings whose rows are concatenated (split where a single result would pass the 4,000-row cap).
Periods: BAU = Sep 1-21 + Oct 1-6, EVE = Oct 7, SALE = Oct 8 onward, X = anything else (Sep 22-30)."""
D2C = "('256945782785','web','326345687041')"; POS = "'266308321281'"
WEBAPP = "(256945782785,580111,326345687041)"; ALLAPP = "(256945782785,580111,326345687041,266308321281)"
def PER(d): return (f"case when {d} between '2026-09-01' and '2026-09-21' or {d} between '2026-10-01' and '2026-10-06' then 'BAU' "
                    f"when {d}='2026-10-07' then 'EVE' when {d}>='2026-10-08' then 'SALE' else 'X' end")
ORD = f"""o as (select ID, SOURCE_NAME sn, TOTAL_PRICE::float p, coalesce(TOTAL_DISCOUNTS::float,0) disc, DISCOUNT_CODES dc, to_varchar(PAYMENT_GATEWAY_NAMES) gw,
  CANCELLED_AT ca, convert_timezone('Asia/Kolkata',CREATED_AT) t, date(convert_timezone('Asia/Kolkata',CREATED_AT)) d
  from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_ORDERS where SOURCE_NAME in ('256945782785','web','326345687041',{POS})
  and date(convert_timezone('Asia/Kolkata',CREATED_AT)) between '2026-09-01' and '{{T}}')"""
GD = "gd as (select ID, max(GOKWIK_UTM_SOURCE) gs, max(GOKWIK_UTM_MEDIUM) gm, max(GOKWIK_UTM_CAMPAIGN) gc from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_GOKWIK_SOURCE group by 1)"
SRC = "upper(coalesce(nullif(trim(gd.gs),''), nullif(trim(c.CHECKOUT_UTM_SOURCE),''),'UNATTRIB'))"
MED = "upper(coalesce(nullif(trim(gd.gm),''), nullif(trim(c.CHECKOUT_UTM_MEDIUM),''),''))"
CAMP = "coalesce(nullif(trim(gd.gc),''), nullif(trim(c.CHECKOUT_UTM_CAMPAIGN),''),'')"
UJOIN = "left join SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_CHECKOUT_SOURCE c on c.ID=o.ID left join gd on gd.ID=o.ID"
# order-level product classes from line items (toppers sit in the MATTRESSES category, so classify by name first)
LI = f"""li as (select ORDER_ID, max(date(ORDER_TIMESTAMP)) over (partition by ORDER_ID) d, iff(APP_ID=266308321281,'S','W') ch, QUANTITY q, TOTAL_SALES::float s,
  upper(coalesce(PRODUCT_NAME_FINAL, PRODUCT_NAME, '')) nm, PRODUCT_CATEGORY cat, PRODUCT_SUB_CATEGORY sub, upper(trim(STATE)) st, upper(trim(CITY)) ct,
  case when upper(coalesce(PRODUCT_NAME_FINAL,PRODUCT_NAME,'')) like '%TOPPER%' or PRODUCT_SUB_CATEGORY ilike '%TOPPER%' then 256
       when PRODUCT_SUB_CATEGORY='MATTRESS PROTECTOR' or upper(coalesce(PRODUCT_NAME_FINAL,PRODUCT_NAME,'')) like '%PROTECTOR%' then 128
       when PRODUCT_CATEGORY in ('MATTRESS','MATTRESSES') then 1
       when PRODUCT_SUB_CATEGORY='DOG BED COVER' or PRODUCT_CATEGORY in ('PET BED','PET MAT') then 16
       when PRODUCT_CATEGORY in ('BEDDING','COVER') then 2 when PRODUCT_CATEGORY='PILLOW' then 4 when PRODUCT_CATEGORY='CASE' then 8
       when PRODUCT_CATEGORY in ('BED','RECLINER') then 32 else 64 end b
  from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_SHOPIFY_FACT_ITEMS where APP_ID in {ALLAPP} and ORDER_STATUS<>'CANCELLED'
  and date(ORDER_TIMESTAMP) between '{{LO}}' and '{{T}}')"""
GRP = "case b when 1 then 'Mattress' when 256 then 'Topper' when 128 then 'Protector' when 2 then 'Bedding' when 4 then 'Pillow' when 8 then 'Pillow case' when 16 then 'Pet' when 32 then 'Furniture' else 'Ergo & other' end"
PNAME = r"coalesce(nullif(sub,''), nullif(trim(regexp_replace(nm, '\\s*\\(.*\\)\\s*$', '')),''), cat)"
SQL = {
 's_utm': [f"""with {GD}, {ORD}
select to_varchar(o.d), {SRC}, {MED}, '', count(*), round(sum(o.p)) from o {UJOIN} where o.sn in {D2C} and o.ca is null group by 1,2,3 order by 1"""],
 's_utm_camp': [f"""with {GD}, {ORD}
select {PER('o.d')} pr, {SRC}, {MED}, {CAMP} cp, count(*), round(sum(o.p)) from o {UJOIN} where o.sn in {D2C} and o.ca is null and cp<>'' group by 1,2,3,4 having pr in ('BAU','SALE')"""],
 's_ga4': ["""select DATE, sum(SESSIONS), sum(ENGAGEDSESSIONS), sum(ADDTOCARTS), sum(CHECKOUTS) from SLEEPYCAT_DB.MAPLEMONK.GA4_SC_GA4_SESSIONS_BY_DATE_SOURCE
where DATE between '20260901' and replace('{T}','-','') group by 1 order by 1"""],
 's_day': [f"""with {ORD}
select to_varchar(d), case when sn='326345687041' then 'G' when sn={POS} then 'S' else 'R' end ch, coalesce(gw,''), count_if(ca is null), count_if(ca is not null),
 round(sum(iff(ca is null,p,0))), round(sum(iff(ca is null,disc,0))), count_if(ca is null and array_size(dc)>0) from o group by 1,2,3 order by 1"""],
 's_disc': [f"""with {ORD}, x as (select o.d, o.p, upper(trim(f.value:code::string)) code, f.value:amount::float amt from o, lateral flatten(input=>o.dc) f where o.sn in {D2C} and o.ca is null)
select {PER('d')} pr, 'W', code, count(*), round(sum(amt)), round(sum(p)) from x group by 1,2,3"""],
 's_nr': [f"""select to_varchar(d), ch, iff(fl='Repeat','Repeat','New'), count(*), round(sum(s)) from (select ORDER_ID, max(date(ORDER_TIMESTAMP)) d, iff(max(APP_ID)=266308321281,'S','W') ch,
 max(SHOPIFY_NEW_CUSTOMER_FLAG) fl, sum(TOTAL_SALES) s from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_SHOPIFY_FACT_ITEMS where APP_ID in {ALLAPP} and ORDER_STATUS<>'CANCELLED'
 and date(ORDER_TIMESTAMP) between '2026-09-01' and '{{T}}' group by 1) group by 1,2,3 order by 1"""],
 's_mkt_day': ["""select to_varchar(DATE), CHANNEL, round(sum(SPEND)), sum(IMPRESSIONS), sum(CLICKS), sum(CONVERSIONS), round(sum(CONVERSION_VALUE)), round(sum(SHOPIFY_REVENUE))
from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_MARKETING_CONSOLIDATED where CHANNEL in ('FACEBOOK','GOOGLE') and DATE between '2026-09-01' and '{T}' group by 1,2 order by 1"""],
 's_basket': [f"""with {LI.replace('{LO}', '2026-09-01')}, o as (select ORDER_ID, max(d) d, max(ch) ch, sum(q) u, sum(s) s, bitor_agg(b) mk from li group by 1)
select to_varchar(d), ch, count(*), sum(u), round(sum(s)), count_if(bitand(mk,1)>0), count_if(bitand(mk,1)>0 and bitand(mk,{2|4|8|128|256})>0),
 count_if(bitand(mk,1)>0 and bitand(mk,{2|8|128|256})>0), count_if(bitand(mk,1)=0 and bitand(mk,{2|4|8|128|256})>0) from o group by 1,2 order by 1"""],
 's_hour': [f"""with {ORD}
select to_varchar(d), hour(t), iff(sn={POS},'S','W'), count(*), round(sum(p)) from o where ca is null group by 1,2,3 order by 1"""],
 's_prod': [f"""with {LI.replace('{LO}', '2026-09-01')}
select 'BAU', ch, {GRP}, {PNAME}, count(distinct ORDER_ID), sum(q), round(sum(s)) from li where {PER('d')}='BAU' group by 1,2,3,4""",
  f"""with {LI.replace('{LO}', '2026-10-07')}
select to_varchar(d), ch, {GRP}, {PNAME}, count(distinct ORDER_ID), sum(q), round(sum(s)) from li where d between '2026-10-07' and '2026-10-17' group by 1,2,3,4""",
  f"""with {LI.replace('{LO}', '2026-10-18')}
select to_varchar(d), ch, {GRP}, {PNAME}, count(distinct ORDER_ID), sum(q), round(sum(s)) from li where d between '2026-10-18' and '{{T}}' group by 1,2,3,4"""],
 's_geo_state': [f"""with {LI.replace('{LO}', '2026-09-01')}, o as (select ORDER_ID, max(d) d, max(ch) ch, max(st) st, sum(s) s, max(iff(b=1,1,0)) m from li group by 1)
select {PER('d')} pr, ch, coalesce(st,''), count(*), round(sum(s)), sum(m) from o group by 1,2,3 having pr in ('BAU','SALE')"""],
 's_geo_city': [f"""with {LI.replace('{LO}', '2026-09-01')}, o as (select ORDER_ID, max(d) d, max(ch) ch, max(st) st, max(ct) ct, sum(s) s, max(iff(b=1,1,0)) m from li group by 1)
select {PER('d')} pr, ch, coalesce(ct,''), coalesce(st,''), count(*), round(sum(s)), sum(m) from o where ch='W' group by 1,2,3,4 having pr in ('BAU','SALE') and count(*)>=2"""],
 's_mkt_camp': ["""select CHANNEL, to_varchar(CAMPAIGN_ID), max(CAMPAIGN_NAME), round(sum(SPEND)), round(sum(CONVERSION_VALUE))
from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_MARKETING_CONSOLIDATED where CHANNEL in ('FACEBOOK','GOOGLE') and DATE between '2026-10-08' and '{T}' group by 1,2 having sum(SPEND)>0"""],
}
def get(T): return {k: [s.replace('{T}', T) for s in v] for k, v in SQL.items()}
