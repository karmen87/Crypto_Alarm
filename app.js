// ========================================
// Crypto Price Alarm Application
// ========================================

class CryptoPriceAlarm {
    constructor() {
        this.assets = new Map(); // Map of ticker -> asset data
        this.priceHistory = new Map(); // Map of ticker -> price history array
        this.alarms = new Map(); // Map of alarmId -> alarm config
        this.activeAlarm = null;
        this.audioContext = null;
        this.alarmOscillator = null;
        this.alarmGain = null;
        this.alarmPulseInterval = null;
        this.titleFlashInterval = null;
        this.updateInterval = null;
        this.currentView = 'assets'; // 'assets' or 'alarms'
        this.selectedAsset = null;
        this.originalTitle = document.title;

    // Reset cooldown intervals for target alarms: alarmId -> intervalId
    this.resetIntervals = new Map();
            // Modal stack for multiple triggered alarms (top is last)
            this.modalStack = [];
            // Flag to avoid creating multiple oscillators
            this.alarmSoundPlaying = false;
        // Rate limiting for API calls
        this.lastApiCall = 0;
        this.minApiDelay = 1200; // Minimum 1.2 seconds between API calls (50 calls/minute max)
        this.apiQueue = [];
        this.isProcessingQueue = false;

        this.init();
    }

    async init() {
        this.loadFromStorage();
        // Restore any pending reset timers from storage
        this.rehydrateResetTimers();
        this.setupEventListeners();
        this.setupAudioContext();
        this.updateStatus('Initializing...');

        if (this.assets.size > 0) {
            await this.updateAllPrices();
            this.renderAssets();
        }

        this.startMonitoring();
        this.updateStatus('Monitoring active', 'active');
    }

    // ========================================
    // Storage Management
    // ========================================

    loadFromStorage() {
        try {
            const savedAssets = localStorage.getItem('cryptoAlarmAssets');
            const savedAlarms = localStorage.getItem('cryptoAlarmAlarms');
            const savedHistory = localStorage.getItem('cryptoAlarmHistory');

            if (savedAssets) {
                const assetsArray = JSON.parse(savedAssets);
                assetsArray.forEach(asset => {
                    this.assets.set(asset.ticker, asset);
                });
            }

            if (savedAlarms) {
                const alarmsArray = JSON.parse(savedAlarms);
                alarmsArray.forEach(alarm => {
                    this.alarms.set(alarm.id, alarm);
                });
            }

            if (savedHistory) {
                const historyObj = JSON.parse(savedHistory);
                Object.keys(historyObj).forEach(ticker => {
                    this.priceHistory.set(ticker, historyObj[ticker]);
                });
            }
        } catch (error) {
            console.error('Error loading from storage:', error);
        }
    }

    saveToStorage() {
        try {
            const assetsArray = Array.from(this.assets.values());
            const alarmsArray = Array.from(this.alarms.values());
            const historyObj = {};
            this.priceHistory.forEach((value, key) => {
                historyObj[key] = value;
            });

            localStorage.setItem('cryptoAlarmAssets', JSON.stringify(assetsArray));
            localStorage.setItem('cryptoAlarmAlarms', JSON.stringify(alarmsArray));
            localStorage.setItem('cryptoAlarmHistory', JSON.stringify(historyObj));
        } catch (error) {
            console.error('Error saving to storage:', error);
        }
    }

    // ========================================
    // API Integration
    // ========================================

    parseTradingPair(pairString) {
        // Common quote currencies
        const quotes = ['USDT', 'USDC', 'USD', 'BUSD', 'DAI', 'BTC', 'ETH', 'BNB', 'EUR', 'GBP'];

        pairString = pairString.toUpperCase().trim();

        // Try to find a quote currency in the pair
        for (const quote of quotes) {
            if (pairString.endsWith(quote) && pairString.length > quote.length) {
                const base = pairString.substring(0, pairString.length - quote.length);
                return { base, quote, pair: pairString };
            }
        }

        return null;
    }

    // Rate limiting helper
    async waitForRateLimit() {
        const now = Date.now();
        const timeSinceLastCall = now - this.lastApiCall;

        if (timeSinceLastCall < this.minApiDelay) {
            const waitTime = this.minApiDelay - timeSinceLastCall;
            await new Promise(resolve => setTimeout(resolve, waitTime));
        }

        this.lastApiCall = Date.now();
    }

    async fetchCoinId(ticker) {
        await this.waitForRateLimit();
        try {
            const response = await fetch('https://api.coingecko.com/api/v3/search?query=' + ticker);

            if (response.status === 429) {
                console.warn('Rate limited by CoinGecko API. Waiting 60 seconds...');
                await new Promise(resolve => setTimeout(resolve, 60000));
                return this.fetchCoinId(ticker); // Retry after wait
            }

            const data = await response.json();

            const coin = data.coins.find(c =>
                c.symbol.toLowerCase() === ticker.toLowerCase()
            );

            return coin ? { id: coin.id, name: coin.name, symbol: coin.symbol } : null;
        } catch (error) {
            console.error('Error fetching coin ID:', error);
            return null;
        }
    }

    async fetchPrice(coinId) {
        await this.waitForRateLimit();
        try {
            const response = await fetch(
                `https://api.coingecko.com/api/v3/simple/price?ids=${coinId}&vs_currencies=usd&include_24hr_change=true`
            );

            if (response.status === 429) {
                console.warn('Rate limited by CoinGecko API. Waiting 60 seconds...');
                await new Promise(resolve => setTimeout(resolve, 60000));
                return this.fetchPrice(coinId); // Retry after wait
            }

            const data = await response.json();

            if (data[coinId]) {
                return {
                    price: data[coinId].usd,
                    change24h: data[coinId].usd_24h_change || 0
                };
            }
            return null;
        } catch (error) {
            console.error('Error fetching price:', error);
            return null;
        }
    }

    async fetchPairPrice(baseCoinId, quoteCoinId) {
        await this.waitForRateLimit();
        try {
            // Fetch both prices in USD
            const response = await fetch(
                `https://api.coingecko.com/api/v3/simple/price?ids=${baseCoinId},${quoteCoinId}&vs_currencies=usd&include_24hr_change=true`
            );

            if (response.status === 429) {
                console.warn('Rate limited by CoinGecko API. Waiting 60 seconds...');
                await new Promise(resolve => setTimeout(resolve, 60000));
                return this.fetchPairPrice(baseCoinId, quoteCoinId); // Retry after wait
            }

            const data = await response.json();

            if (data[baseCoinId] && data[quoteCoinId]) {
                const basePrice = data[baseCoinId].usd;
                const quotePrice = data[quoteCoinId].usd;
                const pairPrice = basePrice / quotePrice;

                // Calculate 24h change for the pair
                const baseChange = data[baseCoinId].usd_24h_change || 0;
                const quoteChange = data[quoteCoinId].usd_24h_change || 0;
                const pairChange = baseChange - quoteChange;

                return {
                    price: pairPrice,
                    change24h: pairChange
                };
            }
            return null;
        } catch (error) {
            console.error('Error fetching pair price:', error);
            return null;
        }
    }

    isStablecoin(symbol) {
        const stablecoins = ['USDT', 'USDC', 'USD', 'BUSD', 'DAI', 'TUSD', 'USDD', 'USDP'];
        return stablecoins.includes(symbol.toUpperCase());
    }

    // ========================================
    // Asset Management
    // ========================================

    async addAsset(pairInput) {
        pairInput = pairInput.trim().toUpperCase();

        if (!pairInput) {
            this.showError('Please enter a trading pair');
            return;
        }

        if (this.assets.has(pairInput)) {
            this.showError('Pair already added');
            return;
        }

        this.updateStatus('Fetching pair info...');

        // Parse the trading pair
        const parsed = this.parseTradingPair(pairInput);

        if (!parsed) {
            this.showError('Invalid pair format. Try: BTCUSDT, ETHBTC, etc.');
            this.updateStatus('Monitoring active', 'active');
            return;
        }

        const { base, quote, pair } = parsed;

        // Fetch base asset info
        const baseCoinInfo = await this.fetchCoinId(base);
        if (!baseCoinInfo) {
            this.showError(`Base asset "${base}" not found. Check the symbol.`);
            this.updateStatus('Monitoring active', 'active');
            return;
        }

        // Handle quote asset
        let quoteCoinInfo = null;
        let priceData = null;

        if (this.isStablecoin(quote)) {
            // For stablecoins, just use base price in USD
            priceData = await this.fetchPrice(baseCoinInfo.id);
            if (!priceData) {
                this.showError('Could not fetch price data');
                this.updateStatus('Monitoring active', 'active');
                return;
            }
        } else {
            // For non-stablecoin pairs, fetch both assets
            quoteCoinInfo = await this.fetchCoinId(quote);
            if (!quoteCoinInfo) {
                this.showError(`Quote asset "${quote}" not found. Check the symbol.`);
                this.updateStatus('Monitoring active', 'active');
                return;
            }

            priceData = await this.fetchPairPrice(baseCoinInfo.id, quoteCoinInfo.id);
            if (!priceData) {
                this.showError('Could not fetch pair price data');
                this.updateStatus('Monitoring active', 'active');
                return;
            }
        }

        const asset = {
            ticker: pair,
            isPair: true,
            base: base,
            quote: quote,
            baseCoinId: baseCoinInfo.id,
            quoteCoinId: quoteCoinInfo ? quoteCoinInfo.id : null,
            name: `${baseCoinInfo.name}/${quote}`,
            baseName: baseCoinInfo.name,
            price: priceData.price,
            change24h: priceData.change24h,
            maxPrice: priceData.price,
            minPrice: priceData.price,
            lastUpdate: Date.now()
        };

        this.assets.set(pair, asset);
        this.priceHistory.set(pair, [{ price: priceData.price, timestamp: Date.now() }]);
        this.saveToStorage();
        this.renderAssets();
        this.clearError();
        this.updateStatus('Monitoring active', 'active');

        document.getElementById('assetTicker').value = '';
    }

    removeAsset(ticker) {
        this.assets.delete(ticker);
        this.priceHistory.delete(ticker);

        // Remove associated alarms
        const alarmsToRemove = [];
        this.alarms.forEach((alarm, id) => {
            if (alarm.ticker === ticker) {
                alarmsToRemove.push(id);
            }
        });
        alarmsToRemove.forEach(id => this.alarms.delete(id));

        this.saveToStorage();
        this.renderAssets();
    }

    async updateAllPrices() {
        const updatePromises = Array.from(this.assets.values()).map(async (asset) => {
            let priceData = null;

            if (asset.isPair) {
                // Handle trading pair
                if (this.isStablecoin(asset.quote)) {
                    // For stablecoin pairs, just fetch base price in USD
                    priceData = await this.fetchPrice(asset.baseCoinId);
                } else {
                    // For non-stablecoin pairs, fetch both and calculate ratio
                    priceData = await this.fetchPairPrice(asset.baseCoinId, asset.quoteCoinId);
                }
            } else {
                // Legacy support for single assets (if any exist)
                priceData = await this.fetchPrice(asset.coinId || asset.baseCoinId);
            }

            if (priceData) {
                const oldPrice = asset.price;
                asset.price = priceData.price;
                asset.change24h = priceData.change24h;
                asset.lastUpdate = Date.now();

                // Update max/min tracking
                if (priceData.price > asset.maxPrice) {
                    asset.maxPrice = priceData.price;
                }
                if (priceData.price < asset.minPrice) {
                    asset.minPrice = priceData.price;
                }

                // Update price history
                const history = this.priceHistory.get(asset.ticker) || [];
                history.push({ price: priceData.price, timestamp: Date.now() });

                // Keep only last 24 hours of data
                const oneDayAgo = Date.now() - (24 * 60 * 60 * 1000);
                const filteredHistory = history.filter(h => h.timestamp > oneDayAgo);
                this.priceHistory.set(asset.ticker, filteredHistory);

                this.assets.set(asset.ticker, asset);
            }
        });

        await Promise.all(updatePromises);
        this.saveToStorage();
    }

    // ========================================
    // Alarm Management
    // ========================================

    addTargetPriceAlarm(ticker, targetPrice, direction) {
        const alarm = {
            id: this.generateAlarmId(),
            ticker: ticker,
            type: 'target',
            targetPrice: parseFloat(targetPrice),
            direction: direction,
            triggered: false,
            createdAt: Date.now()
        };

        this.alarms.set(alarm.id, alarm);
        this.saveToStorage();
        this.renderAlarms();
    }

    addExtremeAlarm(ticker, percentage, extremeType) {
        const alarm = {
            id: this.generateAlarmId(),
            ticker: ticker,
            type: 'extreme',
            percentage: parseFloat(percentage),
            extremeType: extremeType,
            triggered: false,
            createdAt: Date.now()
        };

        this.alarms.set(alarm.id, alarm);
        this.saveToStorage();
        this.renderAlarms();
    }

    addTimeframeAlarm(ticker, percentage, direction, timeValue, timeUnit) {
        const alarm = {
            id: this.generateAlarmId(),
            ticker: ticker,
            type: 'timeframe',
            percentage: parseFloat(percentage),
            direction: direction,
            timeValue: timeUnit === 'since_start' ? null : parseInt(timeValue),
            timeUnit: timeUnit,
            triggered: false,
            createdAt: Date.now(),
            lastResetTime: Date.now() // For 'since_start' alarms
        };

        this.alarms.set(alarm.id, alarm);
        this.saveToStorage();
        this.renderAlarms();
    }

    removeAlarm(alarmId) {
        this.alarms.delete(alarmId);
        this.saveToStorage();
        this.renderAlarms();
        // Also clear any reset cooldown interval
        this.clearResetCooldown(alarmId);
        // If All Active Alarms tab is visible, refresh it as well
        const allAlarmsTabBtn = document.querySelector('.tab-button[data-tab="all-alarms"]');
        if (allAlarmsTabBtn && allAlarmsTabBtn.classList.contains('active')) {
            this.renderAllActiveAlarms();
        }
    }

    generateAlarmId() {
        return 'alarm_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    getAlarmDescription(alarm) {
        const asset = this.assets.get(alarm.ticker);

        switch (alarm.type) {
            case 'target':
                const directionText = alarm.direction === 'up' ? ' (from below)' :
                                     alarm.direction === 'down' ? ' (from above)' : '';
                const priceDisplay = asset && asset.isPair ?
                    this.formatPairPrice(alarm.targetPrice, asset.quote) :
                    `$${alarm.targetPrice.toFixed(2)}`;
                return `Target price: ${priceDisplay}${directionText}`;

            case 'extreme':
                return `${alarm.percentage}% ${alarm.extremeType === 'max' ? 'down from max' : 'up from min'} price`;

            case 'timeframe':
                const moveDir = alarm.direction === 'up' ? 'up' :
                               alarm.direction === 'down' ? 'down' : 'change';

                // Handle legacy alarms that still use timeframeMinutes
                if (alarm.timeframeMinutes !== undefined) {
                    return `${alarm.percentage}% ${moveDir} in ${alarm.timeframeMinutes} minutes`;
                }

                if (alarm.timeUnit === 'since_start') {
                    return `${alarm.percentage}% ${moveDir} since start (resets on trigger)`;
                } else {
                    return `${alarm.percentage}% ${moveDir} in ${alarm.timeValue} ${alarm.timeUnit}`;
                }

            default:
                return 'Unknown alarm type';
        }
    }

    // ========================================
    // Alarm Detection & Monitoring
    // ========================================

    checkAlarms() {
        this.alarms.forEach((alarm, alarmId) => {
            if (alarm.triggered) return;

            const asset = this.assets.get(alarm.ticker);
            if (!asset) return;

            let shouldTrigger = false;
            let message = '';
            let direction = null; // 'up' or 'down'

            switch (alarm.type) {
                case 'target':
                    // Diagnostic logging to help trace target alarm evaluation
                    try {
                        const history = this.priceHistory.get(asset.ticker) || [];
                        const prevPrice = history.length >= 2 ? history[history.length - 2].price : null;
                        console.debug(`Checking target alarm ${alarmId} for ${alarm.ticker}: prev=${prevPrice}, curr=${asset.price}, target=${alarm.targetPrice}`);
                    } catch (e) { /* ignore logging errors */ }
                    shouldTrigger = this.checkTargetAlarm(alarm, asset);
                    if (shouldTrigger) {
                        const targetDisplay = asset.isPair ? this.formatPairPrice(alarm.targetPrice, asset.quote) : `$${alarm.targetPrice.toFixed(2)}`;
                        const currentDisplay = asset.isPair ? this.formatPairPrice(asset.price, asset.quote) : `$${asset.price.toFixed(2)}`;
                        message = `${asset.name} (${asset.ticker}) reached target price of ${targetDisplay}!\nCurrent price: ${currentDisplay}`;

                        // Determine direction based on alarm direction setting
                        if (alarm.direction === 'up' || asset.price >= alarm.targetPrice) {
                            direction = 'up';
                        } else {
                            direction = 'down';
                        }
                    }
                    break;

                case 'extreme':
                    shouldTrigger = this.checkExtremeAlarm(alarm, asset);
                    if (shouldTrigger) {
                        const extremePrice = alarm.extremeType === 'max' ? asset.maxPrice : asset.minPrice;
                        const extremeDisplay = asset.isPair ? this.formatPairPrice(extremePrice, asset.quote) : `$${extremePrice.toFixed(2)}`;
                        const currentDisplay = asset.isPair ? this.formatPairPrice(asset.price, asset.quote) : `$${asset.price.toFixed(2)}`;
                        message = `${asset.name} (${asset.ticker}) moved ${alarm.percentage}% ${alarm.extremeType === 'max' ? 'down from max' : 'up from min'}!\n` +
                                `${alarm.extremeType === 'max' ? 'Max' : 'Min'} price: ${extremeDisplay}\nCurrent price: ${currentDisplay}`;

                        // Max = price went down, Min = price went up
                        direction = alarm.extremeType === 'max' ? 'down' : 'up';
                    }
                    break;

                case 'timeframe':
                    const priceMovement = this.checkTimeframeAlarm(alarm, asset);
                    shouldTrigger = priceMovement !== null;

                    if (shouldTrigger) {
                        const currentDisplay = asset.isPair ? this.formatPairPrice(asset.price, asset.quote) : `$${asset.price.toFixed(2)}`;

                        // Build time description
                        let timeDesc;
                        if (alarm.timeframeMinutes !== undefined) {
                            // Legacy alarm
                            timeDesc = `${alarm.timeframeMinutes} minutes`;
                        } else if (alarm.timeUnit === 'since_start') {
                            timeDesc = 'since start';
                        } else {
                            timeDesc = `${alarm.timeValue} ${alarm.timeUnit}`;
                        }

                        message = `${asset.name} (${asset.ticker}) moved ${alarm.percentage}% in ${timeDesc}!\nCurrent price: ${currentDisplay}`;

                        // Use the actual price movement direction
                        direction = priceMovement > 0 ? 'up' : 'down';
                    }
                    break;
            }

            if (shouldTrigger) {
                // For "since_start" alarms, reset instead of marking as permanently triggered
                if (alarm.type === 'timeframe' && alarm.timeUnit === 'since_start') {
                    alarm.lastResetTime = Date.now();
                    this.saveToStorage();
                    this.triggerAlarm(alarm, message, direction);
                } else {
                    alarm.triggered = true;
                    alarm.triggeredAt = Date.now();
                    this.saveToStorage();
                    this.triggerAlarm(alarm, message, direction);
                }
            }
        });
    }

    checkTargetAlarm(alarm, asset) {
        const currentPrice = asset.price;
        const targetPrice = alarm.targetPrice;

        // Small tolerance for floating point comparisons
        const eps = Math.max(1e-8, Math.abs(targetPrice) * 1e-6);

        // Get previous price from history
        const history = this.priceHistory.get(asset.ticker) || [];

        // If we don't have a previous price, fall back to direct comparison with tolerance.
        // This handles the common case where the app was just started or the pair was just added.
        if (history.length < 2) {
            if (alarm.direction === 'up') {
                return currentPrice + eps >= targetPrice;
            } else if (alarm.direction === 'down') {
                return currentPrice - eps <= targetPrice;
            } else {
                // 'any' direction: trigger only when current price is very close to target
                return Math.abs(currentPrice - targetPrice) <= eps;
            }
        }

        const previousPrice = history[history.length - 2].price;

        if (alarm.direction === 'up') {
            return previousPrice < targetPrice && currentPrice + eps >= targetPrice;
        } else if (alarm.direction === 'down') {
            return previousPrice > targetPrice && currentPrice - eps <= targetPrice;
        } else {
            return (previousPrice < targetPrice && currentPrice + eps >= targetPrice) ||
                   (previousPrice > targetPrice && currentPrice - eps <= targetPrice);
        }
    }

    checkExtremeAlarm(alarm, asset) {
        const currentPrice = asset.price;

        if (alarm.extremeType === 'max') {
            const maxPrice = asset.maxPrice;
            const percentDown = ((maxPrice - currentPrice) / maxPrice) * 100;
            return percentDown >= alarm.percentage;
        } else {
            const minPrice = asset.minPrice;
            const percentUp = ((currentPrice - minPrice) / minPrice) * 100;
            return percentUp >= alarm.percentage;
        }
    }

    getTimeframeMs(alarm) {
        // Handle legacy alarms
        if (alarm.timeframeMinutes !== undefined) {
            return alarm.timeframeMinutes * 60 * 1000;
        }

        if (alarm.timeUnit === 'since_start') {
            return null; // Special case
        }

        const value = alarm.timeValue;
        switch (alarm.timeUnit) {
            case 'minutes':
                return value * 60 * 1000;
            case 'hours':
                return value * 60 * 60 * 1000;
            case 'days':
                return value * 24 * 60 * 60 * 1000;
            default:
                return value * 60 * 1000; // Default to minutes
        }
    }

    checkTimeframeAlarm(alarm, asset) {
        const history = this.priceHistory.get(asset.ticker) || [];
        if (history.length < 2) return null;

        const currentTime = Date.now();
        let startTime;

        if (alarm.timeUnit === 'since_start') {
            // Use lastResetTime or createdAt as the start time
            startTime = alarm.lastResetTime || alarm.createdAt;
        } else {
            const timeframeMs = this.getTimeframeMs(alarm);
            startTime = currentTime - timeframeMs;
        }

        // Find price at start of timeframe
        const relevantHistory = history.filter(h => h.timestamp >= startTime);
        if (relevantHistory.length === 0) return null;

        const startPrice = relevantHistory[0].price;
        const currentPrice = asset.price;
        const percentChange = ((currentPrice - startPrice) / startPrice) * 100;

        let triggered = false;
        if (alarm.direction === 'up') {
            triggered = percentChange >= alarm.percentage;
        } else if (alarm.direction === 'down') {
            triggered = percentChange <= -alarm.percentage;
        } else {
            triggered = Math.abs(percentChange) >= alarm.percentage;
        }

        // Return the percent change if triggered, null otherwise
        return triggered ? percentChange : null;
    }

    startMonitoring() {
        // Update prices every 15 seconds
        this.updateInterval = setInterval(async () => {
            await this.updateAllPrices();
            this.checkAlarms();
            this.renderAssets();
            if (this.currentView === 'alarms' && this.selectedAsset) {
                this.renderAlarms();
            }
        }, 15000);
    }

    stopMonitoring() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
    }

    // ========================================
    // Audio/Alarm System
    // ========================================

    setupAudioContext() {
        // Create audio context on first user interaction
        document.addEventListener('click', () => {
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
        }, { once: true });
    }

    triggerAlarm(alarm, message, direction) {
        // Push the alarm onto the modal stack and render a modal for it.
        try {
            this.modalStack.push({ alarm, message, direction });

            // Keep activeAlarm set so audio loop sees that an alarm is active
            this.activeAlarm = { alarm, message, direction };

            // Create and show a modal instance for this alarm on top of any others
            const modalEl = this._createAlarmModalElement(alarm, message, direction);
            document.body.appendChild(modalEl);

            // Start sound/flash if not already active
            if (!this.alarmSoundPlaying) {
                this.playAlarmSound();
                this.flashPageTitle();
            }
        } catch (e) {
            console.error('Error while stacking alarm modal:', e);
            // Fallback to original behavior
            this.activeAlarm = { alarm, message, direction };
            this.showAlarmModal(message, direction);
            this.playAlarmSound();
            this.flashPageTitle();
        }
    }

    // Create a DOM modal element for a triggered alarm. Each modal is independent and stacked.
    _createAlarmModalElement(alarm, message, direction) {
        const wrapper = document.createElement('div');
        wrapper.className = 'modal alarm-modal-instance active';
        // ensure increasing z-index and offset for stacking
        const stackIndex = this.modalStack.length - 1;
        wrapper.style.setProperty('--stack-index', stackIndex);
        wrapper.style.zIndex = 1000 + stackIndex;

        const content = document.createElement('div');
        content.className = 'modal-content';

        // Alarm icon and direction
        const icon = document.createElement('div');
        icon.className = 'alarm-icon';
        icon.textContent = '⚠️';

        const directionEl = document.createElement('div');
        directionEl.className = 'alarm-direction';
        if (direction === 'up') {
            directionEl.classList.add('up');
            directionEl.textContent = '↑';
        } else if (direction === 'down') {
            directionEl.classList.add('down');
            directionEl.textContent = '↓';
        }

        const title = document.createElement('h2');
        title.textContent = 'PRICE ALARM!';

        const messageEl = document.createElement('div');
        messageEl.innerHTML = message.replace(/\n/g, '<br>');

        // Buttons container
        const btnContainer = document.createElement('div');
        btnContainer.style.marginTop = '16px';

        const dismissBtn = document.createElement('button');
        dismissBtn.className = 'btn-dismiss';
        dismissBtn.textContent = 'DISMISS ALARM';
        dismissBtn.addEventListener('click', () => {
            // Remove this modal and advance stack
            this._removeModalInstance(wrapper, alarm.id);
        });

        btnContainer.appendChild(dismissBtn);

        // If alarm is a target type, add Restart button next to Dismiss
        if (alarm && alarm.type === 'target') {
            const restartBtn = document.createElement('button');
            restartBtn.className = 'btn-dismiss';
            restartBtn.style.marginLeft = '12px';
            restartBtn.textContent = 'RESTART (60s)';
            restartBtn.addEventListener('click', () => {
                this.startResetCooldown(alarm.id);
                // remove this modal instance
                this._removeModalInstance(wrapper, alarm.id);
            });
            btnContainer.appendChild(restartBtn);
        }

        content.appendChild(icon);
        content.appendChild(directionEl);
        content.appendChild(title);
        content.appendChild(messageEl);
        content.appendChild(btnContainer);

        wrapper.appendChild(content);

        return wrapper;
    }

    // Remove a specific modal instance element from DOM and advance the stack
    _removeModalInstance(modalEl, alarmId) {
        try {
            // Add closing animation
            modalEl.classList.add('closing');
            modalEl.addEventListener('animationend', () => {
                // remove from DOM after animation
                if (modalEl && modalEl.parentNode) modalEl.parentNode.removeChild(modalEl);
            });

            // remove corresponding entry from modalStack (match by alarm id)
            for (let i = this.modalStack.length - 1; i >= 0; i--) {
                if (this.modalStack[i].alarm && this.modalStack[i].alarm.id === alarmId) {
                    this.modalStack.splice(i, 1);
                    break;
                }
            }

            // Update z-indices and offsets for remaining modals
            this.modalStack.forEach((_, index) => {
                const remainingModals = document.querySelectorAll('.alarm-modal-instance:not(.closing)');
                remainingModals[index]?.style.setProperty('--stack-index', index);
                remainingModals[index]?.style.setProperty('z-index', 1000 + index);
            });

            // If no more modals, stop sound/flash
            if (this.modalStack.length === 0) {
                this.stopAlarmSound();
                this.stopTitleFlash();
                this.alarmSoundPlaying = false;
                // Clear activeAlarm so other audio loops respect that nothing is active
                this.activeAlarm = null;
            }
        } catch (e) {
            console.error('Error removing modal instance:', e);
        }
    }

    flashPageTitle() {
        // Flash the page title to alert user even if they can't hear the sound
        let isAlertShowing = true;

        this.titleFlashInterval = setInterval(() => {
            if (isAlertShowing) {
                document.title = '🚨 ALARM TRIGGERED! 🚨';
            } else {
                document.title = '⚠️ PRICE ALARM ⚠️';
            }
            isAlertShowing = !isAlertShowing;
        }, 1000);
    }

    stopTitleFlash() {
        if (this.titleFlashInterval) {
            clearInterval(this.titleFlashInterval);
            this.titleFlashInterval = null;
            document.title = this.originalTitle;
        }
    }

    async playAlarmSound() {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }

        // mark that the alarm sound is playing (prevents duplicate creation)
        this.alarmSoundPlaying = true;

        // Resume audio context in case it was suspended (important for background tabs)
        if (this.audioContext.state === 'suspended') {
            console.warn('Audio context was suspended - resuming now. This can happen when tab is inactive.');
            await this.audioContext.resume();
        }

        console.log('Playing alarm sound at volume 0.6 with continuous monitoring for suspension.');

        // Create oscillator for alarm sound
        this.alarmOscillator = this.audioContext.createOscillator();
        this.alarmGain = this.audioContext.createGain();

        this.alarmOscillator.connect(this.alarmGain);
        this.alarmGain.connect(this.audioContext.destination);

        // Create a pulsing alarm sound - use sawtooth for more piercing sound
        this.alarmOscillator.type = 'sawtooth';
        this.alarmOscillator.frequency.value = 880; // A5 note - attention-grabbing

        // Set initial gain to loud
        this.alarmGain.gain.value = 0.6;

        // Start the oscillator (no stop time = plays indefinitely)
        this.alarmOscillator.start();

        // Create continuous pulsing pattern using setInterval
        const pulseDuration = 150; // milliseconds - faster pulsing
        let pulseCount = 0;

        this.alarmPulseInterval = setInterval(async () => {
            if (!this.activeAlarm) {
                // Safety check - stop if alarm was dismissed
                this.stopAlarmSound();
                return;
            }

            // Resume audio context if it got suspended (critical for inactive tabs)
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }

            // Alternate between loud and silent to create beeping effect
            // Use direct value assignment instead of scheduling
            if (pulseCount % 2 === 0) {
                // LOUD beep
                this.alarmGain.gain.value = 0.6;
                this.alarmOscillator.frequency.value = 880;
            } else {
                // Silent gap
                this.alarmGain.gain.value = 0;
            }

            pulseCount++;
        }, pulseDuration);
    }

    stopAlarmSound() {
        // Clear the pulse interval
        if (this.alarmPulseInterval) {
            clearInterval(this.alarmPulseInterval);
            this.alarmPulseInterval = null;
        }

        // Stop and disconnect the oscillator
        if (this.alarmOscillator) {
            try {
                this.alarmOscillator.stop();
            } catch (e) {
                // Oscillator may already be stopped
            }
            this.alarmOscillator.disconnect();
            this.alarmOscillator = null;
        }

        // Disconnect the gain node
        if (this.alarmGain) {
            this.alarmGain.disconnect();
            this.alarmGain = null;
        }

        // mark that alarm sound is no longer playing
        this.alarmSoundPlaying = false;
    }

    dismissAlarm() {
        // Clear any stacked modals
        const modalInstances = document.querySelectorAll('.alarm-modal-instance');
        modalInstances.forEach(modal => {
            if (modal.parentNode) modal.parentNode.removeChild(modal);
        });
        this.modalStack = [];

        // Stop audio and clear state
        this.stopAlarmSound();
        this.stopTitleFlash();
        this.hideAlarmModal();
        this.activeAlarm = null;
        this.alarmSoundPlaying = false;
    }

    // Start a 60-second reset cooldown for a target alarm so it can trigger again later
    startResetCooldown(alarmId) {
        const alarm = this.alarms.get(alarmId);
        if (!alarm) return;

        // Only applicable to target alarms
        if (alarm.type !== 'target') return;

        // Clear any existing interval for this alarm
        this.clearResetCooldown(alarmId);

        alarm.resetUntil = Date.now() + 60 * 1000; // 60 seconds
        alarm.resetting = true;
        this.alarms.set(alarmId, alarm);
        this.saveToStorage();

        // Start per-second interval to update UI and finalize when done
        const intervalId = setInterval(() => {
            const now = Date.now();
            if (alarm.resetUntil && alarm.resetUntil > now) {
                // update UI periodically
                this.renderAlarms();
                this.renderAllActiveAlarms();
            } else {
                // cooldown finished: clear and reset alarm state
                this.clearResetCooldown(alarmId);
                const storedAlarm = this.alarms.get(alarmId);
                if (storedAlarm) {
                    storedAlarm.resetUntil = null;
                    storedAlarm.resetting = false;
                    storedAlarm.triggered = false; // allow it to trigger again
                    this.alarms.set(alarmId, storedAlarm);
                    this.saveToStorage();
                    this.renderAlarms();
                    this.renderAllActiveAlarms();
                }
            }
        }, 1000);

        this.resetIntervals.set(alarmId, intervalId);
        // initial UI update
        this.renderAlarms();
        this.renderAllActiveAlarms();
    }

    clearResetCooldown(alarmId) {
        const iv = this.resetIntervals.get(alarmId);
        if (iv) {
            clearInterval(iv);
            this.resetIntervals.delete(alarmId);
        }
    }

    // Rehydrate any reset timers found in saved alarms on init
    rehydrateResetTimers() {
        const now = Date.now();
        this.alarms.forEach((alarm, id) => {
            if (alarm.resetUntil && alarm.resetUntil > now) {
                // Start an interval that respects the stored resetUntil without changing it
                const remaining = alarm.resetUntil - now;
                // create interval that checks every second and finalizes when time is up
                const intervalId = setInterval(() => {
                    const now2 = Date.now();
                    if (alarm.resetUntil && alarm.resetUntil > now2) {
                        // update UI periodically
                        this.renderAlarms();
                        this.renderAllActiveAlarms();
                    } else {
                        clearInterval(intervalId);
                        // finalize alarm state
                        const storedAlarm = this.alarms.get(id);
                        if (storedAlarm) {
                            storedAlarm.resetUntil = null;
                            storedAlarm.resetting = false;
                            storedAlarm.triggered = false;
                            this.alarms.set(id, storedAlarm);
                            this.saveToStorage();
                            this.renderAlarms();
                            this.renderAllActiveAlarms();
                        }
                    }
                }, 1000);
                this.resetIntervals.set(id, intervalId);
            } else if (alarm.resetUntil && alarm.resetUntil <= now) {
                // expired — clear fields
                alarm.resetUntil = null;
                alarm.resetting = false;
                alarm.triggered = false;
                this.alarms.set(id, alarm);
            }
        });
        this.saveToStorage();
    }

    triggerTestAlarm() {
        const message = `This is a test alarm!\n\nYou can adjust your system volume and verify the alarm sound is working correctly.\n\nClick "DISMISS ALARM" to stop the sound.`;

        // Create a temporary test alarm object
        const testAlarm = {
            type: 'test',
            ticker: 'TEST'
        };

        this.activeAlarm = { alarm: testAlarm, message, direction: null };
        this.showAlarmModal(message, null);
        this.playAlarmSound();
    }

    // ========================================
    // UI Rendering
    // ========================================

    formatPairPrice(price, quote) {
        // Format price based on quote currency and magnitude
        if (this.isStablecoin(quote)) {
            // For stablecoin pairs, use $ and appropriate decimals
            if (price >= 1000) return `$${price.toFixed(2)}`;
            if (price >= 1) return `$${price.toFixed(4)}`;
            if (price >= 0.01) return `$${price.toFixed(6)}`;
            return `$${price.toFixed(8)}`;
        } else {
            // For non-stablecoin pairs, don't use $
            if (price >= 1) return price.toFixed(6);
            if (price >= 0.0001) return price.toFixed(8);
            return price.toFixed(10);
        }
    }

    renderAssets() {
        const assetsList = document.getElementById('assetsList');

        if (this.assets.size === 0) {
            assetsList.innerHTML = '<p class="placeholder">No pairs added yet</p>';
            return;
        }

        // Update the All Active Alarms tab if it's visible
        const allAlarmsTabBtn = document.querySelector('.tab-button[data-tab="all-alarms"]');
        if (allAlarmsTabBtn && allAlarmsTabBtn.classList.contains('active')) {
            this.renderAllActiveAlarms();
        }

        assetsList.innerHTML = '';

        this.assets.forEach((asset, ticker) => {
            const assetItem = document.createElement('div');
            assetItem.className = 'asset-item';

            const changeClass = asset.change24h >= 0 ? 'positive' : 'negative';
            const changeSymbol = asset.change24h >= 0 ? '+' : '';

            // Count alarms for this asset
            let alarmCount = 0;
            this.alarms.forEach(alarm => {
                if (alarm.ticker === ticker) alarmCount++;
            });

            // Format price display
            const priceDisplay = asset.isPair ?
                this.formatPairPrice(asset.price, asset.quote) :
                `$${asset.price.toFixed(2)}`;

            assetItem.innerHTML = `
                <div class="asset-info">
                    <div class="asset-name">${asset.name}</div>
                    <div class="asset-ticker">${asset.ticker} • ${alarmCount} alarm${alarmCount !== 1 ? 's' : ''}</div>
                </div>
                <div class="asset-price">
                    <div class="price-value">${priceDisplay}</div>
                    <div class="price-change ${changeClass}">${changeSymbol}${asset.change24h.toFixed(2)}%</div>
                </div>
                <div class="asset-actions">
                    <button class="btn-small btn-secondary" onclick="app.showAlarmsFor('${ticker}')">Alarms</button>
                    <button class="btn-small btn-danger" onclick="app.removeAsset('${ticker}')">Remove</button>
                </div>
            `;

            assetsList.appendChild(assetItem);
        });
    }

    renderAlarms() {
        const activeAlarmsList = document.getElementById('activeAlarmsList');

        // Filter alarms for selected asset
        const assetAlarms = Array.from(this.alarms.values())
            .filter(alarm => alarm.ticker === this.selectedAsset);

        if (assetAlarms.length === 0) {
            activeAlarmsList.innerHTML = '<p class="placeholder">No alarms configured</p>';
            return;
        }

        activeAlarmsList.innerHTML = '';

        assetAlarms.forEach(alarm => {
            const alarmItem = document.createElement('div');
            alarmItem.className = 'alarm-item' + (alarm.triggered ? ' triggered' : '');

            // Determine if this alarm is in reset cooldown
            const now = Date.now();
            const resetting = alarm.resetUntil && alarm.resetUntil > now;
            const secondsLeft = resetting ? Math.ceil((alarm.resetUntil - now) / 1000) : 0;

            alarmItem.innerHTML = `
                <div class="alarm-description">
                    ${this.getAlarmDescription(alarm)} ${resetting ? `<span class="reset-counter">(reset in ${secondsLeft}s)</span>` : ''}
                    ${alarm.triggered ? ' <strong>(TRIGGERED)</strong>' : ''}
                </div>
                <div>
                    <button class="btn-small btn-danger" ${resetting ? 'disabled' : ''} onclick="app.removeAlarm('${alarm.id}')">Remove</button>
                </div>
            `;

            activeAlarmsList.appendChild(alarmItem);
        });
    }

    showAlarmsFor(ticker) {
        this.selectedAsset = ticker;
        const asset = this.assets.get(ticker);

        document.getElementById('selectedAssetName').textContent = `${asset.name} (${ticker})`;
        document.querySelector('.card:nth-child(1)').style.display = 'none';
        document.querySelector('.card:nth-child(2)').style.display = 'none';
        document.getElementById('alarmsSection').style.display = 'block';

        this.currentView = 'alarms';
        this.renderAlarms();
    }

    showAssetsView() {
        this.currentView = 'assets';
        this.selectedAsset = null;

        document.querySelector('.card:nth-child(1)').style.display = 'block';
        document.querySelector('.card:nth-child(2)').style.display = 'block';
        document.getElementById('alarmsSection').style.display = 'none';
    }

    showAlarmModal(message, direction) {
        const modal = document.getElementById('alarmModal');
        const messageEl = document.getElementById('alarmMessage');
        const directionEl = document.getElementById('alarmDirection');

        messageEl.innerHTML = message.replace(/\n/g, '<br>');

        // Show directional arrow
        if (direction === 'up') {
            directionEl.innerHTML = '↑';
            directionEl.className = 'alarm-direction up';
        } else if (direction === 'down') {
            directionEl.innerHTML = '↓';
            directionEl.className = 'alarm-direction down';
        } else {
            // No direction (e.g., test alarm)
            directionEl.innerHTML = '';
            directionEl.className = 'alarm-direction';
        }

        modal.classList.add('active');

        // If this is a target alarm, show a Restart button next to Dismiss
        try {
            const restartExisting = document.getElementById('restartAlarmBtn');
            if (restartExisting) restartExisting.remove();

            const dismissBtn = document.getElementById('dismissAlarmBtn');
            if (this.activeAlarm && this.activeAlarm.alarm && this.activeAlarm.alarm.type === 'target') {
                const restartBtn = document.createElement('button');
                restartBtn.id = 'restartAlarmBtn';
                restartBtn.className = 'btn-dismiss';
                restartBtn.style.marginLeft = '12px';
                restartBtn.textContent = 'RESTART (60s)';
                restartBtn.addEventListener('click', async () => {
                    // Start a 60s reset cooldown for this alarm
                    const alarmObj = this.activeAlarm.alarm;
                    this.startResetCooldown(alarmObj.id);
                    // Close modal after starting cooldown
                    this.dismissAlarm();
                });

                // insert after dismiss button
                dismissBtn.insertAdjacentElement('afterend', restartBtn);
            }
        } catch (e) {
            console.error('Error adding restart button to modal:', e);
        }
    }

    hideAlarmModal() {
        const modal = document.getElementById('alarmModal');
        modal.classList.remove('active');
    }

    updateStatus(text, state = '') {
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');

        statusText.textContent = text;
        statusDot.className = 'status-dot' + (state ? ' ' + state : '');
    }

    showError(message) {
        const errorEl = document.getElementById('assetError');
        errorEl.textContent = message;
    }

    clearError() {
        const errorEl = document.getElementById('assetError');
        errorEl.textContent = '';
    }

    // ========================================
    // Event Listeners
    // ========================================

    calculatePercentTillTrigger(alarm, asset) {
        switch (alarm.type) {
            case 'target': {
                const price = asset.price;
                const targetPrice = alarm.targetPrice;
                const percentDiff = ((targetPrice - price) / price) * 100;
                return percentDiff.toFixed(2);
            }

            case 'extreme':
                if (alarm.extremeType === 'max') {
                    const maxPrice = asset.maxPrice;
                    const percentDown = ((maxPrice - asset.price) / maxPrice) * 100;
                    return (alarm.percentage - percentDown).toFixed(2);
                } else {
                    const minPrice = asset.minPrice;
                    const percentUp = ((asset.price - minPrice) / minPrice) * 100;
                    return (alarm.percentage - percentUp).toFixed(2);
                }

            case 'timeframe': {
                // For timeframe alarms, we'll show the remaining percentage needed
                const history = this.priceHistory.get(alarm.ticker) || [];
                if (history.length < 2) return "N/A";

                let startTime;
                if (alarm.timeUnit === 'since_start') {
                    startTime = alarm.lastResetTime || alarm.createdAt;
                } else {
                    const timeframeMs = this.getTimeframeMs(alarm);
                    startTime = Date.now() - timeframeMs;
                }

                const relevantHistory = history.filter(h => h.timestamp >= startTime);
                if (relevantHistory.length === 0) return "N/A";

                const startPrice = relevantHistory[0].price;
                const price = asset.price;
                const percentChange = ((price - startPrice) / startPrice) * 100;
                
                if (alarm.direction === 'up') {
                    return (alarm.percentage - percentChange).toFixed(2);
                } else if (alarm.direction === 'down') {
                    return (alarm.percentage + percentChange).toFixed(2);
                } else {
                    return (alarm.percentage - Math.abs(percentChange)).toFixed(2);
                }}

            default:
                return "N/A";
        }
    }

    renderAllActiveAlarms() {
        const tbody = document.querySelector('#allAlarmsTable tbody');
        tbody.innerHTML = '';

        // Group alarms by ticker. Include alarms that are not triggered OR are in reset cooldown
        const alarmsByTicker = new Map();
        const now = Date.now();
        this.alarms.forEach((alarm) => {
            const inCooldown = alarm.resetUntil && alarm.resetUntil > now;
            if (!alarm.triggered || inCooldown) {
                if (!alarmsByTicker.has(alarm.ticker)) {
                    alarmsByTicker.set(alarm.ticker, []);
                }
                alarmsByTicker.get(alarm.ticker).push(alarm);
            }
        });

        // Render each group
        alarmsByTicker.forEach((alarms, ticker) => {
            const asset = this.assets.get(ticker);
            if (!asset) return;

            alarms.forEach((alarm, index) => {
                const row = document.createElement('tr');
                
                const percentTillTrigger = this.calculatePercentTillTrigger(alarm, asset);
                const displayPercentage = percentTillTrigger === "N/A" ? "N/A" : percentTillTrigger + "%";

                const now = Date.now();
                const resetting = alarm.resetUntil && alarm.resetUntil > now;
                const secondsLeft = resetting ? Math.ceil((alarm.resetUntil - now) / 1000) : 0;

                row.innerHTML = `
                    <td>${index === 0 ? asset.name : ''}</td>
                    <td>${this.getAlarmDescription(alarm)} ${resetting ? `<span class="reset-counter">(reset in ${secondsLeft}s)</span>` : ''}</td>
                    <td>${displayPercentage}</td>
                    <td>
                        <button class="btn-small btn-danger" ${resetting ? 'disabled' : ''} onclick="app.removeAlarm('${alarm.id}')">Remove</button>
                    </td>
                `;

                if (index === 0) {
                    row.classList.add('alarm-group');
                }

                tbody.appendChild(row);
            });
        });

        if (tbody.children.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = '<td colspan="4" class="placeholder">No active alarms</td>';
            tbody.appendChild(row);
        }
    }

    setupEventListeners() {
            // Handle tab switching
            document.querySelectorAll('.tab-button').forEach(button => {
            button.addEventListener('click', () => {
                    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');

                const tabId = button.getAttribute('data-tab');
                document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
                document.getElementById(tabId).classList.add('active');

                // If switching to all-alarms tab, render the alarms grid
                if (tabId === 'all-alarms') {
                    this.renderAllActiveAlarms();
                }
            });
        });

        // Add asset
        document.getElementById('addAssetBtn').addEventListener('click', () => {
            const ticker = document.getElementById('assetTicker').value;
            this.addAsset(ticker);
        });

        document.getElementById('assetTicker').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const ticker = document.getElementById('assetTicker').value;
                this.addAsset(ticker);
            }
        });

        // Add target price alarm
        document.getElementById('addTargetAlarmBtn').addEventListener('click', () => {
            const targetPrice = document.getElementById('targetPrice').value;
            const direction = document.getElementById('targetDirection').value;

            if (targetPrice && this.selectedAsset) {
                this.addTargetPriceAlarm(this.selectedAsset, targetPrice, direction);
                document.getElementById('targetPrice').value = '';
            }
        });

        // Add extreme alarm
        document.getElementById('addExtremeAlarmBtn').addEventListener('click', () => {
            const percentage = document.getElementById('percentFromExtreme').value;
            const extremeType = document.getElementById('extremeType').value;

            if (percentage && this.selectedAsset) {
                this.addExtremeAlarm(this.selectedAsset, percentage, extremeType);
                document.getElementById('percentFromExtreme').value = '';
            }
        });

        // Handle timeframe unit change to disable/enable time value input
        document.getElementById('timeframeUnit').addEventListener('change', (e) => {
            const timeValueInput = document.getElementById('timeframeValue');
            if (e.target.value === 'since_start') {
                timeValueInput.disabled = true;
                timeValueInput.placeholder = 'N/A';
                timeValueInput.value = '';
            } else {
                timeValueInput.disabled = false;
                timeValueInput.placeholder = 'Time';
            }
        });

        // Add timeframe alarm
        document.getElementById('addTimeframeAlarmBtn').addEventListener('click', () => {
            const percentage = document.getElementById('percentMove').value;
            const direction = document.getElementById('moveDirection').value;
            const timeValue = document.getElementById('timeframeValue').value;
            const timeUnit = document.getElementById('timeframeUnit').value;

            if (percentage && this.selectedAsset) {
                // For 'since_start', timeValue is not required
                if (timeUnit === 'since_start' || timeValue) {
                    this.addTimeframeAlarm(this.selectedAsset, percentage, direction, timeValue, timeUnit);
                    document.getElementById('percentMove').value = '';
                    document.getElementById('timeframeValue').value = '';
                }
            }
        });

        // Back to assets
        document.getElementById('backToAssetsBtn').addEventListener('click', () => {
            this.showAssetsView();
        });

        // Dismiss alarm
        document.getElementById('dismissAlarmBtn').addEventListener('click', () => {
            this.dismissAlarm();
        });

        // Test alarm
        document.getElementById('testAlarmBtn').addEventListener('click', () => {
            this.triggerTestAlarm();
        });
    }
}

// Initialize the application
const app = new CryptoPriceAlarm();
