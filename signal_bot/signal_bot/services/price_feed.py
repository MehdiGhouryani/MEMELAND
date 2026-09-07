"""
قیمت لحظه‌ای برای آلارم رسیدن به ورود — services/price_feed.py

هردو API رایگان، بدون کلید. GeckoTerminal اصلی (برای توکن‌های خیلی تازه که
جای دیگه ایندکس نشدن بهتره)، DexScreener پشتیبان (وقتی GeckoTerminal
چیزی نداره) + تشخیص خودکار chain موقع ثبت سیگنال (چون chain نمی‌خواد).

فرمت endpointها از مستندات رسمی/نمونه‌ی واقعی چک شده، نه فرض:
  GeckoTerminal: GET /api/v2/simple/networks/{network}/token_price/{addr1,addr2,...}
                 -> {"data":{"attributes":{"token_prices":{"<addr>":"123.45"}}}}
  DexScreener:   GET /latest/dex/tokens/{addr1,addr2,...}
                 -> {"pairs":[{"chainId":"solana","priceUsd":"0.0012",
                               "liquidity":{"usd":50000}, "baseToken":{"address":...}}]}

⚠️ GeckoTerminal رسماً "beta, subject to change" هست. ⚠️ chain تو DB ما همیشه
به slugهای خودِ GeckoTerminal نرمالایز می‌شه (eth/bsc/solana/base/arbitrum/
polygon_pos/avax/optimism — این‌ها از مستندات واقعی GeckoTerminal با مثال
curl تأیید شدن). map زیر chainId خروجی DexScreener رو به همین slugها
تبدیل می‌کنه؛ برای چندتای رایج (eth/bsc/solana/base/arbitrum/polygon/avax/
optimism) مطمئنم، ولی برای شبکه‌های کم‌رایج‌تر تأیید زنده نشده — اگه یه
chain جدید لازم شد که این‌جا نیست، قبل از اعتماد بهش با یه فراخوانی واقعی
GeckoTerminal تست کن.
"""
import asyncio
import logging

import aiohttp

GECKOTERMINAL_URL = "https://api.geckoterminal.com/api/v2/simple/networks/{network}/token_price/{addresses}"
DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/{addresses}"
_TIMEOUT = aiohttp.ClientTimeout(total=10)
_BATCH_SIZE = 30  # سقف مستندشده‌ی هردو API برای چندآدرسی تو یه درخواست

# DexScreener chainId -> GeckoTerminal network slug (کانونیکال داخلی ما).
# فقط شبکه‌های زیر رو زنده تأیید کردم؛ ناشناخته‌ها None برمی‌گردن (یعنی
# انتخاب دستی لازمه، نه یه حدس خطرناک).
_DEXSCREENER_TO_CANONICAL_CHAIN = {
    "ethereum": "eth", "bsc": "bsc", "solana": "solana", "base": "base",
    "arbitrum": "arbitrum", "polygon": "polygon_pos", "avalanche": "avax",
    "optimism": "optimism",
}


async def _get_json(session: aiohttp.ClientSession, url: str):
    try:
        async with session.get(url, timeout=_TIMEOUT) as r:
            if r.status != 200:
                if r.status == 429:
                    logging.warning("price_feed: rate limited by %s", url.split("/")[2])
                return None
            return await r.json()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logging.warning("price_feed: request failed (%s): %s", url.split("/")[2], e)
        return None


async def _geckoterminal_prices(session, network: str, addresses: list) -> dict:
    """{address_lower: price_float} — فقط آدرس‌های جواب‌گرفته."""
    out = {}
    for i in range(0, len(addresses), _BATCH_SIZE):
        chunk = addresses[i:i + _BATCH_SIZE]
        url = GECKOTERMINAL_URL.format(network=network, addresses=",".join(chunk))
        data = await _get_json(session, url)
        if not data:
            continue
        prices = ((data.get("data") or {}).get("attributes") or {}).get("token_prices") or {}
        for addr, price in prices.items():
            try:
                out[addr.lower()] = float(price)
            except (TypeError, ValueError):
                pass
    return out


async def _dexscreener_prices(session, addresses: list) -> dict:
    """{address_lower: (price_float, canonical_chain_or_none)} — بین چند pair
    برای همون آدرس، نقدشونده‌ترین (بیشترین liquidity.usd) انتخاب می‌شه."""
    best = {}  # addr -> (price, chain, liquidity)
    for i in range(0, len(addresses), _BATCH_SIZE):
        chunk = addresses[i:i + _BATCH_SIZE]
        url = DEXSCREENER_URL.format(addresses=",".join(chunk))
        data = await _get_json(session, url)
        if not data:
            continue
        for pair in (data.get("pairs") or []):
            addr = ((pair.get("baseToken") or {}).get("address") or "").lower()
            if not addr:
                continue
            try:
                price = float(pair.get("priceUsd"))
            except (TypeError, ValueError):
                continue
            liq = ((pair.get("liquidity") or {}).get("usd")) or 0
            if addr not in best or liq > best[addr][2]:
                chain = _DEXSCREENER_TO_CANONICAL_CHAIN.get(pair.get("chainId"))
                best[addr] = (price, chain, liq)
    return {addr: (price, chain) for addr, (price, chain, _liq) in best.items()}


async def detect_chain_and_price(contract_address: str):
    """موقع ثبت سیگنال: کنترکت رو بده، (chain, price) حدس زده‌شده رو بگیر —
    یا (None, None) اگه پیدا نشد یا chain ناشناخته بود. همیشه باید دستی هم
    قابل ویرایش/تأیید بمونه، این فقط یه پیشنهاده."""
    async with aiohttp.ClientSession() as session:
        result = await _dexscreener_prices(session, [contract_address])
        hit = result.get(contract_address.lower())
        return hit if hit else (None, None)


async def get_current_prices(signals: list) -> dict:
    """
    ورودی: [{"contract_address": str, "chain": str}, ...]  (هردو الزامی)
    خروجی: {(chain, contract_address_lower): price_float} — فقط اونایی که جواب
    گرفتن. ⚠️ کلید عمداً tuple(chain, address) هست نه فقط address — چون یه
    آدرس EVM می‌تونه رو دو شبکه‌ی مختلف، دو توکن کاملاً نامرتبط باشه؛ کلید
    تک‌بخشی قبلاً باعث می‌شد نتیجه‌ی یه chain نتیجه‌ی chain دیگه رو رو همون
    آدرس overwrite کنه.

    اول GeckoTerminal به‌تفکیک chain (batched)، برای باقی‌مونده‌ها DexScreener.
    """
    by_chain: dict[str, list[str]] = {}
    for s in signals:
        if s.get("chain") and s.get("contract_address"):
            by_chain.setdefault(s["chain"], []).append(s["contract_address"])

    out: dict[tuple, float] = {}
    async with aiohttp.ClientSession() as session:
        for network, addresses in by_chain.items():
            for addr, price in (await _geckoterminal_prices(session, network, addresses)).items():
                out[(network, addr)] = price

        missing_by_chain = {
            network: [a for a in addrs if (network, a.lower()) not in out]
            for network, addrs in by_chain.items()
        }
        for network, addrs in missing_by_chain.items():
            if not addrs:
                continue
            fallback = await _dexscreener_prices(session, addrs)
            for addr, (price, _reported_chain) in fallback.items():
                # chain رو از خودِ رکورد سیگنال می‌گیریم (از قبل با detect_chain_and_price
                # تعیین شده)، نه از حدس DexScreener تو همین فراخوانی — چون این یه fallback
                # دیتاست، نه یه منبع تشخیص chain.
                out[(network, addr)] = price
    return out
