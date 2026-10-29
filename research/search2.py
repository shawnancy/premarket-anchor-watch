import json,subprocess,datetime as D,os
coins=json.load(open('coins.json'))
res=json.load(open('tweets_all.json')) if os.path.exists('tweets_all.json') else {}
for sym,h,start in coins:
    if sym in res: continue
    s=D.date.fromisoformat(start)-D.timedelta(days=1); e=s+D.timedelta(days=46)
    q=f"from:{h} -filter:replies since:{s} until:{e}"
    tweets=[];cur='';seen=set()
    for page in range(40):
        args=['./tw.sh','tweet/advanced_search',f'query={q}','queryType=Latest']
        if cur: args.append(f'cursor={cur}')
        out=subprocess.run(args,capture_output=True,text=True).stdout
        try: d=json.loads(out,strict=False)
        except Exception: print(sym,'bad json',out[:200]);break
        tw=d.get('tweets',[])
        for t in tw:
            if t['id'] in seen or t.get('retweeted_tweet'): continue
            seen.add(t['id'])
            a=t.get('article') or {}
            tweets.append({'id':t['id'],'at':t['createdAt'],'views':t.get('viewCount'),'text':t['text'][:600],
              'atitle':a.get('title'),'aprev':(a.get('preview_text') or '')[:600],
              'quote':((t.get('quoted_tweet') or {}).get('text') or '')[:300]})
        if not d.get('has_next_page') or not tw: break
        cur=d.get('next_cursor')
    res[sym]=tweets
    json.dump(res,open('tweets_all.json','w'),ensure_ascii=False)
    print(sym,h,len(tweets),'pages',page+1,flush=True)
