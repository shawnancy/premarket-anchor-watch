import json,datetime as D,bisect
EV=[
# sym, utc time, kind, airdrop%, note, confidence
('PREDICT','2026-10-28 06:22:25','项目公布','7%（即领35%）','官推长文','高'),
('LIT','2025-12-30 04:45:05','项目公布','25%（当场发币）','官推线程','高'),
('MON','2025-11-10 10:30:32','链上被扒','3.33%','第三方扒链上数据','中'),
('MON','2025-11-10 14:06:18','项目公布','3.3%（同时宣布 Coinbase 公募 25 亿估值）','官推','高'),
('KITE','2025-10-30 17:52:11','项目公布','生态+社区 48%','基金会号','高'),
('STABLE','2025-12-02 18:59:29','项目公布','约10%（第三方转述）','官推','中'),
('OPN','2026-03-02 12:45:51','项目公布+币安Launchpool','23.5%（TGE只解锁3.5%）','币安公告','高'),
('SXT','2025-05-05 00:01:13','项目公布','7.5%','官推线程','中'),
('NEWT','2025-06-23 12:48:29','项目公布','（未抓到比例）','官推','中'),
('FOGO','2026-01-10 21:30:00','项目公布','TGE 解锁 38.98%','第三方首转,官方时间未钉死','低'),
('MET','2025-10-13 12:06:33','代币经济学调整','Mercurial 20%拆15+5','官推','高'),
('INIT','2025-04-17 08:59:59','币安Launchpool','—','币安公告','高'),
('SXT','2025-05-05 14:14:13','币安Launchpool','—','币安公告','高'),
('NEWT','2025-06-23 14:08:19','币安HODLer空投','—','币安公告','高'),
('SOMI','2025-09-01 08:59:32','币安HODLer空投','—','币安公告','高'),
('0G','2025-09-21 08:58:17','币安HODLer空投','—','币安公告','高'),
('YB','2025-10-14 09:46:27','币安HODLer空投','—','币安公告','高'),
('KITE','2025-10-31 08:09:28','币安Launchpool','—','币安公告','高'),
('BREV','2026-01-05 10:04:14','币安HODLer空投','—','币安公告','高'),
]
rows=[]
for sym,t,kind,ad,note,conf in EV:
    k=json.load(open(f'kl/{sym}.json')); T=[r[0] for r in k]
    ms=int(D.datetime.strptime(t,'%Y-%m-%d %H:%M:%S').replace(tzinfo=D.timezone.utc).timestamp()*1000)
    i=bisect.bisect_right(T,ms)-1
    if i<0 or T[i]+60000<ms or i+241>len(k): rows.append((sym,t,kind,'无K线'));continue
    p0=k[i][1]; e=k[i+1][1]   # e: next-minute open = ~30-60s late
    w=k[i+1:i+61]
    hi=max(r[2] for r in w); pk=max(range(len(w)),key=lambda j:w[j][2])+1
    lo=min(r[3] for r in w)
    f=lambda m: round((k[i+m][4]/e-1)*100,1)
    pre=round((e/p0-1)*100,1)  # what you miss in first minute
    bj=(D.datetime.fromtimestamp(ms/1000,D.timezone.utc)+D.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    rows.append(dict(sym=sym,bj=bj,kind=kind,ad=ad,conf=conf,miss1=pre,peak=round((hi/e-1)*100,1),pk=pk,dd=round((lo/e-1)*100,1),r5=f(5),r15=f(15),r60=f(60),r240=f(240)))
json.dump(rows,open('final.json','w'),ensure_ascii=False)
for r in rows: print(r)
