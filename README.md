# Crypto Price Alarm

> A reliable web application for tracking cryptocurrency trading pairs and receiving real-time alarm notifications when specific price events occur.

[![Build & Deploy](https://github.com/karmen87/Crypto_Alarm/actions/workflows/deploy.yml/badge.svg)](https://github.com/karmen87/Crypto_Alarm/actions/workflows/deploy.yml)
[![Documentation](https://img.shields.io/badge/docs-hugo-blue.svg)](https://karmen87.github.io/Crypto_Alarm/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📚 Documentation

**[📖 Read the Full Documentation →](https://karmen87.github.io/Crypto_Alarm/)**

Comprehensive technical documentation including:
- Detailed implementation guides for JavaScript and Python versions
- In-depth alarm logic explanations
- API integration specifics
- DevOps and CI/CD setup

---

## 🚀 Quick Start

### JavaScript App (Recommended - No Installation Required)

```bash
# Clone the repository
git clone https://github.com/karmen87/Crypto_Alarm.git

# Navigate to the JavaScript app
cd Crypto_Alarm/javascript-app

# Open in browser
open index.html  # macOS
# or just double-click index.html in Windows/Linux
```

**That's it!** No server, no dependencies, no configuration needed.

### Python App (Advanced Features)

```bash
# Navigate to Python app
cd Crypto_Alarm/python-app

# Follow setup instructions
See python-app/PYTHON_SETUP.md
```

---

## ✨ Features

### Core Capabilities
- 📊 **Multi-Pair Tracking** - Monitor multiple cryptocurrency trading pairs simultaneously
- ⏱️ **Real-Time Updates** - Price updates every 15 seconds via CoinGecko API
- 🔔 **Smart Alarms** - Three configurable alarm types for different trading strategies
- 💾 **Persistent Storage** - All settings saved automatically
- 🎨 **Clean Interface** - Minimal design focused on functionality

### Three Alarm Types

1. **🎯 Target Price** - Alert when price reaches a specific value
   - Configure direction: from above, below, or any direction

2. **📈 % Change from Max/Min** - Track percentage moves from extremes
   - Set alerts for pullbacks or breakouts

3. **⏰ % Move in Timeframe** - Monitor price action over time periods
   - Configure minutes, hours, days, or "since start"

### Supported Trading Pairs

Any pair with these quote currencies: **USDT**, **USDC**, **USD**, **BUSD**, **DAI**, **BTC**, **ETH**, **BNB**, **EUR**, **GBP**

**Examples**: `BTCUSDT`, `ETHBTC`, `BNBETH`, `SOLUSDC`

---

## 📂 Project Structure

```
Crypto_Alarm/
├── javascript-app/       # Standalone browser-based app (no server)
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── python-app/           # Flask + WebSocket server application
│   ├── app.py
│   ├── requirements.txt
│   └── templates/
├── docs/                 # Hugo documentation site
│   └── content/
└── .github/
    └── workflows/        # CI/CD automation
```

---

## 🎯 Use Cases

### Day Trading
- Set 3-5% quick movement alarms in 15-30 minute windows
- Monitor multiple pairs for volatility spikes

### Swing Trading
- Track % moves over hours/days
- Set target price alerts for key resistance levels

### Portfolio Monitoring
- Set "% down from max" stop-loss alerts
- Monitor long-term holdings for significant moves

---

## 🔧 Technical Stack

### JavaScript App
- Pure HTML/CSS/JavaScript (no frameworks)
- LocalStorage for persistence
- Web Audio API for alarms
- **No backend required**

### Python App
- Flask web framework
- Socket.IO for real-time updates
- JSON file storage
- Server-side monitoring

### Documentation Site
- Hugo static site generator
- Relearn theme
- Automated deployment via GitHub Actions

---

## ⚠️ Important Notes

### For JavaScript App Users
**Keep browser tab visible** - Browsers may suspend audio for inactive tabs. For reliable alarms:
- ✅ Keep the tab visible (not minimized)
- ✅ Use a dedicated browser window for monitoring
- ℹ️ Visual backup: Page title flashes "🚨 ALARM TRIGGERED! 🚨"

**Test first** - Click "🔔 Test Alarm" to verify sound works before setting critical alarms.

### Privacy
All data is stored locally in your browser (JavaScript) or on your server (Python). No information is sent anywhere except CoinGecko API requests for price data.

---

## 📖 Documentation & Resources

- **[Full Documentation](https://karmen87.github.io/Crypto_Alarm/)** - Complete technical guides
- **[JavaScript Implementation](https://karmen87.github.io/Crypto_Alarm/implementations/javascript-app/)** - Client-side app details
- **[Python Implementation](https://karmen87.github.io/Crypto_Alarm/implementations/python-app/)** - Server-side app details
- **[Alarm Logic Deep Dive](https://karmen87.github.io/Crypto_Alarm/alarm-logic/)** - How alarms work
- **[API Integration](https://karmen87.github.io/Crypto_Alarm/api-integration/)** - CoinGecko integration guide

---

## 🐛 Troubleshooting

**Common Issues:**

| Issue | Solution |
|-------|----------|
| Invalid pair format | Ensure pair ends with supported quote currency (USDT, BTC, ETH, etc.) |
| No alarm sound | Check browser audio permissions; keep tab visible (JS version) |
| Base asset not found | Verify token symbol exists on CoinGecko |
| Prices not updating | Check internet connection and browser console |

**[📋 Full Troubleshooting Guide →](https://karmen87.github.io/Crypto_Alarm/)**

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Karmen Kardum**
- GitHub: [@karmen87](https://github.com/karmen87)
- Portfolio: [karmen87.github.io](https://karmen87.github.io/)

---

## 🙏 Acknowledgments

- Powered by [CoinGecko API](https://www.coingecko.com/en/api) for cryptocurrency price data
- Documentation built with [Hugo](https://gohugo.io/) and the [Relearn theme](https://mcshelby.github.io/hugo-theme-relearn/)

---

**[📖 View Full Documentation](https://karmen87.github.io/Crypto_Alarm/)** | **[🐛 Report Issues](https://github.com/karmen87/Crypto_Alarm/issues)** | **[⭐ Star this repo](https://github.com/karmen87/Crypto_Alarm)**
