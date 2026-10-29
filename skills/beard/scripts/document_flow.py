"""Lossless paragraph planning and checked assembly; no implicit storage or model calls."""
import argparse,hashlib,json,re,sys
from verify_text import inspect_text,IMMUTABLE
def digest(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()
def plan_document(original,budget=6000):
 if not isinstance(original,str) or not isinstance(budget,int) or budget<1:raise ValueError('text and positive integer budget required')
 blocks=[];buf=[];fence=None;had_fence=False;offset=0;position=0
 protected_spans=[m.span() for m in IMMUTABLE.finditer(original)]
 def flush():
  nonlocal buf,had_fence,offset
  if not buf:return
  text=''.join(buf);kind='protected' if had_fence or not text.strip() or any(line.lstrip().startswith('|') for line in text.splitlines()) else 'body'
  blocks.append(dict(id=f'B{len(blocks)+1:04}',start=offset,end=offset+len(text),text=text,kind=kind));offset+=len(text);buf=[];had_fence=False
 for line in original.splitlines(keepends=True):
  m=re.match(r'^\s*(`{3,}|~{3,})',line)
  if m:
   token=m.group(1);had_fence=True
   if fence is None:fence=token
   elif token[0]==fence[0] and len(token)>=len(fence):fence=None
  buf.append(line);position+=len(line)
  if not line.strip() and fence is None and not any(a<position<b for a,b in protected_spans):flush()
 flush();chunks=[];ids=[];size=0
 for b in blocks:
  if ids and size+len(b['text'])>budget:chunks.append(dict(id=f'C{len(chunks)+1:04}',block_ids=ids));ids=[];size=0
  ids.append(b['id']);size+=len(b['text'])
 if ids:chunks.append(dict(id=f'C{len(chunks)+1:04}',block_ids=ids))
 return dict(source_sha256=digest(original),source_length=len(original),budget=budget,blocks=blocks,chunks=chunks,oversize_blocks=[b['id'] for b in blocks if len(b['text'])>budget],unclosed_fence=fence is not None)
def validate_plan(plan,original):
 if not isinstance(original,str) or digest(original)!=plan['source_sha256'] or len(original)!=plan['source_length']:raise ValueError('Original does not match plan')
 offset=0;ids=[]
 for b in plan['blocks']:
  if b['id'] in ids or b['kind'] not in {'body','protected'}:raise ValueError('Invalid or duplicate block')
  if b['start']!=offset or b['end']!=offset+len(b['text']) or original[b['start']:b['end']]!=b['text']:raise ValueError('Block span or text mismatch')
  ids.append(b['id']);offset=b['end']
 if offset!=len(original) or [i for c in plan['chunks'] for i in c['block_ids']]!=ids:raise ValueError('Incomplete or repeated plan coverage')
def assemble_document(plan,rewrites,original):
 validate_plan(plan,original)
 if not isinstance(rewrites,dict):raise ValueError('rewrites must be an object')
 expected={b['id'] for b in plan['blocks'] if b['kind']=='body'}
 if set(rewrites)!=expected:raise ValueError('Missing or unknown rewrite IDs')
 result=[]
 for b in plan['blocks']:
  if b['kind']=='protected':result.append(b['text']);continue
  value=rewrites[b['id']]
  if not isinstance(value,str) or not value.strip():raise ValueError('Empty body output')
  value=re.match(r'\s*',b['text']).group()+value.strip()+re.search(r'\s*$',b['text']).group()
  if inspect_text(b['text'],value)['status']=='protected_change':raise ValueError('Protected text changed in '+b['id'])
  result.append(value)
 text=''.join(result)
 return dict(text=text,block_count=len(plan['blocks']),inspection=inspect_text(original,text),semantic_equivalence='unknown')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['plan','assemble']);p.add_argument('--budget',type=int,default=6000);a=p.parse_args()
 try:
  data=json.load(sys.stdin);out=plan_document(data['original'],a.budget) if a.mode=='plan' else assemble_document(data['plan'],data['rewrites'],data['original'])
 except (ValueError,KeyError,TypeError) as e:print(json.dumps(dict(error=type(e).__name__,message=str(e)),ensure_ascii=False));return 2
 print(json.dumps(out,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
