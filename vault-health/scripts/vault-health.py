import os, re, json, sys
V = sys.argv[1]
SKIP = {'.obsidian', '.trash', 'attachments'}
notes = {}
for root, dirs, files in os.walk(V):
    dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith('.')]
    for f in files:
        if f.endswith('.md'):
            rel = os.path.relpath(os.path.join(root, f), V)
            notes[rel] = open(os.path.join(root, f), encoding='utf-8').read()
allfiles = set()
for root, dirs, files in os.walk(V):
    dirs[:] = [d for d in dirs if d != '.obsidian']
    for f in files: allfiles.add(os.path.relpath(os.path.join(root, f), V))
bybase = {}
for p in allfiles:
    b = os.path.basename(p); bybase.setdefault(b, []).append(p)
    if b.endswith('.md'): bybase.setdefault(b[:-3], []).append(p)
LINK = re.compile(r'(?<!!)\[\[([^\]|#^]+)(?:[#^][^\]|]*)?(?:\\?\|[^\]]*)?\]\]')
def strip_code(s): return re.sub(r'```.*?```', '', re.sub(r'`[^`\n]*`', '', s, flags=re.S), flags=re.S)
def resolve(src, t):
    t = t.strip().rstrip('\\')
    cands = [t, t + '.md', os.path.normpath(os.path.join(os.path.dirname(src), t)), os.path.normpath(os.path.join(os.path.dirname(src), t)) + '.md']
    for c in cands:
        if c in allfiles: return c
    b = os.path.basename(t)
    hits = bybase.get(b) or bybase.get(b + '.md')
    return hits[0] if hits else None
out = {n: set() for n in notes}; inc = {n: set() for n in notes}; broken = []
for n, s in notes.items():
    if n.startswith(('_templates/','_skills/')): continue
    for m in LINK.finditer(strip_code(s)):
        r = resolve(n, m.group(1))
        if r is None: broken.append((n, m.group(1)))
        elif r in notes:
            out[n].add(r); inc[r].add(n)
real = [n for n in notes if not n.startswith(('_templates/','AI-Context/','_skills/')) and n != 'inbox.md' and not n.endswith('.excalidraw.md')]
orphans = [n for n in real if not out[n] and not inc[n]]
no_in = [n for n in real if not inc[n] and n != 'INDEX.md' and n not in orphans]
# hub-spoke
idx = notes.get('INDEX.md', '')
hub_issues = []; missing_index = []
if os.path.isdir(os.path.join(V, 'projects')):
    for p in sorted(os.listdir(os.path.join(V, 'projects'))):
        pd = os.path.join('projects', p)
        if not os.path.isdir(os.path.join(V, pd)): continue
        pn = [n for n in notes if n.startswith(pd + '/')]
        hub = pd + '/overview.md' if pd + '/overview.md' in notes else None
        if not hub:
            ref = [r for r in out.get('INDEX.md', []) if r.startswith(pd + '/')]
            hub = ref[0] if ref else None
        if not hub: missing_index.append(pd); continue
        if hub not in out.get('INDEX.md', set()): missing_index.append(pd)
        for n in pn:
            if n != hub and hub not in out[n]: hub_issues.append((n, hub))
# concept notes
concept = []
for n in notes:
    if n.startswith('resources/concepts/'):
        s = notes[n]
        srcs = [r for r in out[n] if not r.startswith('resources/')]
        rel = [r for r in out[n] if r.startswith('resources/concepts/')]
        listed = n in out.get('resources/overview.md', set())
        miss = []
        if not srcs: miss.append('출처 링크 없음')
        if not rel: miss.append('다른 개념 노트 연결 없음')
        if not listed: miss.append('resources/overview 목록에 없음')
        if miss: concept.append((n, miss))
# color groups
cg_missing = []
try:
    g = json.load(open(os.path.join(V, '.obsidian/graph.json')))
    qs = ' '.join(x['query'] for x in g.get('colorGroups', []))
    for top in ['projects', 'school']:
        tp = os.path.join(V, top)
        if os.path.isdir(tp):
            for d in os.listdir(tp):
                if os.path.isdir(os.path.join(tp, d)) and top == 'projects' and f'path:"{top}/{d}"' not in qs:
                    cg_missing.append(f'{top}/{d}')
    for top in ['resources', 'archive']:
        if os.path.isdir(os.path.join(V, top)) and f'path:"{top}"' not in qs: cg_missing.append(top)
except Exception as e:
    cg_missing.append(f'(graph.json 읽기 실패: {e})')
inbox_lines = len([l for l in notes.get('inbox.md', '').splitlines() if l.strip()])
print(json.dumps({
 'notes': len(real), 'broken': broken, 'orphans': orphans, 'no_backlinks': no_in,
 'hub_issues': hub_issues, 'missing_index': missing_index, 'concept': concept,
 'color_missing': cg_missing, 'inbox_lines': inbox_lines}, ensure_ascii=False, indent=1))
