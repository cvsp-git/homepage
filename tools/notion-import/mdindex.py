import os,re,unicodedata as u,collections,sys
def N(t): return u.normalize('NFC',t)
def norm(s): return re.sub(r'\s+',' ',s or '').strip()
KEYS=('post_type','badges','date','image','is_hidden','display_string','post_title','created','link')
def parse(path):
    t=open(path,encoding='utf-8').read().replace('\r\n','\n')
    lines=t.split('\n'); title=lines[0][2:] if lines[0].startswith('# ') else ''
    i=1
    while i<len(lines) and not lines[i].strip(): i+=1
    props={};cur=None
    while i<len(lines):
        l=lines[i]
        if not l.strip(): break
        m=re.match(r'^([a-z_]+): ?(.*)$',l)
        if m and m.group(1) in KEYS: cur=m.group(1); props[cur]=m.group(2)
        elif cur=='display_string': props[cur]+='\n'+l
        else: break
        i+=1
    body='\n'.join(lines[i:]).strip('\n')
    m=re.search(r'([0-9a-f]{32})\.md$',path)
    return dict(id=m.group(1) if m else None,path=path,dir=os.path.dirname(path),title=title,props=props,body=body)
def load(root):
    out=[]
    for dp,_,fs in os.walk(root):
        for f in fs:
            if f.endswith('.md'): out.append(parse(os.path.join(dp,f)))
    return out
if __name__=='__main__':
    mds=load(sys.argv[1])
    k=collections.Counter((norm(m['title']),norm(m['props'].get('date')),norm(m['props'].get('display_string'))) for m in mds)
    print(len(mds),'dupe keys:',[x for x,c in k.items() if c>1])
    print(collections.Counter(m['props'].get('post_type') for m in mds))
    print('empty body',sum(1 for m in mds if not m['body']))
