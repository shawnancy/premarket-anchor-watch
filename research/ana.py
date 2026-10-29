import json,datetime as D,re,os,bisect,sys
tw=json.load(open('tweets_all.json'))
KW=re.compile(r'tokenomics|token supply|allocation|airdrop|eligib|checker|distribution|unlock|vesting|genesis|claim|TGE|community sale|ICO|public sale',re.I)
def ts(s): return int(D.datetime.strptime(s,'%a %b %d %H:%M:%S %z %Y').timestamp()*1000)
out=[]
for sym,lst in tw.items():
    fn=f'kl/{sym}.json'
    if not os.path.exists(fn): continue
    k=json.load(open(fn)); T=[r[0] for r in k]
    for t in lst:
        blob=' '.join([t['text'],t['atitle'] or '',t['aprev'],t['quote']])
        pass
        ms=ts(t['at']); i=bisect.bisect_right(T,ms)-1
        if i<0 or i+240>=len(k) or T[i]+60000<ms: continue
        p0=k[i][1]  # open of minute containing tweet
        pre=k[i-1][4] if i>0 else p0
        w=k[i:i+61]
        hi=max(r[2] for r in w); lo=min(r[3] for r in w)
        pk=max(range(len(w)),key=lambda j:w[j][2])
        def c(m): return round((k[i+m][4]/p0-1)*100,1)
        e1=k[i+1][1]; e5=k[i+5][1]
        r=lambda e,m: round((k[i+m][4]/e-1)*100,1)
        pct=re.findall(r'([A-Za-z &]{0,40}?)\(?\s*(\d{1,2}(?:\.\d+)?)\s*%',blob)
        out.append(dict(sym=sym,at=D.datetime.fromtimestamp(ms/1000,D.timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),views=t['views'],
          up60=round((hi/p0-1)*100,1),dn60=round((lo/p0-1)*100,1),peak_min=pk,c5=c(5),c15=c(15),c60=c(60),c240=c(240),
          late1_15=r(e1,15),late1_60=r(e1,60),late1_240=r(e1,240),late5_60=r(e5,60),
          vol60=round(sum(x[5] for x in w)),volpre60=round(sum(x[5] for x in k[max(0,i-60):i])),
          title=(t['atitle'] or t['text'])[:120].replace('\n',' '),pcts=[(a.strip()[-25:],b) for a,b in pct][:8],id=t['id']))
json.dump(out,open('cands.json','w'),ensure_ascii=False,indent=0)
out.sort(key=lambda x:-abs(x['up60'])-abs(x['dn60']))
for o in out: print(o['sym'],o['at'],'v',o['views'],'up',o['up60'],'dn',o['dn60'],'pk',o['peak_min'],'c15',o['c15'],'c60',o['c60'],'c240',o['c240'],'vol',o['vol60'],'/',o['volpre60'],'|',o['title'][:90])
