"""Executable mirror of the bounded raw lexical/JSON model, never a native provider."""
import re
from fractions import Fraction
CANON=re.compile(r'(?:0|[1-9][0-9]*|-[1-9][0-9]*)\Z')
def integer(s):return int(s) if CANON.fullmatch(s) else None
def dyadic(s):
 for tail,den,part in [('.25',4,1),('.75',4,3),('.5',2,1),('.0',1,0)]:
  if s.endswith(tail):
   n=integer(s[:-len(tail)])
   return (n*den+(-part if n<0 else part),den,s) if n is not None and -1000<=n<=1000 else None
 return None
def literal(s):
 n=integer(s)
 if n is not None:return ('integer',n,s)
 d=dyadic(s)
 if d is not None:return ('decimal',Fraction(d[0],d[1]),d[2])
 if s=='007':return ('decimal',Fraction(7),'7.0')
 if s.lower() in ('true','false'):return ('boolean',s.lower()=='true',s.lower())
 return ('plain',s,s)
def truth(l):return bool(l[1])
def qualifier(s):
 l=literal(s);return l if truth(l) else ('plain',s,s)
def admitted(s):return integer(s) is not None or dyadic(s) is not None or s=='007' or s=='' or (s[0].isascii() and s[0].isalpha() and all(c.isascii() and (c.isalnum() or c in '_-/:.') for c in s) and s.lower() not in ('nan','inf','infinity'))
def bare(s):
 if s in ('true','false','null'):return {'true':'True','false':'False','null':'None'}[s]
 return s if integer(s) is not None or dyadic(s) is not None else None
def decode(raw):
 if raw is None:return []
 mode=0;key='';value='';es=[]
 def put(k,v):
  for i,(old,_) in enumerate(es):
   if old==k:es[i]=(k,v);return
  es.append((k,v))
 for c in raw:
  if mode==0:mode=mode if c==' ' else (1 if c=='{' else 10)
  elif mode in (1,2):
   if c==' ':pass
   elif c=='"':mode=3;key='';value=''
   elif c=='}' and mode==1:mode=9
   else:mode=10
  elif mode==3:
   if c=='"':mode=4
   elif ' '<=c<='~' and c!='\\':key+=c
   else:mode=10
  elif mode==4:mode=mode if c==' ' else (5 if c==':' else 10)
  elif mode==5:
   if c==' ':pass
   elif c=='"':mode=6;value=''
   elif c in ',}':mode=10
   else:mode=7;value=c
  elif mode==6:
   if c=='"':mode=8;put(key,value)
   elif ' '<=c<='~' and c!='\\':value+=c
   else:mode=10
  elif mode==7:
   if c in ' ,}':
    b=bare(value)
    if b is None:mode=10
    else:put(key,b);mode=8 if c==' ' else (2 if c==',' else 9)
   else:value+=c
  elif mode==8:mode=mode if c==' ' else (2 if c==',' else (9 if c=='}' else 10))
  elif mode==9 and c==' ':pass
  else:mode=10
 return es if mode==9 else []
