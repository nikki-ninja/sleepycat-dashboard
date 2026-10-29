"""Diwali sale tracker (SC_DATA.SALE). Sale Oct 8 – Nov 21, 2026; Diwali Nov 8, 2026.
Target: Rs 80 lakh a day, D2C online + stores, order value incl. tax, cancelled orders excluded.
Last year is aligned by days to Diwali (Diwali 2025 = Oct 20), i.e. each sale day is compared with
the 2025 date 384 days earlier. Used by build_data.py."""
import datetime

START, END = datetime.date(2026, 10, 8), datetime.date(2026, 11, 21)
DIWALI, LY_DIWALI = datetime.date(2026, 11, 8), datetime.date(2025, 10, 20)
TARGET = 8_000_000            # Rs per day, D2C + stores
PRE_DAYS = 7                  # pre-sale days shown before the sale
SHIFT = (DIWALI - LY_DIWALI).days         # 384: same days-to-Diwali last year

# Last year, fixed history. D2C = SLEEPYCAT_DB_ORDERS web + Razorpay checkout, not cancelled ("date orders revenue").
# Stores = EasyEcom MARKETPLACE='QUEUEBUSTER' (the store POS before Shopify POS took over in Jun-Jul 2026),
# SELLING_PRICE minus CANCEL_SALES ("date orders revenue"). Re-pull with LY_SQL if ever needed.
LY_SQL = {
 "d2c": "select to_varchar(date(convert_timezone('Asia/Kolkata',CREATED_AT))) d, count(*) o, round(sum(TOTAL_PRICE::float)) s from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_ORDERS where SOURCE_NAME in ('256945782785','web','326345687041') and CANCELLED_AT is null and date(convert_timezone('Asia/Kolkata',CREATED_AT)) between '2025-09-01' and '2025-12-15' group by 1",
 "store": "select to_varchar(try_to_date(left(ORDER_DATE,10))) d, count(distinct iff(coalesce(CANCEL_SALES,0)<coalesce(SELLING_PRICE,0) or SELLING_PRICE=0, ORDER_ID, null)) n, round(sum(coalesce(SELLING_PRICE,0)-coalesce(CANCEL_SALES,0))) r from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_EASYECOM_FACT_ITEMS where upper(MARKETPLACE)='QUEUEBUSTER' and try_to_date(left(ORDER_DATE,10)) between '2025-09-01' and '2025-12-15' group by 1"}
LY_D2C = "2025-08-15 122 1351799|2025-08-16 102 844212|2025-08-17 140 1272800|2025-08-18 80 718665|2025-08-19 93 796185|2025-08-20 95 907231|2025-08-21 77 641895|2025-08-22 87 765021|2025-08-23 91 732284|2025-08-24 93 826189|2025-08-25 97 969059|2025-08-26 80 652966|2025-08-27 70 789331|2025-08-28 76 652099|2025-08-29 76 748914|2025-08-30 109 892077|2025-08-31 104 1169420|2025-09-01 111 1058113|2025-09-02 93 747177|2025-09-03 93 774186|2025-09-04 80 747778|2025-09-05 87 836764|2025-09-06 105 878683|2025-09-07 102 834684|2025-09-08 101 761362|2025-09-09 93 809801|2025-09-10 102 915106|2025-09-11 80 817879|2025-09-12 85 873293|2025-09-13 97 1059819|2025-09-14 118 1194301|2025-09-15 90 862673|2025-09-16 82 937846|2025-09-17 79 732165|2025-09-18 70 571359|2025-09-19 80 622549|2025-09-20 78 763486|2025-09-21 80 646440|2025-09-22 256 3133092|2025-09-23 220 2585630|2025-09-24 189 2071575|2025-09-25 189 1908153|2025-09-26 180 2095944|2025-09-27 224 2315149|2025-09-28 253 2687475|2025-09-29 159 1743371|2025-09-30 160 1806436|2025-10-01 191 1984752|2025-10-02 257 2710498|2025-10-03 172 1556496|2025-10-04 185 1879573|2025-10-05 272 2573278|2025-10-06 171 1615001|2025-10-07 154 1448969|2025-10-08 143 1160822|2025-10-09 130 1058336|2025-10-10 136 1333716|2025-10-11 135 1354790|2025-10-12 195 2092052|2025-10-13 164 1729019|2025-10-14 140 1309590|2025-10-15 154 1300860|2025-10-16 166 1521228|2025-10-17 122 1159723|2025-10-18 129 1318624|2025-10-19 135 1233640|2025-10-20 194 1934828|2025-10-21 84 831567|2025-10-22 100 1137372|2025-10-23 103 928647|2025-10-24 92 850797|2025-10-25 127 1355210|2025-10-26 104 950868|2025-10-27 112 1406082|2025-10-28 84 716368|2025-10-29 95 891760|2025-10-30 116 1147948|2025-10-31 91 938712|2025-11-01 123 1094807|2025-11-02 159 1496791|2025-11-03 106 1003207|2025-11-04 90 872150|2025-11-05 105 1024980|2025-11-06 119 1240745|2025-11-07 101 989731|2025-11-08 120 1076472|2025-11-09 101 1032982|2025-11-10 104 1058180|2025-11-11 100 955854|2025-11-12 91 930395|2025-11-13 82 646753|2025-11-14 107 1112776|2025-11-15 129 1189769|2025-11-16 122 1337823|2025-11-17 94 921169|2025-11-18 104 1163135|2025-11-19 98 929353|2025-11-20 109 1048939|2025-11-21 122 950887|2025-11-22 97 840551|2025-11-23 190 1769735|2025-11-24 149 1498894|2025-11-25 158 1347721|2025-11-26 147 1348525|2025-11-27 144 1259154|2025-11-28 184 1848646|2025-11-29 197 1465393|2025-11-30 207 1770794|2025-12-01 169 1448294|2025-12-02 131 1072184|2025-12-03 104 1044676|2025-12-04 90 724218|2025-12-05 83 700638|2025-12-06 103 815536|2025-12-07 133 1402908|2025-12-08 93 1066219|2025-12-09 108 972304|2025-12-10 89 992986|2025-12-11 100 1050237|2025-12-12 83 683312|2025-12-13 136 1077494|2025-12-14 143 1124154|2025-12-15 164 1394594"
LY_STORE = "2025-09-01 61 593809|2025-09-02 63 737235|2025-09-03 53 772600|2025-09-04 46 727872|2025-09-05 59 736316|2025-09-06 87 1099151|2025-09-07 112 1441984|2025-09-08 60 1021951|2025-09-09 52 667644|2025-09-10 48 634071|2025-09-11 49 825072|2025-09-12 56 819775|2025-09-13 77 1092243|2025-09-14 83 1339968|2025-09-15 62 807558|2025-09-16 47 834153|2025-09-17 62 898706|2025-09-18 42 554110|2025-09-19 37 414202|2025-09-20 109 1455865|2025-09-21 157 2058443|2025-09-22 102 1402299|2025-09-23 84 1320490|2025-09-24 84 1224283|2025-09-25 78 1157606|2025-09-26 97 1323343|2025-09-27 176 2510770|2025-09-28 192 2632758|2025-09-29 83 1539535|2025-09-30 72 898682|2025-10-01 95 1227271|2025-10-02 186 2839620|2025-10-03 73 990422|2025-10-04 133 1889698|2025-10-05 164 2492934|2025-10-06 85 1057122|2025-10-07 75 1205100|2025-10-08 64 656801|2025-10-09 62 799832|2025-10-10 60 783965|2025-10-11 122 1584302|2025-10-12 133 1460330|2025-10-13 74 1047072|2025-10-14 68 844902|2025-10-15 48 876274|2025-10-16 64 1099624|2025-10-17 79 1432075|2025-10-18 113 1568115|2025-10-19 150 2355178|2025-10-20 71 1118163|2025-10-21 62 1074790|2025-10-22 69 898593|2025-10-23 65 741063|2025-10-24 63 889918|2025-10-25 114 1548476|2025-10-26 141 2398111|2025-10-27 66 805713|2025-10-28 67 928569|2025-10-29 54 809300|2025-10-30 59 840217|2025-10-31 52 771613|2025-11-01 106 1351293|2025-11-02 114 1532845|2025-11-03 55 627092|2025-11-04 60 786735|2025-11-05 90 1161217|2025-11-06 53 646846|2025-11-07 66 896568|2025-11-08 119 1823759|2025-11-09 142 2013533|2025-11-10 70 1001775|2025-11-11 63 744149|2025-11-12 63 848905|2025-11-13 57 640447|2025-11-14 65 846246|2025-11-15 88 1168231|2025-11-16 146 2444161|2025-11-17 61 1053317|2025-11-18 49 881520|2025-11-19 62 883996|2025-11-20 62 1058424|2025-11-21 65 890056|2025-11-22 108 1830700|2025-11-23 155 2536490|2025-11-24 74 1163288|2025-11-25 72 1094853|2025-11-26 81 1614316|2025-11-27 67 1008726|2025-11-28 83 1403542|2025-11-29 148 2405709|2025-11-30 159 2450898|2025-12-01 82 1128439|2025-12-02 52 638637|2025-12-03 67 929671|2025-12-04 56 824520|2025-12-05 67 908638|2025-12-06 107 1397419|2025-12-07 122 1579443|2025-12-08 76 1049496|2025-12-09 83 1146112|2025-12-10 50 788208|2025-12-11 52 882586|2025-12-12 55 680607|2025-12-13 128 1942744|2025-12-14 128 1755800|2025-12-15 59 771573"

# Daily mattress orders by channel (W = D2C online, S = stores), from the order fact table.
SQL = {"sale_mix": """with o as (select ORDER_ID, max(date(ORDER_TIMESTAMP)) d, iff(max(APP_ID)=266308321281,'S','W') ch, max(iff(PRODUCT_CATEGORY in ('MATTRESS','MATTRESSES'),1,0)) mat
 from SLEEPYCAT_DB.MAPLEMONK.SLEEPYCAT_DB_SHOPIFY_FACT_ITEMS where APP_ID in (256945782785,580111,326345687041,266308321281) and ORDER_STATUS<>'CANCELLED' and date(ORDER_TIMESTAMP) between '{S}' and '{T}' group by 1)
select to_varchar(d) d, ch, count(*) n, sum(mat) m from o group by 1,2 order by 1,2"""}

def params(through):
    return {'S': (START - datetime.timedelta(days=PRE_DAYS)).isoformat(), 'T': min(through, END).isoformat()}

def sql(name, through):
    s = SQL[name]
    for k, v in params(through).items(): s = s.replace('{' + k + '}', v)
    return s

def _ly(s, n_idx, r_idx):
    out = {}
    for rec in s.split('|'):
        p = rec.split(); out[p[0]] = (int(p[n_idx]), int(float(p[r_idx])))
    return out

def build(DAILY, mix_rows, utm_daily, through):
    """DAILY: dashboard daily rows; mix_rows: (date, 'W'|'S', orders, mattress orders); utm_daily: SC_DATA.UTM.daily."""
    ly_w, ly_s = _ly(LY_D2C, 1, 2), _ly(LY_STORE, 1, 2)
    D = {r['date']: r for r in DAILY}
    mix = {}
    for d, ch, n, m in mix_rows: mix.setdefault(str(d), {})[ch] = int(m)
    U = {r['date']: r for r in utm_daily}
    days = []
    d = START - datetime.timedelta(days=PRE_DAYS)
    while d <= END:
        iso = d.isoformat(); ly = (d - datetime.timedelta(days=SHIFT)).isoformat()
        e = {'d': iso, 'pre': int(d < START), 'dtd': (DIWALI - d).days, 'ly': ly,
             'lyW': ly_w.get(ly, (0, 0))[1], 'lyS': ly_s.get(ly, (0, 0))[1], 'lyWo': ly_w.get(ly, (0, 0))[0], 'lySo': ly_s.get(ly, (0, 0))[0]}
        if iso in D and d <= through:
            r = D[iso]
            e.update(wo=r['orders'], wr=r['sales'], so=r['pos_orders'], sr=r['pos_sales'], sess=r['sessions'], atc=r['atc'], gk=r['gk_orders'])
            if iso in mix: e.update(wm=mix[iso].get('W', 0), sm=mix[iso].get('S', 0))
            if iso in U: e.update(paid=U[iso]['PAID']['o'], org=U[iso]['ORGANIC']['o'], own=U[iso]['OWNED']['o'])
        days.append(e); d += datetime.timedelta(days=1)
    # pre-sale baselines: September (closed month) and the last 7 pre-sale days
    sep = [r for r in DAILY if r['date'].startswith('2026-09')]
    base = {'sep': {'n': len(sep), 'w': sum(r['sales'] for r in sep), 's': sum(r['pos_sales'] for r in sep),
                    'wo': sum(r['orders'] for r in sep), 'so': sum(r['pos_orders'] for r in sep)}}
    # same calendar window last year, for context on how last year's sale was shaped
    ly_cal = [(datetime.date(2025, 9, 1) + datetime.timedelta(days=i)).isoformat() for i in range(106)]
    return {'start': START.isoformat(), 'end': END.isoformat(), 'diwali': DIWALI.isoformat(), 'lyDiwali': LY_DIWALI.isoformat(),
            'target': TARGET, 'through': through.isoformat(), 'days': days, 'base': base,
            'lyCal': [[x, ly_w.get(x, (0, 0))[1] + ly_s.get(x, (0, 0))[1]] for x in ly_cal]}
