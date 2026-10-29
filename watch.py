#!/usr/bin/env python3
"""
盘前合约 × 估值锚 监控 (premarket-anchor-watch)

回测结论(见 report/): 盘前期间公布估值锚(打新/公募/拍卖价)且盘前价高于锚 → 24h 6/6 下跌;
空投比例本身和涨跌对不上。本程序只发提醒, 不下单。

每轮:
 1. 取币安 USDT-M 盘前合约列表(underlyingSubType 含 Pre-Market) + config.json 里手动追加的币
 2. 对每个币用 twitterapi.io 搜上一轮以来的新推(Latest, 1页)
 3. 正则抽 空投% / 打新价 / 估值(FDV) / 总量, 算 锚÷盘前
 4. 命中规则 → 推送(notify.send_imessage, VPS 上写 outbox → Mac relay 转 iMessage)
 5. 已推送事件 1h/4h/24h 后回填收益到 events.jsonl, 样本自动积累

用法: python3 watch.py            正常跑一轮
      python3 watch.py --selftest 用历史推文做阳性对照(不联网不推送)
      python3 watch.py --dry       跑一轮但不推送
"""
import json, os, re, sys, time, urllib.request, urllib.parse, datetime as D, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
_cfg_local = os.path.join(HERE, "config.local.json")     # 本机真实配置(不进仓库); 没有就用示例配置
CFG = json.load(open(_cfg_local if os.path.exists(_cfg_local) else os.path.join(HERE, "config.json")))
STATE_F = os.path.join(HERE, "state.json")
EVENTS_F = os.path.join(HERE, "events.jsonl")
LOG_F = os.path.join(HERE, "watch.log")
HEART_F = os.path.join(HERE, "heartbeat.txt")
UA = {"User-Agent": "Mozilla/5.0"}

def log(*a):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOG_F, "a") as f: f.write(line + "\n")

def http_json(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode(), strict=False)

def load_state():
    try: return json.load(open(STATE_F))
    except Exception: return {"seen": [], "anchor": {}, "since": {}, "x_fail": 0, "x_calls": {}}

def save_state(s):
    s["seen"] = s["seen"][-20000:]   # 按 tweet id 去重; 2 万条约等于一年量, 不会造成重发
    tmp = STATE_F + ".tmp"; json.dump(s, open(tmp, "w"), ensure_ascii=False); os.replace(tmp, STATE_F)

# ---------- 行情 ----------
def premarket_symbols():
    ei = http_json("https://fapi.binance.com/fapi/v1/exchangeInfo")
    syms = [s["baseAsset"] for s in ei["symbols"]
            if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT"
            and any("pre-market" in t.lower() for t in s.get("underlyingSubType", []))]
    return sorted(set(syms) | set(CFG.get("extra_symbols", [])))

def mark_price(sym):
    d = http_json(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={sym}USDT")
    return float(d["markPrice"])

def close_at(sym, ms):
    k = http_json(f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}USDT&interval=1m&startTime={ms}&limit=1")
    return float(k[0][4]) if k else None

# ---------- X ----------
def x_key():
    p = os.environ.get("TWITTERAPI_KEY_FILE", CFG["twitterapi_key_file"])
    return open(os.path.expanduser(p)).read().strip()

def x_search(query):
    # 坑: 查询里别写带引号的 "%", 会静默返回 0 条
    url = "https://api.twitterapi.io/twitter/tweet/advanced_search?" + urllib.parse.urlencode({"query": query, "queryType": "Latest"})
    d = http_json(url, headers={"X-API-Key": x_key()}, timeout=40)
    if "tweets" not in d: raise RuntimeError(f"x api 返回异常: {str(d)[:200]}")
    return d["tweets"]

def tweet_text(t):
    a = t.get("article") or {}
    q = (t.get("quoted_tweet") or {}).get("text") or ""
    return " ".join([t.get("text") or "", a.get("title") or "", a.get("preview_text") or "", q])

# ---------- 抽取 ----------
NUM = r"(\d+(?:\.\d+)?)\s*([kKmMbB]|million|billion)?"
def _usd(v, unit):
    v = float(v); u = (unit or "").lower()
    return v * {"k": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}.get(u, 1)

def extract(text):
    t = re.sub(r"\s+", " ", text)
    out = {}
    m = re.search(r"airdrop[^.%\n]{0,40}?(\d+(?:\.\d+)?)\s?%|(\d+(?:\.\d+)?)\s?%[^.\n]{0,25}airdrop", t, re.I)
    if m: out["airdrop_pct"] = float(m.group(1) or m.group(2))
    m = re.search(r"total (?:token )?supply[^0-9]{0,15}" + NUM, t, re.I)
    if m: out["supply"] = _usd(m.group(1), m.group(2))
    else:   # "20M tokens (2% of supply)" → 总量 = 20M / 2%
        m = re.search(NUM + r"\s*(?:\$?[A-Z]{2,10}\s*)?tokens?\s*\(\s*(\d+(?:\.\d+)?)\s?% of (?:the )?(?:total )?supply", t, re.I)
        if m and float(m.group(3)) > 0: out["supply"] = _usd(m.group(1), m.group(2)) / (float(m.group(3)) / 100)
    # 估值锚: 必须同时出现 打新/公募/拍卖 语境, 否则 "pre-market FDV" 会被误当成锚
    sale_ctx = re.search(r"prime sale|public sale|token sale|\bsale\b|\bico\b|auction|presale|pre-sale|pre-tge|launchpad|rais(?:e|ed|ing)|打新|公募|预售|拍卖", t, re.I)
    if sale_ctx:
        pats = [r"(?:sale|ico|auction)\s*(?:FDV|valuation)\s*[:：]?\s*\$\s?" + NUM,      # Sale FDV: $90M
                r"\$\s?" + NUM + r"\s*(?:FDV|valuation)"]                                   # $300M FDV
        for m in (mm for p in pats for mm in re.finditer(p, t, re.I)):
            v, u = m.group(1), m.group(2)
            seg = t[max(0, m.start() - 40):m.end()]
            if re.search(r"pre-?market|premarket|盘前|current|trading at|polymarket", seg, re.I): continue
            out["anchor_fdv"] = _usd(v, u); break
        for m in re.finditer(r"(?:sale price|price per token|token price|price)[^$\d]{0,12}\$\s?(0\.\d+|\d+(?:\.\d+)?)", t, re.I):
            if re.search(r"pre-?market|premarket|盘前|current|market|trading|listing|launch|open", t[max(0, m.start() - 15):m.start() + 6], re.I): continue
            out["sale_price"] = float(m.group(1)); break
        if re.search(r"bonus|1 for 1|double allocation|买1送1|双倍", t, re.I): out["bonus"] = True
    return out

# ---------- 规则 ----------
HIST = CFG["history_note"]
def judge(sym, ext, mark, anchor_known, known_supply=None):
    """返回 (级别, 文案) 或 None"""
    ext = dict(ext)
    if not ext.get("supply") and known_supply: ext["supply"] = known_supply
    ratio = None
    if ext.get("sale_price"):
        ratio = ext["sale_price"] / mark
    elif ext.get("anchor_fdv") and ext.get("supply"):
        ratio = ext["anchor_fdv"] / (mark * ext["supply"])
    if ratio is not None and ext.get("bonus"): ratio /= 2   # 买1送1 实际成本减半(ZAMA 案例)
    if ratio is not None:
        if ratio < 1:
            return "SHORT", f"【偏空】{sym} 盘前价高于估值锚: 锚÷盘前={ratio:.0%}（盘前溢价 {1/ratio-1:.0%}）。{HIST['short']}"
        return "WATCH", f"【反向样本·仅观察】{sym} 估值锚高于盘前价: 锚÷盘前={ratio:.0%}。{HIST['reverse']}"
    if ext.get("anchor_fdv") and not ext.get("supply"):
        return "INFO", f"【估值锚待核】{sym} 出现估值 ${ext['anchor_fdv']/1e6:.0f}M 但没抓到总量, 无法算比值, 请人工看原帖。"
    if ext.get("airdrop_pct") is not None and ext["airdrop_pct"] < CFG["airdrop_lt"] and not anchor_known:
        return "WATCH", f"【空投<{CFG['airdrop_lt']}%·无估值锚·仅观察】{sym} 空投 {ext['airdrop_pct']}%。{HIST['low_airdrop']}"
    return None

# ---------- 通知 ----------
def notify(text, dry=False):
    if dry: log("[dry] 推送:", text); return True
    nd = CFG.get("notify_dir")
    if not nd:      # 没配通知模块就只打日志; 想接 Telegram/邮件等, 写一个带 send_imessage(text) 的 notify.py 填进 notify_dir
        log("[通知未配置] ", text); return True
    sys.path.insert(0, os.path.expanduser(nd))
    from notify import send_imessage
    ok = send_imessage(text)
    log("推送", "ok" if ok else "FAIL", text[:80])
    return ok

# ---------- 回填 ----------
def backfill():
    if not os.path.exists(EVENTS_F): return
    rows = [json.loads(l) for l in open(EVENTS_F) if l.strip()]
    now = int(time.time() * 1000); changed = False
    for r in rows:
        for h in (1, 4, 24):
            k = f"r{h}h"
            if r.get(k) is None and now - r["ms"] > h * 3600_000 + 120_000:
                try:
                    c = close_at(r["sym"], r["ms"] + h * 3600_000)
                    if c: r[k] = round((c / r["mark"] - 1) * 100, 2); changed = True
                except Exception as e: log("回填失败", r["sym"], h, e)
    if changed:
        tmp = EVENTS_F + ".tmp"
        with open(tmp, "w") as f:
            for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, EVENTS_F)

# ---------- 主流程 ----------
def run(dry=False):
    seed = not os.path.exists(STATE_F)      # 首次运行只预热: 记下已有的锚/总量/推文, 不推送(防止把旧消息当新消息)
    if seed: log("首次运行: 预热模式, 不推送")
    st = load_state(); seen = set(st["seen"]); day = time.strftime("%Y-%m-%d")
    syms = premarket_symbols()
    if not syms: log("当前没有盘前合约"); 
    log("盘前合约:", syms)
    names = CFG.get("names", {})
    for sym in syms:
        calls = st["x_calls"].get(day, 0)
        if calls >= CFG["x_daily_call_cap"]:
            log("X 调用达到日上限, 本轮停止搜索", calls); break
        since = st["since"].get(sym, int(time.time()) - 6 * 3600)
        terms = f"${sym}" + (f" OR \"{names[sym]}\"" if sym in names else "")
        q = f"({terms}) (FDV OR airdrop OR tokenomics OR sale OR auction OR valuation) since_time:{since}"
        try:
            tweets = x_search(q); st["x_fail"] = 0
        except Exception as e:
            st["x_fail"] += 1; log("X 搜索失败", sym, e)
            if st["x_fail"] == CFG["x_fail_alert_after"]:
                notify(f"⚠️ premarket-anchor-watch: X API 连续失败 {st['x_fail']} 次, 监控失明。最后错误: {str(e)[:120]}", dry)
            continue
        finally:
            st["x_calls"][day] = st["x_calls"].get(day, 0) + 1
        st["since"][sym] = int(time.time()) - 60
        try: mark = mark_price(sym)
        except Exception as e: log("取价失败", sym, e); continue
        for t in sorted(tweets, key=lambda t: t["id"]):
            if t["id"] in seen: continue
            seen.add(t["id"]); st["seen"].append(t["id"])
            ext = extract(tweet_text(t))
            if not ext: continue
            sup = CFG.get("supply", {}).get(sym) or st.setdefault("supply", {}).get(sym)
            if ext.get("supply") and not CFG.get("supply", {}).get(sym): st["supply"][sym] = ext["supply"]
            res = judge(sym, ext, mark, sym in st["anchor"] or sym in CFG.get("known_anchor", {}), sup)
            if not res: continue
            lvl, msg = res
            if lvl in ("SHORT",) or (lvl == "WATCH" and "反向" in msg): st["anchor"][sym] = ext
            key = f"{sym}|{lvl}|{ext.get('anchor_fdv') or ext.get('sale_price') or ext.get('airdrop_pct')}"
            if key in st.get("alerted", []): continue      # 同一个数字被多人转述, 只推一次
            st.setdefault("alerted", []).append(key)
            if seed: log("[预热] 记录不推", key); continue
            url = f"https://x.com/{t['author']['userName']}/status/{t['id']}"
            full = f"{msg}\n当前标记价 {mark}\n来源 @{t['author']['userName']}: {url}"
            notify(full, dry)
            if dry: continue
            with open(EVENTS_F, "a") as f:
                f.write(json.dumps({"ms": int(time.time() * 1000), "sym": sym, "level": lvl, "mark": mark, "ext": ext,
                                    "tweet": url, "r1h": None, "r4h": None, "r24h": None}, ensure_ascii=False) + "\n")
    backfill()
    if dry and not seed: log("[dry] 不写 state"); return
    save_state(st)
    open(HEART_F, "w").write(time.strftime("%Y-%m-%d %H:%M:%S") + f" syms={len(syms)} xcalls_today={st['x_calls'].get(day,0)}\n")

def selftest():
    """阳性对照: 历史真实推文 → 必须得到预期判定, 否则退出码 1"""
    cases = json.load(open(os.path.join(HERE, "selftest_cases.json")))
    bad = 0
    for c in cases:
        ext = extract(c["text"])
        res = judge(c["sym"], ext, c["mark"], c.get("anchor_known", False), c.get("known_supply"))
        lvl = res[0] if res else None
        ok = lvl == c["expect"]
        bad += not ok
        print(("PASS" if ok else "FAIL"), c["name"], "→", lvl, ext)
    print("selftest", "OK" if not bad else f"{bad} FAIL")
    return bad == 0

if __name__ == "__main__":
    if "--selftest" in sys.argv: sys.exit(0 if selftest() else 1)
    try: run(dry="--dry" in sys.argv)
    except Exception:
        tb = traceback.format_exc(); log("致命错误", tb)
        flag = os.path.join(HERE, ".fatal_alerted")
        if not os.path.exists(flag) or time.time() - os.path.getmtime(flag) > 6 * 3600:   # 崩溃要出声, 但 6 小时内只推一次
            try: notify(f"⚠️ premarket-anchor-watch 崩溃: {tb.strip().splitlines()[-1][:150]}", "--dry" in sys.argv); open(flag, "w").write(tb)
            except Exception: pass
        sys.exit(1)
