"""Snowflake results cache. Every mcp__Snowflake__sql_exec_tool call in this session's transcripts (main + subagents)
is indexed by a normalised SQL key, so a build can be re-run without re-querying."""
import json, glob, hashlib, re, os
BASE = '/root/.claude/projects/-home-claude/'
CACHE = '/home/claude/sc/build/cache/'
def key(sql): return hashlib.sha1(re.sub(r'\s+', ' ', sql).strip().encode()).hexdigest()[:16]
def grab():
    uses, n = {}, 0
    for f in glob.glob(BASE + '**/*.jsonl', recursive=True):
        for line in open(f, errors='ignore'):
            if 'sql_exec_tool' not in line and '"query_id"' not in line and 'resultSetMetaData' not in line: continue
            try: d = json.loads(line)
            except Exception: continue
            for c in (d.get('message') or {}).get('content') or []:
                if not isinstance(c, dict): continue
                if c.get('type') == 'tool_use' and 'sql_exec_tool' in c.get('name', ''):
                    uses[c['id']] = c['input'].get('sql', '')
                elif c.get('type') == 'tool_result' and c.get('tool_use_id') in uses:
                    cc = c.get('content'); t = cc if isinstance(cc, str) else ''.join(x.get('text', '') for x in cc if isinstance(x, dict))
                    m = re.search(r'(/root/\.claude/projects/\S+?tool-results/\S+?\.(?:txt|json))', t)
                    if m and os.path.exists(m.group(1)): t = open(m.group(1)).read()
                    try: j = json.loads(t[t.find('{'):])
                    except Exception:
                        try: j = json.loads(json.loads(t)[0]['text'])
                        except Exception: print('WARN unparsed', t[:120]); continue
                    rs = j.get('result_set') or {}
                    if 'data' not in rs: continue
                    rows = rs['data']; meta = rs.get('resultSetMetaData', {})
                    if meta.get('numRows') is not None and meta['numRows'] != len(rows):
                        print('WARN partial result', meta['numRows'], len(rows)); continue
                    if len(rows) >= 4000: print('WARN 4000-row cap hit')
                    k = key(uses[c['tool_use_id']])
                    json.dump({'sql': uses[c['tool_use_id']], 'rows': rows}, open(CACHE + k + '.json', 'w')); n += 1
    return n
def get(sql):
    p = CACHE + key(sql) + '.json'
    return json.load(open(p))['rows'] if os.path.exists(p) else None
if __name__ == '__main__': print('grabbed', grab())
