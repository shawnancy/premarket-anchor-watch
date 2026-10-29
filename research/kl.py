import json,urllib.request,datetime as D,time,os
coins=json.load(open('coins.json'))
now=int(time.time()*1000)
for sym,h,start in coins:
    fn=f'kl/{sym}.json'
    if os.path.exists(fn): continue
    s=int(D.datetime.fromisoformat(start).replace(tzinfo=D.timezone.utc).timestamp()*1000)
    e=min(s+45*86400000,now)
    rows=[];t=s
    while t<e:
        u=f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}USDT&interval=1m&startTime={t}&limit=1500"
        try: k=json.load(urllib.request.urlopen(u,timeout=20))
        except Exception as ex: print(sym,'ERR',ex); break
        if not k: t+=1500*60000; continue
        rows+= [[r[0],float(r[1]),float(r[2]),float(r[3]),float(r[4]),float(r[7])] for r in k]
        t=k[-1][0]+60000
        time.sleep(0.2)
    rows=[r for r in rows if r[0]<e]
    json.dump(rows,open(fn,'w'))
    print(sym,len(rows), rows and D.datetime.fromtimestamp(rows[0][0]/1000,D.timezone.utc), flush=True)
