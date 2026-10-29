"""Read-only editorial checks. Signals are not a semantic equivalence verdict."""
import argparse,base64,collections,difflib,json,re,sys
from pathlib import Path

IMMUTABLE=re.compile(r'(?P<fence>(?P<ticks>`{3,}|~{3,})[^\n]*\n[\s\S]*?\n[ \t]*(?P=ticks)[ \t]*(?=\r?\n|$))|(?P<code>`[^`\n]+`)|(?P<quote>“[^”]+”|「[^」]+」|『[^』]+』|"[^"\n]+")|(?P<address>https?://[^\s<>"“”`]+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})',re.M)
NUMBER=re.compile(r'(?<![0-9A-Za-z_])[-+]?\d[\d,]*(?:\.\d+)?(?:\s*(?:퍼센트|억원|만원|원|명|건|개|장|일|년|월|시|분|초|배|회|km|kg|mg|mL|GB|MB|%))?')
CUES={
 'possibility':re.compile(r'수\s*있|가능성|가능(?:하|합|했)|지도\s*모르'),
 'impossibility':re.compile(r'수\s*없|불가능'),
 'obligation':re.compile(r'해야|하여야|해\s*주셔야|필수|의무'),
 'negation':re.compile(r'않|아니(?:다|라|었|며)|아닙|없|(?:^|\s)못\s'),
 'condition':re.compile(r'경우|한하여|한해|에게만|해야만')}
def immutable(text):
 return collections.Counter((m.lastgroup,m.group().rstrip('.,;') if m.lastgroup=='address' else m.group()) for m in IMMUTABLE.finditer(text))
def numbers(text):
 # Count facts in the body, excluding protected literal spans which are checked separately.
 body=IMMUTABLE.sub(' ',text)
 return collections.Counter(re.sub(r'\s|,','',m.group()) for m in NUMBER.finditer(body))
def sentences(text):return [s.strip() for s in re.split(r'(?<=[.!?。])\s+|\n+',text) if s.strip()]
def inspect_text(original,revised,protected_literals=None):
 if not isinstance(original,str) or not isinstance(revised,str):raise ValueError('original/revised must be strings')
 if protected_literals is None:protected_literals=[]
 if not isinstance(protected_literals,list) or any(not isinstance(v,str) or not v or v not in original for v in protected_literals):raise ValueError('protected_literals must be nonempty original substrings')
 findings=[]
 for value in dict.fromkeys(protected_literals):
  if revised.count(value)<original.count(value):findings.append(dict(kind='explicit_literal',severity='protected_change',value=value))
 before=immutable(original);after=immutable(revised)
 for (kind,value),count in (before-after).items():findings.append(dict(kind=kind,severity='protected_change',value=value,missing_count=count))
 for (kind,value),count in (after-before).items():
  if kind in {'address','code','fence'}:findings.append(dict(kind='new_'+kind,severity='needs_review',value=value,added_count=count))
 bn=numbers(original);an=numbers(revised)
 if bn!=an:findings.append(dict(kind='number_or_unit',severity='needs_review',removed=dict(bn-an),added=dict(an-bn)))
 bs=sentences(original);ass=sentences(revised)
 for index,s in enumerate(bs):
  cues=[k for k,rx in CUES.items() if rx.search(s)]
  if not cues:continue
  # An alignment candidate is an aid to review, never an assertion that the clauses are equivalent.
  ranked=[(difflib.SequenceMatcher(None,s,a,autojunk=False).ratio(),j,a) for j,a in enumerate(ass)]
  similarity,j,candidate=max(ranked,default=(0.0,-1,''))
  lost=[k for k in cues if not CUES[k].search(candidate)]
  if lost:findings.append(dict(kind='semantic_cue',severity='needs_review',source_sentence=index+1,candidate_sentence=j+1 if j>=0 else None,alignment_similarity=round(similarity,3),lost_cues=lost))
 status='protected_change' if any(f['severity']=='protected_change' for f in findings) else 'needs_review' if findings else 'no_mechanical_issue'
 return dict(status=status,findings=findings,semantic_equivalence='unknown',note='Count/substring signals cannot establish factual, logical or stylistic equivalence.')
def read_payload(args):
 if args.payload_base64:
  return json.loads(base64.b64decode(args.payload_base64,validate=True).decode('utf-8-sig'))
 if args.before or args.after:
  if not args.before or not args.after:raise ValueError('--before and --after must be provided together')
  return dict(original=Path(args.before).read_text(encoding='utf-8-sig'),revised=Path(args.after).read_text(encoding='utf-8-sig'))
 return json.load(sys.stdin)
def main():
 p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group();g.add_argument('--payload-base64');g.add_argument('--before');p.add_argument('--after');a=p.parse_args()
 try:
  data=read_payload(a);r=inspect_text(data['original'],data['revised'],data.get('protected_literals'))
 except (ValueError,OSError,KeyError,TypeError) as e:
  print(json.dumps(dict(error=type(e).__name__,message=str(e)),ensure_ascii=False));return 2
 print(json.dumps(r,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
