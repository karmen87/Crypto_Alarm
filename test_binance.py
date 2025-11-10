import requests

print("Testing Binance API...")
print("-" * 50)

try:
    # Test 1: Can we reach Binance?
    url = 'https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT'
    response = requests.get(url, timeout=5)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ SUCCESS!")
        print(f"Bitcoin Price: ${float(data['lastPrice']):,.2f}")
        print(f"24h Change: {float(data['priceChangePercent']):.2f}%")
    else:
        print(f"❌ Error: {response.text}")
        
except Exception as e:
    print(f"❌ Failed: {e}")

print("-" * 50)