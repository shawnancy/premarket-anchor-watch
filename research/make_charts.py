import json,urllib.request,datetime as D,os
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, matplotlib.dates as md
from matplotlib import font_manager as fm
plt.rcParams.update({'font.family':'PingFang SC','axes.unicode_minus':False})
BLUE,ORANGE,INK,INK2,MUTED,SURF,GRID='#2a78d6','#eb6834','#0b0b0b','#52514e','#8a8984','#fcfcfb','#e7e6e2'
TZ=D.timezone(D.timedelta(hours=8)); OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','charts')
def bn(sym,start,end,iv='5m'):
    k=[];t=start
    while t<end:
        x=json.load(urllib.request.urlopen(f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}USDT&interval={iv}&startTime={t}&endTime={end}&limit=1500"))
        if not x: break
        k+=x;t=x[-1][0]+1
    return [(D.datetime.fromtimestamp(r[0]/1000,TZ),float(r[4])) for r in k]
def ms(s): return int(D.datetime.strptime(s,'%Y-%m-%d %H:%M').replace(tzinfo=TZ).timestamp()*1000)
def base(title,sub):
    fig,ax=plt.subplots(figsize=(16,9),dpi=100); fig.patch.set_facecolor(SURF); ax.set_facecolor(SURF)
    fig.text(0.06,0.93,title,fontsize=26,weight='bold',color=INK); fig.text(0.06,0.885,sub,fontsize=15,color=INK2)
    for s in ['top','right']: ax.spines[s].set_visible(False)
    for s in ['left','bottom']: ax.spines[s].set_color(GRID)
    ax.grid(axis='y',color=GRID,lw=1); ax.tick_params(colors=INK2,labelsize=13)
    fig.text(0.06,0.03,'数据：币安 USDT 永续盘前合约 5 分钟收盘价 × 总量；时间为北京时间。github.com/shawnancy/premarket-anchor-watch',fontsize=11,color=MUTED)
    fig.subplots_adjust(left=0.07,right=0.95,top=0.83,bottom=0.12); return fig,ax
def event(ax,t,y,txt,pos):
    dxh,ty,ha=pos   # 标注框: 相对事件点横移几小时, 纵向放在哪个绝对高度, 左/右对齐
    ax.axvline(t,color=MUTED,lw=1,ls=(0,(2,3)),zorder=1)
    ax.annotate(txt,xy=(t,y),xytext=(t+D.timedelta(hours=dxh),ty),fontsize=14,color=INK,ha=ha,va='center',
        arrowprops=dict(arrowstyle='-',color=MUTED,lw=1),bbox=dict(boxstyle='round,pad=0.35',fc=SURF,ec=GRID))
def timeline(sym,supply,a,b,anchor,anchor_lbl,events,title,sub,fn,unit=1e8):
    d=bn(sym,ms(a),ms(b)); xs=[x for x,_ in d]; ys=[p*supply/unit for _,p in d]
    fig,ax=base(title,sub)
    ax.plot(xs,ys,color=BLUE,lw=2,zorder=3,solid_capstyle='round')
    ax.axhline(anchor/unit,color=ORANGE,lw=2,ls=(0,(6,4)),zorder=2)
    ax.text(xs[-1],anchor/unit,f'  {anchor_lbl}',color=INK,fontsize=14,va='bottom',ha='right')
    ax.annotate(f'盘前 FDV {ys[-1]:.1f} 亿',xy=(xs[-1],ys[-1]),xytext=(0,28),textcoords='offset points',color=INK,fontsize=14,ha='right',va='bottom')
    for t,txt,pos in events:
        tt=D.datetime.strptime(t,'%Y-%m-%d %H:%M').replace(tzinfo=TZ)
        y=min(ys,key=lambda v: abs(xs[ys.index(v)]-tt).total_seconds()) if False else ys[min(range(len(xs)),key=lambda i:abs((xs[i]-tt).total_seconds()))]
        event(ax,tt,y,txt,pos)
    ax.set_ylim(0,max(ys)*1.25); ax.set_ylabel('FDV（亿美元）',color=INK2,fontsize=13)
    ax.xaxis.set_major_formatter(md.DateFormatter('%m-%d %H:%M',tz=TZ))
    fig.savefig(os.path.join(OUT,fn),facecolor=SURF); plt.close(fig); return d
p=timeline('PREDICT',1e9,'2026-10-28 12:00','2026-10-29 18:00',3e8,'币安打新估值锚 3 亿',
  [('2026-10-28 14:22','14:22 公布代币经济学\n空投 7%，没给估值',(1.2,8,'left')),('2026-10-28 15:30','15:30 币安钱包公布打新价\n估值 3 亿，当时盘前 16.7 亿',(3,21,'left'))],
  'PREDICT：公布空投时涨 40%，估值锚一出来就往下走','盘前 FDV 一直远高于打新估值（锚 ÷ 盘前 = 18%），打新价公布后 24 小时 −15.7%','1_predict_fdv_timeline.png')
m=timeline('MON',100e9,'2025-11-10 15:00','2025-11-11 22:00',25e8,'Coinbase 公募估值锚 25 亿',
  [('2025-11-10 18:30','18:30 链上被扒出空投 3.33%\n价格基本不动',(0.4,36,'left')),('2025-11-10 22:06','22:06 官方公布：空投 3.3%\n+ 公募价 0.025（估值 25 亿）',(2,73,'left'))],
  'MON：空投最低（3.3%），公募价一出 1 小时内最多跌 30%','公布时盘前 FDV 64.1 亿，是公募估值的 2.6 倍（锚 ÷ 盘前 = 39%），24 小时 −21.6%；跌 30% 指 1 分钟最低价','2_mon_fdv_timeline.png')
# 汇总
rows=[('PREDICT 币安打新',18,-15.7),('MON Coinbase 公募',39,-21.6),('KAT 币安打新',53,-4.5),('ZAMA 打新·买1送1',56,-9.3),('FOGO 币安打新',64,-3.1),('ZAMA 公开拍卖结果',90,-17.2)]
fig,ax=base('盘前价高于估值锚的 6 次：24 小时全部下跌','横轴 = 公布后 24 小时涨跌；括号里是「估值锚 ÷ 公布那一刻的盘前 FDV」，越小 = 盘前溢价越高')
ys=list(range(len(rows)))[::-1]
ax.barh(ys,[r[2] for r in rows],height=0.55,color=BLUE,zorder=3)
for y,(n,ratio,r) in zip(ys,rows):
    ax.text(r-0.4,y,f'{r:+.1f}%',va='center',ha='right',fontsize=14,color=INK)
ax.set_yticks(ys); ax.set_yticklabels([f'{n}（{ratio}%）' for n,ratio,_ in rows],fontsize=14,color=INK)
ax.set_xlim(-26,2); ax.axvline(0,color=INK2,lw=1); ax.grid(axis='y',visible=False); ax.grid(axis='x',color=GRID)
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v,_: f'{v:.0f}%'))
fig.subplots_adjust(left=0.27); fig.savefig(os.path.join(OUT,'3_anchor_ratio_vs_24h.png'),facecolor=SURF); plt.close(fig)
print('PREDICT pts',len(p),'MON pts',len(m))
