# Troubleshooting Guide

## Fixed: Rate Limiting Crash (Nov 10, 2025)

### The Problem
The app was crashing when trying to add trading pairs due to CoinGecko API rate limiting. The app would wait 60 seconds blocking everything.

### The Solution
✅ **Fixed!** The app now:
- Increases API delay from 1.2s to 2.0s between requests
- Returns a friendly error instead of blocking for 60 seconds
- Shows clear messages when rate limited

### How to Get the Fix

1. **Pull the latest changes:**
   ```bash
   cd path/to/Crypto_Alarm
   git pull origin main
   ```

2. **Run the app:**
   ```bash
   python app.py
   ```

### Using the App

**Important:** CoinGecko's free API has strict rate limits. Here's how to use it successfully:

#### ✅ Best Practices

1. **Add pairs slowly** - Wait 5-10 seconds between adding each pair
2. **Start small** - Add 2-3 pairs first, then add more later
3. **Be patient** - If you get a rate limit error, wait 1-2 minutes before trying again
4. **Don't refresh repeatedly** - Each page load makes API calls

#### ⚠️ If You Get Rate Limited

You'll see an error message like:
```
Could not fetch "BTC". Either invalid symbol or API rate limited.
Wait 1-2 minutes and try again.
```

**What to do:**
1. Wait 1-2 minutes (seriously, don't retry immediately)
2. Try adding the pair again
3. If it still fails, wait 5 minutes

#### 🎯 Recommended First Pair

Try adding: **BTCUSDT**

This is the most reliable pair and is definitely available on CoinGecko.

### Common Issues

#### Issue: "Disconnected" keeps showing
**Cause:** The server crashed
**Fix:** Check the terminal for errors. If you see rate limit messages, wait 2 minutes and restart:
```bash
Ctrl+C  # Stop the server
python app.py  # Start again
```

#### Issue: Can't add any pairs
**Cause:** You hit the rate limit
**Fix:**
1. Stop the server (Ctrl+C)
2. Wait 5 minutes
3. Restart: `python app.py`
4. Add ONE pair at a time

#### Issue: App is slow
**Cause:** API delays (intentional to avoid rate limits)
**This is normal!** Each API call waits 2 seconds to respect rate limits.

### Rate Limit Details

CoinGecko's free tier allows:
- 10-50 calls per minute (exact limit varies)
- Adding one pair uses 2-3 API calls
- Monitoring updates all pairs every 15 seconds

**Tip:** For serious monitoring, consider:
1. Using fewer pairs (3-5 max for free tier)
2. Getting a CoinGecko API key (paid)
3. Using a different data source

### Still Having Issues?

Check the terminal output for detailed error messages. Look for:
- `⚠️ Rate limited by CoinGecko API` - Wait 1-2 minutes
- `Error fetching...` - Check your internet connection
- `Could not fetch price data` - The API is overloaded, try again later

### Debug Mode

If you need more detailed error information:

```bash
python app_debug.py
```

This shows emoji-marked messages:
- ✅ Success
- ❌ Errors
- 📥 Incoming requests
- 📤 Responses

---

**Pro Tip:** After adding your pairs, the app monitors them automatically every 15 seconds. You don't need to keep the browser open - just keep the terminal running!
