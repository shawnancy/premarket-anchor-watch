import json,subprocess,datetime as D,os,sys
import os
os.chdir(os.path.dirname(os.path.abspath(__file__))+'/..')
out='r2/xs.json'
res=json.load(open(out)) if os.path.exists(out) else {}
# 10-28 坑: 查询里写 "%"(带引号) 会让 X 搜索整轮返回 0 条(假绿), 只能写裸 %
Q=['tokenomics airdrop % min_faves:150','tokenomics airdrop "total supply" min_faves:100','"airdrop allocation" % supply min_faves:100']
m=D.date(2024,1,1)
while m<D.date(2026,11,1):
    n=(m.replace(day=28)+D.timedelta(days=4)).replace(day=1)
    for qi,q in enumerate(Q):
        key=f'{m}_{qi}'
        if res.get(key): continue  # 只有非空才算完成(空=可能是连接失败)
        tweets=[];cur=''
        for p in range(4):
            a=['../tw.sh','tweet/advanced_search',f'query={q} since:{m} until:{n}','queryType=Top']
            if cur:a.append(f'cursor={cur}')
            raw=subprocess.run(a,capture_output=True,text=True).stdout
            try: d=json.loads(raw,strict=False)
            except Exception:
                print(key,'连接/解析失败,不记',raw[:80],flush=True); tweets=None; break
            for t in d.get('tweets',[]):
                ar=t.get('article') or {}
                tweets.append(dict(id=t['id'],at=t['createdAt'],u=t['author']['userName'],v=t.get('viewCount'),f=t.get('likeCount'),
                    text=(t['text']+' '+(ar.get('title') or '')+' '+(ar.get('preview_text') or ''))[:900]))
            if not d.get('has_next_page'):break
            cur=d.get('next_cursor')
        if tweets is None: continue
        res[key]=tweets
        json.dump(res,open(out,'w'),ensure_ascii=False)
        print(key,len(tweets),'⚠️零条' if not tweets else '',flush=True)
    m=n
