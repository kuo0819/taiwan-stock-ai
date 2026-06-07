import concurrent.futures
import json
import math
import ssl
import statistics
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "market-data.json"
UA = {"User-Agent": "Mozilla/5.0 TaiwanEquityLab/1.0"}
SSL_CONTEXT = ssl._create_unverified_context()

URLS = {
    "tw_quote": "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
    "tw_value": "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL",
    "tw_revenue": "https://openapi.twse.com.tw/v1/opendata/t187ap05_L",
    "otc_quote": "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
    "otc_value": "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis",
    "otc_revenue": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O",
    "tw_income": "https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci",
    "tw_balance": "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ci",
    "otc_income": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap06_O_ci",
    "otc_balance": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap07_O_ci",
}


def fetch_json(url, attempts=5):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            headers = {
                **UA,
                "Accept": "application/json,text/plain,*/*",
                "Cache-Control": "no-cache",
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=45, context=SSL_CONTEXT) as res:
                body = res.read()
                if not body.strip():
                    raise ValueError("received an empty response")
                content_type = res.headers.get("Content-Type", "")
                text = body.decode("utf-8-sig")
                if "json" not in content_type.lower() and text.lstrip()[:1] not in ("[", "{"):
                    raise ValueError(f"received non-JSON response ({content_type or 'unknown type'})")
                return json.loads(text)
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(min(20, 2 ** attempt))
    raise RuntimeError(f"Failed to download JSON after {attempts} attempts: {url}: {last_error}")


def num(value, default=0.0):
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return default


def roc_date(value):
    raw = str(value)
    if len(raw) == 7:
        return f"{int(raw[:3]) + 1911}-{raw[3:5]}-{raw[5:7]}"
    return raw


def revenue_map(rows):
    result = {}
    for row in rows:
        values = list(row.values())
        if len(values) < 12:
            continue
        code = str(values[2]).strip()
        result[code] = {
            "industry": str(values[4]).strip(),
            "revenue_yoy": num(values[9]),
            "revenue_ytd": num(values[12]) if len(values) > 12 else 0,
        }
    return result


def first_num(row, names):
    for name in names:
        if name in row and str(row[name]).strip():
            return num(row[name])
    return 0


def financial_map(income_rows, balance_rows):
    result = {}
    for row in income_rows:
        code = str(row.get("公司代號") or row.get("SecuritiesCompanyCode") or "").strip()
        if code:
            result.setdefault(code, {})["eps"] = first_num(row, ["基本每股盈餘（元）", "基本每股盈餘(元)"])
            result[code]["net_income"] = first_num(row, ["本期淨利（淨損）", "本期淨利(淨損)"])
    for row in balance_rows:
        code = str(row.get("公司代號") or row.get("SecuritiesCompanyCode") or "").strip()
        if not code:
            continue
        assets = first_num(row, ["資產總額", "資產總計"])
        liabilities = first_num(row, ["負債總額", "負債總計"])
        equity = first_num(row, ["權益總額", "權益總計"])
        item = result.setdefault(code, {})
        item["debt_ratio"] = liabilities / assets * 100 if assets else 0
        item["roe"] = item.get("net_income", 0) * 4 / equity * 100 if equity else 0
    return result


def percentile(values, value, reverse=False):
    if not values:
        return 0.5
    rank = sum(v <= value for v in values) / len(values)
    return 1 - rank if reverse else rank


def historical(item):
    suffix = "TW" if item["market"] == "上市" else "TWO"
    symbol = item["code"] if item["code"].startswith("^") else f"{item['code']}.{suffix}"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=2y&interval=1d"
    try:
        data = fetch_json(url)["chart"]["result"][0]
        q = data["indicators"]["quote"][0]
        closes = [x for x in q["close"] if x is not None]
        volumes = [x or 0 for x in q["volume"]]
        if len(closes) < 130:
            return None
        returns = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
        peak, max_dd = closes[0], 0
        for price in closes:
            peak = max(peak, price)
            max_dd = min(max_dd, price / peak - 1)
        cashflow = None
        if item["asset_type"] == "股票":
            now = int(datetime.now(timezone.utc).timestamp())
            cash_url = (
                f"https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/"
                f"{item['code']}.{suffix}?symbol={item['code']}.{suffix}&type=quarterlyOperatingCashFlow"
                f"&merge=false&period1=1640995200&period2={now}"
            )
            try:
                cf = fetch_json(cash_url, attempts=2)["timeseries"]["result"][0].get("quarterlyOperatingCashFlow", [])
                values = [x["reportedValue"]["raw"] for x in cf[-4:] if x.get("reportedValue")]
                cashflow = sum(values) if values else None
            except Exception:
                cashflow = None
        return {
            "prices": [round(x, 2) for x in closes[-500:]],
            "return20": closes[-1] / closes[-21] - 1,
            "return60": closes[-1] / closes[-61] - 1,
            "return120": closes[-1] / closes[-121] - 1,
            "volatility": statistics.stdev(returns[-60:]) * math.sqrt(252),
            "max_drawdown": max_dd,
            "avg_volume20": sum(volumes[-20:]) / 20,
            "ma20": sum(closes[-20:]) / 20,
            "ma60": sum(closes[-60:]) / 60,
            "operating_cashflow": cashflow,
        }
    except Exception:
        return None


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        raw = dict(zip(URLS, pool.map(fetch_json, URLS.values())))

    tw_rev, otc_rev = revenue_map(raw["tw_revenue"]), revenue_map(raw["otc_revenue"])
    financials = financial_map(raw["tw_income"] + raw["otc_income"], raw["tw_balance"] + raw["otc_balance"])
    valuations = {}
    for row in raw["tw_value"]:
        valuations[row["Code"]] = {
            "pe": num(row["PEratio"]), "yield": num(row["DividendYield"]), "pb": num(row["PBratio"])
        }
    for row in raw["otc_value"]:
        valuations[row["SecuritiesCompanyCode"]] = {
            "pe": num(row["PriceEarningRatio"]), "yield": num(row["YieldRatio"]), "pb": num(row["PriceBookRatio"])
        }

    universe = []
    for market, rows, revs in [
        ("上市", raw["tw_quote"], tw_rev),
        ("上櫃", raw["otc_quote"], otc_rev),
    ]:
        for row in rows:
            code = str(row.get("Code") or row.get("SecuritiesCompanyCode", "")).strip()
            is_stock = len(code) == 4 and code.isdigit() and code in revs
            is_etf = code.startswith("00") and 4 <= len(code) <= 7
            if not is_stock and not is_etf:
                continue
            price = num(row.get("ClosingPrice") or row.get("Close"))
            volume = num(row.get("TradeVolume") or row.get("TradingShares"))
            value = num(row.get("TradeValue") or row.get("TransactionAmount"))
            if price <= 0:
                continue
            fundamentals = revs.get(code, {"industry": "ETF", "revenue_yoy": 0, "revenue_ytd": 0})
            asset_type = "ETF" if is_etf else "股票"
            if is_etf:
                name = str(row.get("Name") or row.get("CompanyName")).strip()
                if code.endswith("B"):
                    fundamentals["industry"] = "債券 ETF"
                elif "反" in name or code.endswith("R"):
                    fundamentals["industry"] = "反向 ETF"
                elif "槓" in name or code.endswith("L"):
                    fundamentals["industry"] = "槓桿 ETF"
                else:
                    fundamentals["industry"] = "股票／資產 ETF"
            item = {
                "code": code,
                "name": str(row.get("Name") or row.get("CompanyName")).strip(),
                "market": market,
                "price": price,
                "change": num(row.get("Change")),
                "volume": volume,
                "value": value,
                "asset_type": asset_type,
                **fundamentals,
                **valuations.get(code, {"pe": 0, "yield": 0, "pb": 0}),
                **financials.get(code, {"eps": 0, "roe": 0, "debt_ratio": 0}),
            }
            universe.append(item)

    revenue_vals = [x["revenue_yoy"] for x in universe]
    value_vals = [math.log10(x["value"]) for x in universe]
    for x in universe:
        value_score = 0.5
        if 0 < x["pe"] < 50:
            value_score += 0.25
        if 0 < x["pb"] < 5:
            value_score += 0.15
        if x["yield"] > 2:
            value_score += 0.10
        x["stage1"] = (
            percentile(revenue_vals, x["revenue_yoy"]) * 45
            + percentile(value_vals, math.log10(x["value"])) * 35
            + value_score * 20
        )

    candidates = sorted(universe, key=lambda x: x["stage1"], reverse=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        histories = list(pool.map(historical, candidates))
    ranked = []
    for item, hist in zip(candidates, histories):
        if hist:
            item.update(hist)
            ranked.append(item)

    r20, r60, r120 = ([x[k] for x in ranked] for k in ("return20", "return60", "return120"))
    vols = [x["volatility"] for x in ranked]
    for x in ranked:
        momentum = percentile(r20, x["return20"]) * 15 + percentile(r60, x["return60"]) * 20 + percentile(r120, x["return120"]) * 15
        if x["asset_type"] == "ETF":
            quality = 15
            x["quality_pass"] = None
        else:
            checks = [
                x.get("eps", 0) > 0,
                x.get("roe", 0) >= 10,
                x.get("operating_cashflow") is not None and x["operating_cashflow"] > 0,
                0 < x.get("debt_ratio", 0) < 60,
                x["revenue_yoy"] > 0,
            ]
            x["quality_pass"] = sum(checks)
            quality = x["quality_pass"] / len(checks) * 25
        liquidity = percentile(value_vals, math.log10(x["value"])) * 15
        risk = percentile(vols, x["volatility"], reverse=True) * 7 + percentile(
            [y["max_drawdown"] for y in ranked], x["max_drawdown"]
        ) * 3
        raw_score = round(momentum + quality + liquidity + risk)
        atr_risk = min(0.14, max(0.05, x["volatility"] / math.sqrt(252) * 3))
        trend_ok = x["price"] >= x["ma60"] and x["return60"] > 0.03 and x["return120"] > 0
        not_overheated = x["return20"] < 0.25 and x["price"] < x["ma20"] * 1.12
        risk_ok = x["volatility"] < 0.70 and x["max_drawdown"] > -0.60
        quality_ok = x["asset_type"] == "ETF" or x.get("quality_pass", 0) >= 3
        if trend_ok and not_overheated and risk_ok and quality_ok and x["return20"] > -0.04:
            x["decision"], x["decision_code"] = "可分批進場", "enter"
            reason = "中長期趨勢向上，短線未明顯過熱，波動仍在模型可承受範圍。"
        elif trend_ok and risk_ok:
            x["decision"], x["decision_code"] = "等待回測", "wait"
            reason = "中期趨勢偏多，但短線漲幅或乖離較大，等待價格靠近均線較有利。"
        else:
            x["decision"], x["decision_code"] = "暫不進場", "avoid"
            reason = "趨勢或風險條件尚未通過，現階段優先保留資金。"
        penalty = {"enter": 0, "wait": 10, "avoid": 25}[x["decision_code"]]
        x["score"] = max(0, raw_score - penalty)
        reference = min(x["price"], x["ma20"] * 1.02)
        x["entry_low"] = round(reference * 0.98, 2)
        x["entry_high"] = round(reference * 1.005, 2)
        x["stop"] = round(reference * (1 - atr_risk), 2)
        x["take"] = round(reference * (1 + atr_risk * 2.2), 2)
        x["exit"] = round(reference * (1 + atr_risk * 1.2), 2)
        x["risk_pct"] = round(atr_risk * 100, 1)
        x["reason"] = reason
        x["distance_ma20"] = round((x["price"] / x["ma20"] - 1) * 100, 1)

    ranked = sorted(ranked, key=lambda x: x["score"], reverse=True)
    for rank, x in enumerate(ranked, 1):
        x["rank"] = rank
        detail = (
            f"近 60 日報酬 {x['return60'] * 100:+.1f}%，ETF 採趨勢、流動性與波動風險評估。"
            if x["asset_type"] == "ETF"
            else f"近 60 日報酬 {x['return60'] * 100:+.1f}%，最新月營收年增 {x['revenue_yoy']:+.1f}%。"
        )
        x["thesis"] = f"{x['decision']}。{x['reason']} {x['market']} {x['industry']}；{detail}"
        for key in ("stage1", "avg_volume20"):
            x.pop(key, None)

    market_hist = historical({"code": "^TWII", "market": "上市", "asset_type": "ETF"})
    market_filter = {"state": "資料不足", "exposure": 40, "description": "無法取得大盤資料，採防守部位。"}
    if market_hist:
        prices = market_hist["prices"]
        ma60, ma200, current = sum(prices[-60:]) / 60, sum(prices[-200:]) / 200, prices[-1]
        if current > ma200 and ma60 > ma200:
            market_filter = {"state": "多頭", "exposure": 80, "description": "加權指數位於 200 日線之上，60 日線高於 200 日線。"}
        elif current > ma200:
            market_filter = {"state": "中性", "exposure": 55, "description": "指數位於 200 日線之上，但中期趨勢尚未完全轉強。"}
        else:
            market_filter = {"state": "防守", "exposure": 30, "description": "加權指數低於 200 日線，建議降低股票曝險。"}
        market_filter.update({"price": round(current, 2), "ma60": round(ma60, 2), "ma200": round(ma200, 2)})
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_date": roc_date(raw["tw_quote"][0]["Date"]),
        "universe_count": len(universe),
        "history_count": len(ranked),
        "enter_count": sum(x["decision_code"] == "enter" for x in ranked),
        "wait_count": sum(x["decision_code"] == "wait" for x in ranked),
        "avoid_count": sum(x["decision_code"] == "avoid" for x in ranked),
        "market_filter": market_filter,
        "method": "全市場股票與 ETF → 公司股採營收/估值、ETF 採趨勢/風險 → 20/60/120日動能、波動與風險排名",
        "stocks": ranked,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUT}: screened {len(universe)}, analyzed {len(ranked)}")


if __name__ == "__main__":
    main()
