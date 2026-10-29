import json,subprocess,datetime as D,re,os
coins=json.load(open('coins.json'));out={}
for sym,h,start in coins:
    if sym in('PREDICT','MON'): continue
    s=D.date.fromisoformat(start); e=s+D.timedelta(days=46)
    q=f'${sym} sale FDV since:{s-D.timedelta(days=20)} until:{e}'
    raw=subprocess.run(['./tw.sh','tweet/advanced_search',f'query={q}','queryType=Top'],capture_output=True,text=True).stdout
    try: tw=json.loads(raw,strict=False).get('tweets',[])
    except: print(sym,'ERR');continue
    tw.sort(key=lambda t:D.datetime.strptime(t['createdAt'],'%a %b %d %H:%M:%S %z %Y'))
    out[sym]=[(t['createdAt'],t['author']['userName'],t['text']) for t in tw]
    hits=[]
    for at,u,tx in out[sym]:
        for m in re.finditer(r'.{0,70}FDV.{0,50}',tx.replace('\n',' '),re.I): hits.append(f"{D.datetime.strptime(at,'%a %b %d %H:%M:%S %z %Y'):%m-%d %H:%M} @{u}: {m.group(0)}")
    print(f'== {sym} (盘前 {start}) n={len(tw)}');[print('  ',x[:170]) for x in hits[:4]]
json.dump(out,open('r2/fdv_tweets.json','w'),ensure_ascii=False)
