"""Discover stocks for a theme via THS (同花顺) concept/industry classification.

Data source: 10jqka.com.cn (THS/同花顺) web scraping + Tencent spot verification.
Since Eastmoney APIs are blocked, we use THS as primary data source.

Channel:
1. THS concept board constituents (scraped from q.10jqka.com.cn)
2. Spot verification via Tencent qt.gtimg.cn API
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import requests


# ---------------------------------------------------------------------------
# Theme → keyword mapping for THS concept search
# ---------------------------------------------------------------------------

THEME_KEYWORDS: dict[str, list[str]] = {
    "PCB": ["PCB", "印制电路", "覆铜板", "电子元件"],
    "机器人": ["机器人", "人形机器人", "工业机器人"],
    "AI算力": ["算力", "数据中心", "东数西算", "AI"],
    "光模块": ["光通信", "光模块", "光器件"],
    "半导体": ["半导体", "芯片", "集成电路"],
    "新能源汽车": ["新能源", "锂电池", "电动车"],
}


# ---------------------------------------------------------------------------
# THS concept board scraping (10jqka.com.cn)
# ---------------------------------------------------------------------------

def get_ths_concept_codes(keywords: list[str]) -> list[dict[str, str]]:
    """Get THS concept board codes matching keywords via akshare."""
    import akshare as ak

    df = ak.stock_board_concept_name_ths()
    results = []
    for _, row in df.iterrows():
        name = str(row["name"])
        code = str(row["code"])
        for kw in keywords:
            if kw.lower() in name.lower():
                results.append({"code": code, "name": name})
                break
    return results


def scrape_concept_stocks(concept_code: str, concept_name: str, max_pages: int = 20) -> list[dict[str, str]]:
    """Scrape constituent stocks from 10jqka.com.cn concept board page.

    Returns list of {code, name} for the concept board.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": f"https://q.10jqka.com.cn/gn/detail/code/{concept_code}/",
        "X-Requested-With": "XMLHttpRequest",
    }

    all_stocks = []
    for page in range(1, max_pages + 1):
        url = f"https://q.10jqka.com.cn/gn/detail/order/desc/page/{page}/ajax/1/code/{concept_code}/"
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                break

            # Extract stock codes and names from <tr> rows
            # Pattern: code in first column link, name in second column link
            body_start = r.text.find("<tbody>")
            body_end = r.text.find("</tbody>")
            body = r.text[body_start:body_end] if body_start != -1 else r.text

            rows = body.split("<tr>")
            page_stocks = []
            for row in rows[1:]:
                if not row.strip():
                    continue
                code_match = re.search(r"10jqka\.com\.cn/(\d{6})/", row)
                name_matches = re.findall(r'target="_blank">([^<]+)</a>', row)
                if code_match and len(name_matches) >= 2:
                    page_stocks.append({"code": code_match.group(1), "name": name_matches[1]})

            if not page_stocks:
                break

            all_stocks.extend(page_stocks)

            # Stop if fewer results than page size (likely last page)
            if len(page_stocks) < 10:
                break
        except Exception as e:
            break

    return all_stocks


# ---------------------------------------------------------------------------
# Spot verification via Tencent
# ---------------------------------------------------------------------------

def verify_stock(code: str) -> dict[str, Any] | None:
    """Verify a stock code via Tencent spot API and return enriched data."""
    if code.startswith(("0", "3")):
        prefix = f"sz{code}"
    elif code.startswith("6"):
        prefix = f"sh{code}"
    elif code.startswith("8"):
        prefix = f"bj{code}"
    else:
        return None

    url = f"https://qt.gtimg.cn/q={prefix}"
    try:
        r = requests.get(url, timeout=5)
        for line in r.text.strip().split(";"):
            if '="' not in line:
                continue
            val = line.split('="')[1].rstrip('"')
            parts = val.split("~")
            if len(parts) < 40:
                continue
            if parts[2] != code:
                continue

            name = parts[1]
            price = float(parts[3]) if parts[3] else 0
            prev_close = float(parts[4]) if parts[4] else 0
            change_pct = float(parts[32]) if parts[32] else 0
            pe = float(parts[39]) if parts[39] else None
            volume_hand = float(parts[6]) if parts[6] else 0

            is_st = "ST" in name or "*ST" in name or "退" in name

            return {
                "code": code,
                "name": name,
                "price": price,
                "prev_close": prev_close,
                "change_pct": change_pct,
                "pe_ttm": pe if pe and 0 < pe < 10000 else None,
                "volume_hand": volume_hand,
                "is_st": is_st,
            }
    except Exception:
        pass
    return None


def estimate_avg_turnover(codes: list[str], n: int = 20) -> dict[str, float]:
    """Estimate average daily turnover for stocks over last n days via Tencent history."""
    import akshare as ak

    turnover_map = {}
    for code in codes:
        try:
            clean = code.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
            market = "sz" if clean.startswith(("0", "3", "8")) else "sh"
            url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param={market}{clean},day,,,{n},qfq"
            r = requests.get(url, timeout=5)
            if r.text.startswith("kline_dayqfq="):
                data = json.loads(r.text[len("kline_dayqfq="):])
                key = f"{market}{clean}"
                if key in data.get("data", {}):
                    qfqday = data["data"][key].get("qfqday", [])
                    total_turnover = 0
                    days = 0
                    for row in qfqday[-n:]:
                        if len(row) >= 6:
                            try:
                                vol = float(row[5])
                                # Get price from Tencent spot for this code
                                v = verify_stock(clean)
                                price = v["price"] if v else 0
                                if price > 0:
                                    turnover = vol * 100 * price
                                    total_turnover += turnover
                                    days += 1
                            except Exception:
                                pass
                    if days > 0:
                        turnover_map[code] = total_turnover / days
        except Exception:
            pass
        time.sleep(0.1)

    return turnover_map


# ---------------------------------------------------------------------------
# Main discovery
# ---------------------------------------------------------------------------

def discover_theme(theme: str, keywords: list[str]) -> list[dict[str, Any]]:
    """Discover stocks for a theme via THS concept board scraping."""
    # Step 1: find matching THS concepts
    concepts = get_ths_concept_codes(keywords)
    print(f"  Found {len(concepts)} THS concepts: {[c['name'] for c in concepts[:5]]}")

    all_candidates: dict[str, dict[str, Any]] = {}

    # Step 2: scrape each concept board
    for concept in concepts:
        code = concept["code"]
        name = concept["name"]
        print(f"  Scraping {name} (code={code})...")
        try:
            stocks = scrape_concept_stocks(code, name)
            print(f"    -> {len(stocks)} constituents")
            for s in stocks:
                if s["code"] not in all_candidates:
                    all_candidates[s["code"]] = {
                        "code": s["code"],
                        "name": s["name"],
                        "source": f"THS:{name}",
                    }
        except Exception as e:
            print(f"    -> Error: {e}")

    # Step 3: estimate average turnover for top candidates
    all_verified = list(all_candidates.keys())
    if len(all_verified) > 60:
        print(f"  Estimating avg turnover for {len(all_verified)} candidates...")
        turnover_map = estimate_avg_turnover(all_verified[:100], n=20)
    else:
        turnover_map = {}

    # Step 4: spot verify all candidates
    verified = []
    for code, info in all_candidates.items():
        v = verify_stock(code)
        if v:
            turnover = turnover_map.get(code, 0)
            if turnover == 0:
                # Fall back to single-day estimate
                turnover = v.get("volume_hand", 0) * 100 * v.get("price", 0) if v.get("price") else 0
            verified.append({
                "code": code,
                "name": v["name"],
                "price": v["price"],
                "change_pct": v["change_pct"],
                "pe_ttm": v.get("pe_ttm"),
                "is_st": v["is_st"],
                "volume_hand": v.get("volume_hand"),
                "avg_turnover_20d": turnover,
                "source": info["source"],
            })

    print(f"  Verified {len(verified)}/{len(all_candidates)} stocks via Tencent")
    return verified


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Discover theme stocks via THS concept boards")
    parser.add_argument("--theme", required=True, help="Theme name")
    parser.add_argument("--keywords", nargs="+", help="Keywords (default: use THEME_KEYWORDS)")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    keywords = args.keywords or THEME_KEYWORDS.get(args.theme, [args.theme])
    print(f"\nDiscovering '{args.theme}' stocks via THS...")
    print(f"  Keywords: {keywords}")

    result = discover_theme(args.theme, keywords)

    output = {"theme": args.theme, "stocks": result, "count": len(result)}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nResult: {len(result)} verified stocks -> {args.output}")
    for s in result[:15]:
        st = "ST" if s.get("is_st") else ""
        pe = f"PE={s.get('pe_ttm')}" if s.get("pe_ttm") else ""
        vol = s.get("volume_hand", 0)
        turnover = s.get("avg_turnover_20d", 0)
        turnover_wan = turnover / 10000 if turnover else 0
        print(f"  {s['code']} {s['name']} {st} {pe} turnover={turnover_wan:.0f}万 [{s.get('source','')}]")