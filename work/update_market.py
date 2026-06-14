import concurrent.futures
import json
import math
import ssl
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
    SSL_CONTEXT = ssl.create_default_context()

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs"
OUT = OUT_DIR / "market-data.json"
UA = {
    "User-Agent": "Mozilla/5.0 TaiwanStockAI/3.0 (+https://github.com/kuo0819/taiwan-stock-ai)",
    "Accept": "application/json,text/plain,*/*",
    "Cache-Control": "no-cache",
}

URLS = {
    "twse_all": "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
    "tpex_all": "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
}

SECTOR_GROUPS = {
    "etf": {"0050","0056","006208","00713","00878","00919","00929","00923","00922","00881","00692","00757","00850"},
    "semiconductor": {"2330","2303","2454","3034","2379","3711","3443","3661","3529","3105","4966","6488","6531","6770","6415","3016"},
    "electronics_ai_server": {"2317","2382","3231","2356","6669","3324","3017","2360","4938","2308","2324","2395","3706","2353","2376"},
    "finance": {"2881","2882","2883","2884","2885","2886","2887","2888","2889","2890","2891","2892","5880","5876","2801","2812"},
    "shipping": {"2603","2609","2615","2618","2606","2610","2617","2637","2634"},
    "defensive_telecom": {"2412","3045","4904","6505","1101","1102","1216","2912"},
    "biotech": {"1795","4123","4743","6446","6547","6472","1760","1789","3164"},
}

GROUP_LABELS = {
    "etf": "ETF",
    "semiconductor": "半導體",
    "electronics_ai_server": "電子／AI／伺服器",
    "finance": "金融",
    "shipping": "航運",
    "defensive_telecom": "防禦／電信／民生",
    "biotech": "生技醫療",
    "other": "其他",
}


def fetch_json(url, attempts=4, timeout=35):
    last = None
    for i in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as res:
                raw = res.read()
                if not raw.strip():
                    raise ValueError("empty response")
                text = raw.decode("utf-8-sig")
                if text.lstrip()[:1] not in ("[", "{"):
                    raise ValueError(f"non-json response: {text[:80]}")
                return json.loads(text)
        except Exception as exc:
            last = exc
            if i < attempts:
                time.sleep(min(12, 1.7 ** i))
    raise RuntimeError(f"Failed to fetch JSON: {url}: {last}")


def n(value, default=0.0):
    try:
        if value is None:
            return default
        s = str(value).replace(",", "").replace("--", "").strip()
        if not s:
            return default
        return float(s)
    except Exception:
        return default


def roc_to_iso(value):
    raw = str(value or "").strip().replace("/", "")
    if len(raw) == 7 and raw[:3].isdigit():
        return f"{int(raw[:3]) + 1911}-{raw[3:5]}-{raw[5:7]}"
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    # fallback to today if source field format changes
    return datetime.now(timezone.utc).date().isoformat()


def pick(row, *names):
    for name in names:
        if name in row and str(row.get(name, "")).strip() not in ("", "--"):
            return row.get(name)
    return None


def classify(code, name):
    for group, codes in SECTOR_GROUPS.items():
        if code in codes:
            return group, GROUP_LABELS[group]
    if code.startswith("00"):
        return "etf", "ETF"
    if any(k in name for k in ("半導", "台積", "聯發", "矽", "晶", "封測")):
        return "semiconductor", "半導體"
    if any(k in name for k in ("金", "銀", "保", "證")):
        return "finance", "金融"
    return "other", "其他"


def parse_twse(rows):
    out = []
    for row in rows:
        code = str(pick(row, "Code", "證券代號") or "").strip()
        name = str(pick(row, "Name", "證券名稱") or "").strip()
        if not code or not name:
            continue
        is_stock = len(code) == 4 and code.isdigit()
        is_etf = code.startswith("00") and 4 <= len(code) <= 7
        if not (is_stock or is_etf):
            continue
        price = n(pick(row, "ClosingPrice", "收盤價", "Close"))
        if price <= 0:
            continue
        volume = n(pick(row, "TradeVolume", "成交股數", "Volume"))
        value = n(pick(row, "TradeValue", "成交金額", "Value"))
        open_ = n(pick(row, "OpeningPrice", "開盤價"), price)
        high = n(pick(row, "HighestPrice", "最高價"), price)
        low = n(pick(row, "LowestPrice", "最低價"), price)
        change = n(pick(row, "Change", "漲跌價差", "漲跌"))
        date = roc_to_iso(pick(row, "Date", "日期"))
        group, sector = classify(code, name)
        out.append({
            "code": code, "name": name, "market": "上市", "asset_type": "ETF" if is_etf else "股票",
            "sector_group": group, "sector": sector, "price": price, "open": open_, "high": high, "low": low,
            "change": change, "volume": volume, "value": value, "date": date,
        })
    return out


def parse_tpex(rows):
    out = []
    for row in rows:
        code = str(pick(row, "SecuritiesCompanyCode", "Code", "代號") or "").strip()
        name = str(pick(row, "CompanyName", "Name", "名稱") or "").strip()
        if not code or not name:
            continue
        is_stock = len(code) == 4 and code.isdigit()
        is_etf = code.startswith("00") and 4 <= len(code) <= 7
        if not (is_stock or is_etf):
            continue
        price = n(pick(row, "Close", "ClosingPrice", "收盤"))
        if price <= 0:
            continue
        volume = n(pick(row, "TradingShares", "TradeVolume", "成交股數"))
        value = n(pick(row, "TransactionAmount", "TradeValue", "成交金額"))
        open_ = n(pick(row, "Open", "OpeningPrice"), price)
        high = n(pick(row, "High", "HighestPrice"), price)
        low = n(pick(row, "Low", "LowestPrice"), price)
        change = n(pick(row, "Change", "漲跌"))
        date = roc_to_iso(pick(row, "Date", "日期"))
        group, sector = classify(code, name)
        out.append({
            "code": code, "name": name, "market": "上櫃", "asset_type": "ETF" if is_etf else "股票",
            "sector_group": group, "sector": sector, "price": price, "open": open_, "high": high, "low": low,
            "change": change, "volume": volume, "value": value, "date": date,
        })
    return out


def yahoo_history(code, market):
    suffix = "TW" if market == "上市" else "TWO"
    symbol = f"{code}.{suffix}" if not code.startswith("^") else code
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=1y&interval=1d"
    try:
        data = fetch_json(url, attempts=2, timeout=18)["chart"]["result"][0]
        q = data["indicators"]["quote"][0]
        adj = data["indicators"].get("adjclose", [{}])[0].get("adjclose") or q.get("close") or []
        highs = q.get("high") or []
        lows = q.get("low") or []
        vols = q.get("volume") or []
        rows = [(c, h, l, v or 0) for c, h, l, v in zip(adj, highs, lows, vols) if c is not None and h is not None and l is not None]
        if len(rows) < 70:
            return None
        closes = [x[0] for x in rows]
        highs = [x[1] for x in rows]
        lows = [x[2] for x in rows]
        vols = [x[3] for x in rows]
        return {"closes": closes[-260:], "highs": highs[-260:], "lows": lows[-260:], "volumes": vols[-260:]}
    except Exception:
        return None


def sma(values, length):
    if len(values) < length:
        return None
    return sum(values[-length:]) / length


def rsi(closes, length=14):
    if len(closes) <= length:
        return 50.0
    gains, losses = [], []
    for i in range(-length, 0):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0))
        losses.append(max(-ch, 0))
    avg_gain = sum(gains) / length
    avg_loss = sum(losses) / length
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def atr(highs, lows, closes, length=14):
    if len(closes) <= length:
        return None
    trs = []
    for i in range(-length, 0):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    return sum(trs) / len(trs)


def max_drawdown(closes):
    peak = closes[0]
    mdd = 0
    for c in closes:
        peak = max(peak, c)
        mdd = min(mdd, c / peak - 1)
    return mdd


def enrich(item):
    hist = yahoo_history(item["code"], item["market"])
    price = item["price"]
    if hist:
        closes, highs, lows, vols = hist["closes"], hist["highs"], hist["lows"], hist["volumes"]
        ma20 = sma(closes, 20) or price
        ma60 = sma(closes, 60) or price
        rsi14 = rsi(closes, 14)
        atr14 = atr(highs, lows, closes, 14) or max(price * 0.035, 0.01)
        ret20 = closes[-1] / closes[-21] - 1 if len(closes) > 21 else 0
        ret60 = closes[-1] / closes[-61] - 1 if len(closes) > 61 else 0
        volume20 = sum(vols[-20:]) / 20 if len(vols) >= 20 else item["volume"]
        mdd = max_drawdown(closes[-120:]) if len(closes) >= 120 else 0
        source = "TWSE/TPEx + Yahoo history"
    else:
        ma20 = price * 0.995
        ma60 = price * 0.985
        rsi14 = 50 + max(-12, min(12, item["change"] / max(price - item["change"], 0.01) * 100 * 2))
        atr14 = max((item["high"] - item["low"]), price * 0.035, 0.01)
        ret20 = item["change"] / max(price - item["change"], 0.01)
        ret60 = ret20
        volume20 = item["volume"]
        mdd = 0
        source = "TWSE/TPEx official close only"

    near_ma20 = abs(price / ma20 - 1) if ma20 else 0.99
    trend_ok = price > ma60 and ma20 >= ma60 and ret60 > -0.02
    not_chasing = price < ma20 * 1.10 and rsi14 < 72
    momentum_ok = 43 <= rsi14 <= 68 and ret20 > -0.06
    liquidity_score = min(25, math.log10(max(item["value"], 1)) * 2.6)
    trend_score = 30 if trend_ok else 12
    position_score = max(0, 20 - near_ma20 * 250)
    momentum_score = max(0, min(20, (rsi14 - 40) * 0.9)) if momentum_ok else 6
    risk_score = max(0, 15 + mdd * 40)
    score = round(liquidity_score + trend_score + position_score + momentum_score + risk_score)

    reference = min(price, ma20 * 1.02)
    stop = max(reference - atr14 * 1.8, reference * 0.90)
    risk = max(reference - stop, 0.01)
    tp1 = reference + risk * 1.0
    tp2 = reference + risk * 2.0
    tp3 = reference + risk * 3.0

    if trend_ok and not_chasing and momentum_ok and score >= 78:
        decision, code, reason = "A 級觀察：可等回測買進", "enter", "趨勢偏多、位置未明顯追高，適合等回測到買進區再分批布局。"
    elif trend_ok and not_chasing and score >= 66:
        decision, code, reason = "B 級觀察：等待更好價格", "wait", "中期趨勢尚可，但分數或位置還不夠漂亮，先等靠近支撐。"
    else:
        decision, code, reason = "暫不進場", "avoid", "趨勢、位置或動能條件不足，保留資金。"

    item.update({
        "score": score,
        "decision": decision,
        "decision_code": code,
        "reason": reason,
        "ma20": round(ma20, 2),
        "ma60": round(ma60, 2),
        "rsi14": round(rsi14, 1),
        "atr14": round(atr14, 2),
        "return20": round(ret20 * 100, 2),
        "return60": round(ret60 * 100, 2),
        "max_drawdown120": round(mdd * 100, 2),
        "avg_volume20": round(volume20),
        "entry_low": round(reference * 0.98, 2),
        "entry_high": round(reference * 1.005, 2),
        "stop": round(stop, 2),
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "tp3": round(tp3, 2),
        "risk_pct": round(risk / reference * 100, 1),
        "data_source": source,
    })
    return item


def market_filter(items):
    # 用 0050 作為台股大盤代理，抓不到則用全部平均分數做中性判斷。
    etf0050 = next((x for x in items if x["code"] == "0050"), None)
    if etf0050 and etf0050.get("ma60"):
        if etf0050["price"] > etf0050["ma60"] and etf0050["ma20"] >= etf0050["ma60"]:
            return {"state": "多頭", "exposure": 75, "description": "0050 位於 60 日線上方，台股大盤偏多。"}
        if etf0050["price"] > etf0050["ma60"] * 0.97:
            return {"state": "中性", "exposure": 50, "description": "0050 接近 60 日線，大盤中性，降低追價。"}
        return {"state": "防守", "exposure": 30, "description": "0050 低於 60 日線，先以防守為主。"}
    avg = statistics.mean([x.get("score", 50) for x in items[:80]]) if items else 50
    return {"state": "中性" if avg >= 60 else "防守", "exposure": 50 if avg >= 60 else 30, "description": "以全市場動能估算大盤狀態。"}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    errors = []
    twse_rows, tpex_rows = [], []
    try:
        twse_rows = fetch_json(URLS["twse_all"])
    except Exception as exc:
        errors.append(f"TWSE failed: {exc}")
    try:
        tpex_rows = fetch_json(URLS["tpex_all"])
    except Exception as exc:
        errors.append(f"TPEx failed: {exc}")

    if not twse_rows and not tpex_rows:
        raise RuntimeError("All official quote sources failed: " + " | ".join(errors))

    items = parse_twse(twse_rows) + parse_tpex(tpex_rows)
    if not items:
        raise RuntimeError("No securities parsed from official quote data")

    market_date = max(x["date"] for x in items if x.get("date"))
    # 先用成交金額挑候選，再補歷史，避免 Yahoo 請求太多。
    candidates = sorted(items, key=lambda x: x.get("value", 0), reverse=True)[:140]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        enriched = list(pool.map(enrich, candidates))

    ranked = sorted(enriched, key=lambda x: (x.get("score", 0), x.get("value", 0)), reverse=True)
    mf = market_filter(ranked)
    if mf["state"] == "防守":
        for x in ranked:
            if x["decision_code"] == "enter":
                x["decision"] = "B 級觀察：大盤防守，暫不積極買進"
                x["decision_code"] = "wait"
                x["score"] = max(0, x["score"] - 8)
                x["reason"] += " 但大盤濾網偏防守，建議只做紙上觀察或降低部位。"
        ranked = sorted(ranked, key=lambda x: (x.get("score", 0), x.get("value", 0)), reverse=True)

    groups = {}
    for x in ranked:
        groups.setdefault(x["sector_group"], []).append(x["code"])

    payload = {
        "model_version": "3.1.0-fixed-official-first",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_date": market_date,
        "universe_count": len(items),
        "history_count": len(ranked),
        "enter_count": sum(x["decision_code"] == "enter" for x in ranked),
        "wait_count": sum(x["decision_code"] == "wait" for x in ranked),
        "avoid_count": sum(x["decision_code"] == "avoid" for x in ranked),
        "market_filter": mf,
        "source_summary": {
            "primary": "TWSE/TPEx official daily close",
            "history_optional": "Yahoo Finance 1Y history for top-liquidity candidates; fail-soft",
            "warnings": errors,
            "note": "若 Yahoo 歷史資料失敗，仍會用官方盤後資料產生當日市場資料，避免網站停在舊日期。",
        },
        "groups": {k: {"label": GROUP_LABELS.get(k, k), "count": len(v)} for k, v in groups.items()},
        "method": "官方盤後資料優先；以流動性、趨勢、位置、RSI、ATR 風控產生台股日線波段觀察名單。不是當沖，不代表買賣建議。",
        "stocks": ranked,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUT}: market_date={market_date}, universe={len(items)}, analyzed={len(ranked)}, enter={payload['enter_count']}")
    if errors:
        print("Warnings:")
        for e in errors:
            print("-", e)


if __name__ == "__main__":
    main()
