# START HERE - Simple Instructions

## Problem Summary

The Python app keeps failing because CoinGecko's free API has very strict rate limits. You've been getting blocked constantly.

## Solution: Use the DEMO Version

I created a version that uses **fake/mock data** so you can see the app working without any API issues.

---

## How to Run It (3 Simple Steps)

### Step 1: Open Terminal in Your Crypto_Alarm Folder

```bash
cd C:\Users\Karmen\Documents\projects\alarm
```

### Step 2: Activate Virtual Environment

```bash
venv\Scripts\activate
```

You should see `(venv)` at the start of your prompt.

### Step 3: Run the Demo

```bash
python app_demo.py
```

---

## What You'll See

The terminal will show:
```
🎮 CRYPTO PRICE ALARM - DEMO MODE (Mock Data)
📍 Open http://localhost:5000 in your browser

Available pairs to add:
  • BTCUSDT - Bitcoin/USDT
  • ETHUSDT - Ethereum/USDT
  • BNBUSDT - Binance Coin/USDT
  • SOLUSDT - Solana/USDT
  • ADAUSDT - Cardano/USDT

Prices update every 5 seconds with random fluctuations
```

---

## Using the Demo

1. **Open browser:** http://localhost:5000

2. **Add a pair:** Type `BTCUSDT` and click "Add Pair"
   - It will add INSTANTLY (no waiting, no API calls)

3. **Watch prices update:** Every 5 seconds, prices change randomly

4. **Set an alarm:**
   - Click "Alarms" on the pair
   - Set a target price close to the current price
   - Click "Add"
   - Wait a bit and watch it trigger!

5. **Try other pairs:** ETHUSDT, BNBUSDT, SOLUSDT, ADAUSDT

---

## What This Demo Does

✅ All the same features as the real app
✅ No API calls = no rate limiting = no failures
✅ Prices update every 5 seconds automatically
✅ Alarms work exactly the same way
✅ Audio alerts work
✅ All UI features work

❌ Not real prices (fake data)
❌ Only 5 pre-set trading pairs available

---

## Next Steps

Once you see the demo working, we have options:

**Option A:** Keep using the original **JavaScript version** (the one in `index.html`)
- Just open `index.html` directly in your browser
- Uses real CoinGecko data but no Python needed

**Option B:** Get a **CoinGecko API key** (paid, $130/month)
- Removes rate limits
- Makes the Python version work reliably

**Option C:** Use a **different data source**
- Binance, Coinbase, etc. (I can help implement this)

---

## If the Demo Doesn't Work

If even the demo fails, something is wrong with your Python/Flask setup. Let me know and I'll help debug that specifically.

But the demo should work because it doesn't make any external API calls!

---

**Just run: `python app_demo.py` and open http://localhost:5000**

That's it!
