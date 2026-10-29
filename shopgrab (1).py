# Pull every ShopifyQL result in this session's transcript into sale/shop/all.json {query: {cols, rows}}
import json, glob
base = '/root/.claude/projects/-home-claude/'
import os
P = '/home/claude/sc/sale/shop/all.json'
out = json.load(open(P)) if os.path.exists(P) else {}   # merge: never drop earlier results
for f in glob.glob(base + '**/*.jsonl', recursive=True):
    for line in open(f):
        if '"shopDomain' not in line or 'tool_result' not in line: continue
        try: d = json.loads(line)
        except Exception: continue
        for c in (d.get('message', {}) or {}).get('content', []) or []:
            if not (isinstance(c, dict) and c.get('type') == 'tool_result'): continue
            cc = c.get('content'); t = cc if isinstance(cc, str) else ''.join(x.get('text', '') for x in cc if isinstance(x, dict))
            if '"shopDomain' not in t: continue
            try: j = json.loads(t[t.find('{'):])
            except Exception: continue
            out[j['query']] = {'cols': [x['name'] for x in j['columns']], 'rows': j['rows']}
json.dump(out, open('/home/claude/sc/sale/shop/all.json', 'w'))
for q in out: print(len(out[q]['rows']), q[:150])
