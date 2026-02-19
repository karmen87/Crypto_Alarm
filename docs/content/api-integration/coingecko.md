---
title: "CoinGecko Integration"
weight: 1
---

# CoinGecko API Integration

## Overview

The Crypto Price Alarm uses CoinGecko's **free public API** to fetch real-time cryptocurrency prices. No API key or authentication is required, making deployment simple and accessible.

## API Endpoint

**Base URL**: `https://api.coingecko.com/api/v3`

**Primary Endpoint**: `/simple/price`

## Polling Architecture

### Update Interval: 15 Seconds

Both implementations use a 15-second polling interval:

**JavaScript Implementation**:
```javascript
setInterval(async () => {
  await updateAllPrices();
}, 15000);
```

**Python Implementation**:
```python
from apscheduler.schedulers.background import BackgroundScheduler

sched = BackgroundScheduler()

@sched.scheduled_job('interval', seconds=15)
def update_prices():
    fetch_and_update_all_pairs()
```

### Why 15 Seconds?

**Trade-offs analysis**:

| Interval | Pros | Cons |
|----------|------|------|
| 5s | Very responsive | High API usage, potential rate limiting |
| 10s | Good responsiveness | Moderate API usage |
| **15s** | ✅ Balanced | ✅ Optimal for free tier |
| 30s | Low API usage | Slower alarm response |
| 60s | Minimal API usage | Poor user experience |

**Calculation**:
- 15-second interval = 4 calls/minute per pair
- 10 pairs = 40 calls/minute
- CoinGecko free tier: 50 calls/minute
- **Result**: Safe margin with room for burst requests

## Price Fetching Logic

### Two-Tier Strategy

The app uses different strategies based on the quote currency:

#### Tier 1: Stablecoin Pairs

**Quote currencies**: USDT, USDC, USD, BUSD, DAI

**Strategy**: Treat stablecoin as $1.00, fetch base asset price in USD

**Example: BTCUSDT**
```javascript
async function fetchStablecoinPair(base) {
  const coinId = symbolToCoinId(base); // 'BTC' → 'bitcoin'

  const response = await fetch(
    `https://api.coingecko.com/api/v3/simple/price?ids=${coinId}&vs_currencies=usd`
  );

  const data = await response.json();
  return data[coinId].usd; // Returns BTC price in USD (≈ USDT)
}

// Usage
const btcusdtPrice = await fetchStablecoinPair('BTC');
// Returns: 50000 (BTC price in USD/USDT)
```

**API Request**:
```
GET https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd
```

**API Response**:
```json
{
  "bitcoin": {
    "usd": 50000
  }
}
```

#### Tier 2: Crypto-to-Crypto Pairs

**Quote currencies**: BTC, ETH, BNB, and other cryptocurrencies

**Strategy**: Fetch both assets in USD, calculate ratio

**Example: ETHBTC**
```javascript
async function fetchCryptoPair(base, quote) {
  const baseId = symbolToCoinId(base);   // 'ETH' → 'ethereum'
  const quoteId = symbolToCoinId(quote); // 'BTC' → 'bitcoin'

  const response = await fetch(
    `https://api.coingecko.com/api/v3/simple/price?ids=${baseId},${quoteId}&vs_currencies=usd`
  );

  const data = await response.json();
  const basePrice = data[baseId].usd;   // ETH in USD
  const quotePrice = data[quoteId].usd; // BTC in USD

  return basePrice / quotePrice; // ETH/BTC ratio
}

// Usage
const ethbtcPrice = await fetchCryptoPair('ETH', 'BTC');
// Returns: 0.055 (ETH price in BTC)
```

**API Request**:
```
GET https://api.coingecko.com/api/v3/simple/price?ids=ethereum,bitcoin&vs_currencies=usd
```

**API Response**:
```json
{
  "ethereum": {
    "usd": 2750
  },
  "bitcoin": {
    "usd": 50000
  }
}
```

**Calculation**:
```
ETH/BTC = 2750 / 50000 = 0.055
```

## Symbol to CoinGecko ID Mapping

CoinGecko uses human-readable IDs (e.g., "bitcoin"), not ticker symbols (e.g., "BTC").

### Static Mapping Table

```javascript
const SYMBOL_TO_COIN_ID = {
  // Major cryptocurrencies
  'BTC': 'bitcoin',
  'ETH': 'ethereum',
  'BNB': 'binancecoin',
  'SOL': 'solana',
  'ADA': 'cardano',
  'DOT': 'polkadot',
  'MATIC': 'matic-network',
  'AVAX': 'avalanche-2',
  'LINK': 'chainlink',
  'UNI': 'uniswap',

  // Stablecoins
  'USDT': 'tether',
  'USDC': 'usd-coin',
  'BUSD': 'binance-usd',
  'DAI': 'dai',

  // Layer 1s
  'ATOM': 'cosmos',
  'NEAR': 'near',
  'FTM': 'fantom',
  'ALGO': 'algorand',

  // DeFi
  'AAVE': 'aave',
  'CRV': 'curve-dao-token',
  'MKR': 'maker',
  'COMP': 'compound-governance-token',

  // Add more as needed...
};

function symbolToCoinId(symbol) {
  const coinId = SYMBOL_TO_COIN_ID[symbol.toUpperCase()];

  if (!coinId) {
    throw new Error(`Unknown symbol: ${symbol}. Please add to mapping.`);
  }

  return coinId;
}
```

### Dynamic Lookup (Advanced)

For unknown symbols, query CoinGecko's coin list:

```javascript
async function lookupCoinId(symbol) {
  // Cache coin list (refresh daily)
  if (!coinListCache || isCacheStale()) {
    const response = await fetch(
      'https://api.coingecko.com/api/v3/coins/list'
    );
    coinListCache = await response.json();
  }

  // Find by symbol
  const coin = coinListCache.find(
    c => c.symbol.toUpperCase() === symbol.toUpperCase()
  );

  if (!coin) {
    throw new Error(`Symbol ${symbol} not found on CoinGecko`);
  }

  return coin.id;
}
```

**Coin list response sample**:
```json
[
  {
    "id": "bitcoin",
    "symbol": "btc",
    "name": "Bitcoin"
  },
  {
    "id": "ethereum",
    "symbol": "eth",
    "name": "Ethereum"
  }
]
```

## Rate Limiting & Error Handling

### CoinGecko Free Tier Limits

**Rate Limits**:
- 50 calls/minute
- No API key required
- Subject to IP-based throttling

**Recommended Practices**:
1. Batch requests when possible (multiple IDs in one call)
2. Implement exponential backoff on errors
3. Cache responses briefly (15s in our case)
4. Monitor 429 responses

### Error Handling Strategy

```javascript
async function fetchPriceWithRetry(pair, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const price = await fetchPrice(pair);
      return price;
    } catch (error) {
      if (error.status === 429) {
        // Rate limited - exponential backoff
        const delay = Math.pow(2, attempt) * 1000;
        console.warn(`Rate limited, retrying in ${delay}ms`);
        await sleep(delay);
        continue;
      }

      if (error.status >= 500) {
        // Server error - retry
        console.warn(`Server error, attempt ${attempt}/${maxRetries}`);
        await sleep(1000 * attempt);
        continue;
      }

      // Client error (400, 404) - don't retry
      throw error;
    }
  }

  throw new Error(`Failed to fetch price after ${maxRetries} attempts`);
}
```

### HTTP Status Code Handling

| Status | Meaning | Action |
|--------|---------|--------|
| 200 | Success | Process response |
| 429 | Rate limited | Exponential backoff, retry |
| 500-504 | Server error | Retry with delay |
| 400 | Bad request | Log error, don't retry |
| 404 | Not found | Invalid symbol, don't retry |

### Python Implementation with Retries

```python
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

def get_session():
    """Create session with automatic retries"""
    session = requests.Session()

    retry_strategy = Retry(
        total=3,                    # 3 retry attempts
        backoff_factor=1,           # 1s, 2s, 4s delays
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session

# Usage
session = get_session()
response = session.get(f'{BASE_URL}/simple/price?ids=bitcoin&vs_currencies=usd')
```

## Response Parsing

### Success Response

```json
{
  "bitcoin": {
    "usd": 50000
  }
}
```

**Parsing**:
```javascript
const data = await response.json();
const price = data['bitcoin']['usd'];

if (typeof price !== 'number') {
  throw new Error('Invalid price data');
}

return price;
```

### Error Response

```json
{
  "error": "Could not find coin with the given id"
}
```

**Handling**:
```javascript
const data = await response.json();

if (data.error) {
  throw new Error(`CoinGecko API error: ${data.error}`);
}
```

## Caching Strategy

### In-Memory Cache (15s TTL)

**Purpose**: Avoid duplicate API calls within polling interval

```javascript
const priceCache = new Map();

async function getCachedPrice(pair) {
  const cached = priceCache.get(pair);

  if (cached && Date.now() - cached.timestamp < 15000) {
    // Cache still valid
    return cached.price;
  }

  // Fetch fresh price
  const price = await fetchPrice(pair);

  priceCache.set(pair, {
    price: price,
    timestamp: Date.now()
  });

  return price;
}
```

### Cache Invalidation

**When to invalidate**:
1. After 15 seconds (TTL expiry)
2. On API error (force refresh)
3. User manually refreshes pair

**When NOT to cache**:
- Alarm checking (use fresh price)
- User-triggered updates

## Batch Optimization

### Multiple Pairs Batching

**Instead of**:
```javascript
// ❌ Bad: 3 separate API calls
const btc = await fetch('...?ids=bitcoin&vs_currencies=usd');
const eth = await fetch('...?ids=ethereum&vs_currencies=usd');
const sol = await fetch('...?ids=solana&vs_currencies=usd');
```

**Do this**:
```javascript
// ✅ Good: 1 API call for multiple assets
const response = await fetch(
  'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd'
);

const data = await response.json();
const prices = {
  BTC: data.bitcoin.usd,
  ETH: data.ethereum.usd,
  SOL: data.solana.usd
};
```

### Implementation

```javascript
async function fetchAllPrices(pairs) {
  // Group by quote currency
  const stablecoinPairs = pairs.filter(p => isStablecoin(p.quote));
  const cryptoPairs = pairs.filter(p => !isStablecoin(p.quote));

  // Batch stablecoin pairs
  const stablecoinIds = stablecoinPairs.map(p => symbolToCoinId(p.base)).join(',');
  const stablecoinResponse = await fetch(
    `${API_BASE}/simple/price?ids=${stablecoinIds}&vs_currencies=usd`
  );
  const stablecoinData = await stablecoinResponse.json();

  // Batch crypto pairs (need both base and quote)
  const cryptoIds = new Set();
  cryptoPairs.forEach(p => {
    cryptoIds.add(symbolToCoinId(p.base));
    cryptoIds.add(symbolToCoinId(p.quote));
  });

  const cryptoIdsString = Array.from(cryptoIds).join(',');
  const cryptoResponse = await fetch(
    `${API_BASE}/simple/price?ids=${cryptoIdsString}&vs_currencies=usd`
  );
  const cryptoData = await cryptoResponse.json();

  // Calculate prices
  return {
    ...stablecoinData,
    ...calculateCryptoPairPrices(cryptoPairs, cryptoData)
  };
}
```

**API savings**:
- 10 stablecoin pairs: 10 calls → 1 call (10x reduction)
- 5 crypto pairs: 5 calls → 1 call (5x reduction)

## Network Resilience

### Offline Detection

```javascript
window.addEventListener('online', () => {
  console.log('Connection restored, resuming updates');
  resumePriceUpdates();
});

window.addEventListener('offline', () => {
  console.log('Connection lost, pausing updates');
  pausePriceUpdates();
  showOfflineIndicator();
});
```

### Stale Data Handling

```javascript
function isPriceStale(lastUpdate) {
  const staleThreshold = 60000; // 1 minute
  return Date.now() - lastUpdate > staleThreshold;
}

// UI indication
if (isPriceStale(pair.lastUpdate)) {
  displayStaleWarning(pair);
}
```

## Performance Metrics

### Typical Latency

**CoinGecko API response times**:
- P50: ~200ms
- P95: ~500ms
- P99: ~1000ms

**Total update cycle**:
```
API call: 200-500ms
Parsing: <10ms
Alarm checking: <10ms
UI update: <10ms
Total: ~220-530ms per pair
```

### Monitoring

```javascript
async function fetchPriceWithMetrics(pair) {
  const startTime = performance.now();

  try {
    const price = await fetchPrice(pair);
    const duration = performance.now() - startTime;

    logMetric('api_latency', duration);

    if (duration > 1000) {
      console.warn(`Slow API call: ${pair} took ${duration}ms`);
    }

    return price;
  } catch (error) {
    logMetric('api_error', 1);
    throw error;
  }
}
```

## Alternative APIs (Future Considerations)

### When to Consider Alternatives

- Exceeding CoinGecko rate limits
- Need for sub-second updates
- Require WebSocket real-time feeds
- Need more exotic trading pairs

### Potential Alternatives

| API | Rate Limit (Free) | Real-Time | Auth Required |
|-----|-------------------|-----------|---------------|
| CoinGecko | 50/min | No (HTTP) | No |
| CoinMarketCap | 333/day | No | Yes |
| Binance | 1200/min | Yes (WS) | No (public data) |
| CryptoCompare | 100k/month | Yes (WS) | Yes |

## Testing API Integration

### Mock API Responses

```javascript
// Test helper
function mockCoinGeckoResponse(coinId, price) {
  global.fetch = jest.fn(() =>
    Promise.resolve({
      json: () => Promise.resolve({
        [coinId]: { usd: price }
      })
    })
  );
}

// Test
test('fetches BTC price correctly', async () => {
  mockCoinGeckoResponse('bitcoin', 50000);

  const price = await fetchPrice('BTCUSDT');

  expect(price).toBe(50000);
  expect(global.fetch).toHaveBeenCalledWith(
    expect.stringContaining('ids=bitcoin')
  );
});
```

### Integration Testing

```javascript
test('handles rate limiting gracefully', async () => {
  global.fetch = jest.fn()
    .mockRejectedValueOnce({ status: 429 }) // First call fails
    .mockResolvedValueOnce({                // Retry succeeds
      json: () => Promise.resolve({ bitcoin: { usd: 50000 } })
    });

  const price = await fetchPriceWithRetry('BTCUSDT');

  expect(price).toBe(50000);
  expect(global.fetch).toHaveBeenCalledTimes(2);
});
```

## Debugging Tips

### Enable Request Logging

```javascript
async function fetchPrice(pair) {
  const url = buildApiUrl(pair);

  console.log(`[API] Fetching ${pair}: ${url}`);

  const startTime = Date.now();
  const response = await fetch(url);
  const duration = Date.now() - startTime;

  console.log(`[API] ${pair} response: ${response.status} in ${duration}ms`);

  return parseResponse(response);
}
```

### Common Issues

**Issue**: "Could not find coin with the given id"
```
Solution: Check symbol-to-ID mapping, verify spelling
Example: 'MATIC' → 'matic-network' (not 'polygon')
```

**Issue**: Prices seem wrong for crypto pairs
```
Solution: Verify ratio calculation (base / quote)
Example: ETH/BTC should be ~0.05, not ~20,000
```

**Issue**: 429 rate limit errors
```
Solution: Reduce polling frequency or batch requests
Check: Are you monitoring too many pairs?
```

## Next Steps

- Explore **Alarm Logic** for price data usage
- See **Implementations** for language-specific code
- Check **DevOps** for monitoring and deployment
