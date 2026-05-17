# Chinese Market Data (A-Shares, ETFs, Funds)

When opencli has no Chinese finance adapter (no 雪球/同花顺/东方财富/longbridge installed), use the Tencent Finance HTTP API as a fallback.

## Tencent Finance API (`qt.gtimg.cn`)

Free, no auth, real-time during trading hours (9:30-15:00 CST).

```bash
# Single quote
curl -s "https://qt.gtimg.cn/q=sh000300"

# Multiple quotes in one call
curl -s "https://qt.gtimg.cn/q=sh000300,sh000001,sh518880,sz159915"
```

### Code format

| prefix | market |
|--------|--------|
| `sh`   | Shanghai (indices, ETFs, stocks starting 6) |
| `sz`   | Shenzhen (ETFs, stocks starting 0/3) |

Common codes:
- `sh000001` — 上证指数
- `sh000300` — 沪深300
- `sh000016` — 上证50
- `sh518880` — 黄金ETF华安
- `sh510300` — 沪深300ETF
- `sh511010` — 国债ETF
- `sz159915` — 创业板ETF

### Response format

Response is GBK-encoded, `~`-delimited. Key field positions:

| index | field |
|-------|-------|
| 1 | name (GBK) |
| 2 | code |
| 3 | current price |
| 4 | previous close |
| 5 | open |
| 31 | price change (absolute) |
| 32 | price change (%) |

### Parsing (handles GBK encoding)

```bash
curl -s "https://qt.gtimg.cn/q=sh000300,sh000001,sh518880" \
  | python3 -c "
import sys
raw = sys.stdin.buffer.read().decode('gbk', errors='replace')
for line in raw.strip().split(';'):
    line = line.strip()
    if not line or '=' not in line:
        continue
    parts = line.split('~')
    if len(parts) > 32:
        name = parts[1]
        code = parts[2]
        price = parts[3]
        change = parts[31]
        change_pct = parts[32]
        print(f'{name} ({code}): {price}, {change} ({change_pct}%)')
"
```

### Limitations

- No fund NAV data (基金净值) — only ETF real-time prices
- No bond fund detail — use 中证全债指数 (`sh000023`) as proxy
- No money market fund rates
- Data is delayed ~3s from exchange
- Weekend/holiday data shows last trading day

## CoinGecko (Crypto, via opencli)

For Bitcoin and other crypto, use `opencli coingecko`:

```bash
opencli coingecko coin bitcoin -f json          # BTC details
opencli coingecko top --limit 5 -f json         # top coins
opencli coingecko coin tether-gold -f json      # gold price proxy
```

For CNY conversion: `curl -s "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=cny"`

## Gold Price

- International: `opencli coingecko coin tether-gold` (XAUT, tracks physical gold)
- Domestic ETF: `sh518880` (黄金ETF华安) via Tencent API
- CNY per gram: CoinGecko XAUT price ÷ 31.1035 (troy oz to grams) × CNY rate, or just use the ETF price as proxy

## longbridge (not yet installed)

Available via `opencli external install longbridge`. Supports HK, US, A-share markets with proper API keys from https://open.longbridge.com. Best option for comprehensive Chinese market data if needed regularly.
