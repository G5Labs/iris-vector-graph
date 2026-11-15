"""Executable semantic port of the admitted model, with named numeric providers.
The JSON stack/lexer follows json_width.rs. Python json is only the independent oracle.
"""
import math,re

def width(raw):
    if not isinstance(raw,str) or not raw.strip().startswith('['):return None
    z=parse(raw.strip());return None if z is None else z[0]

def parse(t):
    stack=[];lex=('normal',);done=False;outer=None
    def finish(w=None):
        nonlocal lex,done,outer
        lex=('normal',)
        if not stack:done=True;outer=w;return True
        k,n=stack[-1]
        if k in ('first','next'):stack[-1]=('after',n+1);return True
        if k=='value':stack[-1]=('objafter',0);return True
        return False
    def close(w=None):
        if not stack:return False
        stack.pop();return finish(w)
    def begin(c):
        nonlocal lex
        if c=='[':stack.append(('first',0))
        elif c=='{':stack.append(('objfirst',0))
        elif c=='"':lex=('str',False,False,0)
        elif c=='-':lex=('num','sign')
        elif c=='0':lex=('num','zero')
        elif c in '123456789':lex=('num','int')
        elif c in 'tfnNI':lex=('word',{'t':'rue','f':'alse','n':'ull','N':'aN','I':'nfinity'}[c])
        else:return False
        return True
    def normal(c):
        nonlocal lex
        if c in ' \t\n\r':return True
        if done:return False
        if not stack:return begin(c)
        k,n=stack[-1]
        if k=='first':return close(n) if c==']' else begin(c)
        if k=='next':return begin(c)
        if k=='after':
            if c==',':stack[-1]=('next',n);return True
            return close(n) if c==']' else False
        if k in ('objfirst','objnext'):
            if c=='"':lex=('str',True,False,0);return True
            return close() if c=='}' and k=='objfirst' else False
        if k=='colon':
            if c==':':stack[-1]=('value',0);return True
            return False
        if k=='value':return begin(c)
        if k=='objafter':
            if c==',':stack[-1]=('objnext',0);return True
            return close() if c=='}' else False
        return False
    for c in t:
        tag=lex[0];okay=True
        if tag=='normal':okay=normal(c)
        elif tag=='word':
            word=lex[1]
            if not word or c!=word[0]:okay=False
            elif len(word)==1:okay=finish()
            else:lex=('word',word[1:])
        elif tag=='str':
            _,key,escape,unicode=lex
            if unicode:
                if c not in '0123456789abcdefABCDEF':okay=False
                else:lex=('str',key,False,unicode-1)
            elif escape:
                if c=='u':lex=('str',key,False,4)
                elif c in '"\\/bfnrt':lex=('str',key,False,0)
                else:okay=False
            elif c=='\\':lex=('str',key,True,0)
            elif c=='"':
                if key:
                    if not stack:okay=False
                    else:stack[-1]=('colon',0);lex=('normal',)
                else:okay=finish()
            elif ord(c)<32:okay=False
        else:
            p=lex[1];complete=p in ('zero','int','frac','edigits')
            if complete and c in ' \t\r\n,]}':okay=finish() and normal(c)
            elif p=='sign' and c=='I':lex=('word','nfinity')
            elif p=='sign':
                if c=='0':lex=('num','zero')
                elif c in '123456789':lex=('num','int')
                else:okay=False
            elif p=='dot':
                if c in '0123456789':lex=('num','frac')
                else:okay=False
            elif p=='exp':
                if c in '+-':lex=('num','esign')
                elif c in '0123456789':lex=('num','edigits')
                else:okay=False
            elif p=='esign':
                if c in '0123456789':lex=('num','edigits')
                else:okay=False
            elif c in '0123456789' and p!='zero':pass
            elif c=='.' and p in ('int','zero'):lex=('num','dot')
            elif c in 'eE' and p!='edigits':lex=('num','exp')
            else:okay=False
        if not okay:return None
    if done:return (outer,)
    if not stack and lex[0]=='num' and lex[1] in ('zero','int','frac','edigits'):return (None,)
    return None

def catalog(c):
    # c contains raw compiled strings, lower/upper raw nullable cells or exceptions.
    try:
        for s in c.get('params',[]):
            m=re.search(r'(?:^|,)LEN,([^,]*)',s)
            if m:
                try:return int(m[1]),2
                except (ValueError,TypeError):break
            m=re.search(r'LEN[\x00-\x1f]+(\d+)',s)
            if m:return int(m[1]),2
    except Exception:pass
    if c.get('error'):return None,3
    cells=c.get('info',[])
    if not cells:return None,4
    for v in cells[0]:
        if not v:continue
        text=str(v);ms=re.findall(r'(\d+)\s*\)',text)
        if ms:return int(ms[-1]),3
        digits=''.join(x for x in text if x.isdigit())
        if digits:return int(digits),3
    return None,3

class Port:
    def __init__(self,rows=None,raw=None,reg_error=None,cat=None,data=(),faults=None,embedded='unavailable',now=0,ttl=30,dtype='DOUBLE'):
        self.rows=rows or [];self.raw=raw;self.reg_error=reg_error;self.cat=cat or {};self.data=list(data);self.faults=list(faults or []);self.embedded=embedded;self.now=now;self.ttl=ttl;self.dtype=dtype;self.cache={};self.events=[];self.cells=None
    def resolve(self,g,m,kind='node'):
        key=('embedding_registry',g or '',m,kind);self.events.append(('route',key))
        if self.ttl and key in self.cache:
            route,at=self.cache[key]
            if self.now-at<=self.ttl:return route
            del self.cache[key]
        self.events.append(('registry',key))
        if self.reg_error:
            if getattr(self.reg_error,'sqlcode',None)==-30 or 'SQLCODE: <-30>' in str(self.reg_error):return ('kg_NodeEmbeddings',None,None)
            raise self.reg_error
        rows=self.raw if self.raw is not None else [(x['table_name'],x['dimension'],x['dtype'],None,None) for x in self.rows if x['graph_id']==g and x['model_key']==m and (x.get('kind') or 'node')==kind]
        if not rows:return ('kg_NodeEmbeddings',None,None) if not g and m is None else (None,None,None)
        rows=[x for x in rows if len(x)>=5]
        if not rows:return ('kg_NodeEmbeddings',None,None)
        pref=['kg_NodeEmbeddings','kg_NodeEmbeddings_optimized','kg_EdgeEmbeddings'];row=min(rows,key=lambda x:pref.index(x[0]) if x[0] in pref else len(pref))
        d=None if row[1] is None or row[1]=='' else int(row[1]);route=(row[0],d,row[2] or 'DOUBLE');self.cache[key]=(route,self.now);return route
    def check(self,q,route):
        if not isinstance(q,str) or not q.strip().startswith('['):return
        d=route[1]
        if not d:
            d,n=catalog(self.cat);self.events.append(('catalog',n))
        w=width(q)
        if d and w is not None and w!=int(d):raise ValueError('width')
    def selected(self,t,g,l,exclude=None,client=False):
        return [r for r in self.data if r['table']==t and r['graph']==g and (l is None or l in r.get('labels',())) and (not exclude or r['id']!=exclude) and (not client or r['emb'] is not None)]
    def reader(self,rows,embedded=False,exact=False):
        out=[]
        for row in rows:
            if len(row)==0:raise IndexError()
            if embedded and row[0] is None:continue
            if len(row)<2 or exact and len(row)!=2:raise ValueError('arity')
            out.append((row[0],float(row[1])))
        return out
    def score(self,stage,q,k,t,g,label,exclude=None):
        import json
        self.events.append(('score',stage,q,t,g,label,exclude))
        if stage=='embedded' and self.embedded=='unavailable':raise RuntimeError('embedded unavailable')
        if stage!='embedded' and self.faults:
            f=self.faults.pop(0)
            if f:raise f
        rows=self.selected(t,g,label,exclude)
        if self.cells is not None:return self.cells
        if any('cells' in r for r in rows):return [r.get('cells',(r['id'],r.get('score',.75))) for r in rows][:int(k)]
        a=json.loads(q);scored=[]
        for row in rows:
            b=[float(x) for x in str(row['emb']).split(',')]
            if len(a)!=len(b):raise RuntimeError('SQLCODE -257 vectors of different lengths')
            den=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b));s=sum(x*y for x,y in zip(a,b))/den if den else None
            scored.append((row['id'],s))
        return sorted(scored,key=lambda x:x[1],reverse=True)[:int(k)]
    def search(self,stage,q,k=2,label=None,g='g',m='m',override=None):
        import json
        t,d,dt=self.resolve(g,m)
        if t is None:return []
        dtype=(override or dt or self.dtype).upper() if stage=='primary' else self.dtype
        self.check(q,(t,d,dt))
        if stage=='client':
            arr=json.loads(q)
            import numpy as np
            np.array(arr) # named NumPy array-construction provider, distinct from JSON syntax
            self.events.append(('client',t,g,label));out=[]
            for row in self.selected(t,g,label,client=True):
                self.events.append(('kernel',row['id']))
                try:
                    b=[float(x) for x in str(row['emb']).split(',')]
                    if not isinstance(arr,list) or len(arr)!=len(b):continue
                    qa=math.sqrt(sum(x*x for x in arr));rb=math.sqrt(sum(x*x for x in b))
                    if qa>0 and rb>0:out.append((row['id'],sum(x*y for x,y in zip(arr,b))/(qa*rb)))
                except Exception:continue
            return sorted(out,key=lambda x:x[1],reverse=True)[:k]
        if stage=='optimized':
            for provider in ['embedded','dbapi']:
                try:return self.reader(self.score(provider,q,k,t,g,label or None),embedded=provider=='embedded')
                except Exception:pass
            return self.search('client',q,k,label,g,m)
        try:
            seed=None
            if isinstance(q,str) and not q.strip().startswith('['):
                seed=q.strip();self.events.append(('seed',t,g,seed));rows=[r for r in self.data if r['table']==t and r['graph']==g and r['id']==seed]
                if not rows:return []
                q='['+str(rows[0]['emb'])+']'
            return self.reader(self.score('primary',q,k,t,g,label or None,seed),exact=True)
        except Exception as ex:
            if '-257' in str(ex) or 'vectors of different lengths' in str(ex):
                self.events.append(('diagnostic',t,g));raise ValueError('width')
            return self.search('optimized',q,k,label,g,m)


def phase_request(requests,stage):
    """scenario's fixed engine/key fields; raw replies/clock samples remain phase-specific."""
    i={'primary':0,'optimized':1,'client':2}[stage];root=requests[0];z=dict(requests[i])
    for k in ['registry','graph','model','ttl']:z[k]=root[k]
    z['kind']='node';return z
