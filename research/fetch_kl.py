# usage: python3 fetch_kl.py events.json out.json   (runs on VPS)
# events: [{"sym":"MON","utc":"2025-11-10 14:06:18"}, ...]
import json,sys,urllib.request,datetime as D,time
def g(u):
    try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=20))
    except Exception as e: return None
def binance(s,a,b):
    out=[];t=a
    while t<b:
        k=g(f"https://fapi.binance.com/fapi/v1/klines?symbol={s}USDT&interval=1m&startTime={t}&endTime={b}&limit=1500")
        if not k: break
        out+=[[r[0],float(r[1]),float(r[2]),float(r[3]),float(r[4]),float(r[7])] for r in k]; t=k[-1][0]+60000
    return out
def okx(s,a,b):
    out=[];after=b+60000
    for _ in range(10):
        d=g(f"https://www.okx.com/api/v5/market/history-candles?instId={s}-USDT-SWAP&bar=1m&after={after}&before={a-60000}&limit=100")
        rows=(d or {}).get("data") or []
        if not rows: break
        out+=[[int(r[0]),float(r[1]),float(r[2]),float(r[3]),float(r[4]),float(r[7])] for r in rows]; after=int(rows[-1][0])
        time.sleep(0.15)
    return sorted({r[0]:r for r in out}.values())
def bitget(s,a,b):
    out=[];t=a
    while t<b:
        e=min(t+200*60000,b)
        d=g(f"https://api.bitget.com/api/v2/mix/market/history-candles?symbol={s}USDT&productType=usdt-futures&granularity=1m&startTime={t}&endTime={e}&limit=200")
        rows=(d or {}).get("data") or []
        out+=[[int(r[0]),float(r[1]),float(r[2]),float(r[3]),float(r[4]),float(r[6])] for r in rows]; t=e
        time.sleep(0.15)
    return sorted({r[0]:r for r in out}.values())
def spot_before(s,ms):
    k=g(f"https://api.binance.com/api/v3/klines?symbol={s}USDT&interval=1m&endTime={ms}&limit=1")
    if k: return "binance_spot"
    d=g(f"https://www.okx.com/api/v5/market/history-candles?instId={s}-USDT&bar=1m&after={ms}&limit=1")
    if (d or {}).get("data"): return "okx_spot"
    return ""
ev=json.load(open(sys.argv[1])); res={}
for e in ev:
    ms=int(D.datetime.strptime(e["utc"],"%Y-%m-%d %H:%M:%S").replace(tzinfo=D.timezone.utc).timestamp()*1000)
    a=ms-3600000; b=ms+5*3600000
    for name,f in (("binance",binance),("okx",okx),("bitget",bitget)):
        k=[r for r in f(e["sym"],a,b) if a<=r[0]<=b]
        if len(k)>=300 and k[0][0]<=ms-60000:
            res[f'{e["sym"]}|{e["utc"]}']={"venue":name,"k":k,"spot_before":spot_before(e["sym"],ms)}; break
    print(e["sym"],e["utc"],res.get(f'{e["sym"]}|{e["utc"]}',{}).get("venue","无数据"),flush=True)
json.dump(res,open(sys.argv[2],"w"))
