// Crypto Price Alarm - Client Side
class CryptoAlarmClient {
    constructor() {
        this.socket = null;
        this.assets = {};
        this.alarms = {};
        this.currentView = 'assets';
        this.selectedAsset = null;
        this.audioContext = null;
        this.alarmOscillator = null;
        this.alarmGain = null;
        this.alarmPulseInterval = null;
        this.titleFlashInterval = null;
        this.originalTitle = document.title;
        this.alarmSoundPlaying = false;
        this.activeAlarm = null;

        this.init();
    }

    init() {
        this.setupSocketConnection();
        this.setupEventListeners();
        this.setupAudioContext();
        this.updateStatus('Connecting...', '');
    }

    setupSocketConnection() {
        this.socket = io();

        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.updateStatus('Connected', 'active');
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.updateStatus('Disconnected', 'error');
        });

        this.socket.on('initial_state', (data) => {
            this.assets = data.assets;
            this.alarms = data.alarms;
            this.renderAssets();
        });

        this.socket.on('asset_adding', (data) => {
            this.updateStatus('Adding ' + data.pair + '... (5-10 seconds)', '');
            this.showError('Fetching data from CoinGecko API... Please wait (this takes 5-10 seconds due to rate limiting)');
        });

        this.socket.on('asset_added', (data) => {
            if (data.success) {
                this.assets[data.asset.ticker] = data.asset;
                this.renderAssets();
                this.clearError();
                this.updateStatus('Connected', 'active');
                document.getElementById('assetTicker').value = '';
            }
        });

        this.socket.on('asset_removed', (data) => {
            delete this.assets[data.ticker];
            this.renderAssets();
        });

        this.socket.on('alarm_added', (data) => {
            this.alarms[data.alarm.id] = data.alarm;
            if (this.currentView === 'alarms') {
                this.renderAlarms();
            }
        });

        this.socket.on('alarm_removed', (data) => {
            delete this.alarms[data.alarmId];
            if (this.currentView === 'alarms') {
                this.renderAlarms();
            }
            this.renderAllActiveAlarms();
        });

        this.socket.on('alarm_restarted', (data) => {
            if (this.alarms[data.alarmId]) {
                this.alarms[data.alarmId].resetting = true;
                if (this.currentView === 'alarms') {
                    this.renderAlarms();
                }
            }
        });

        this.socket.on('price_update', (data) => {
            this.assets = data.assets;
            this.alarms = data.alarms;
            this.renderAssets();
            if (this.currentView === 'alarms') {
                this.renderAlarms();
            }
            const allAlarmsTab = document.querySelector('.tab-button[data-tab="all-alarms"]');
            if (allAlarmsTab && allAlarmsTab.classList.contains('active')) {
                this.renderAllActiveAlarms();
            }
        });

        this.socket.on('alarm_triggered', (data) => {
            this.triggerAlarm(data);
        });

        this.socket.on('error', (data) => {
            this.showError(data.message);
        });
    }

    setupAudioContext() {
        document.addEventListener('click', () => {
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
        }, { once: true });
    }

    setupEventListeners() {
        // Tab switching
        document.querySelectorAll('.tab-button').forEach(button => {
            button.addEventListener('click', () => {
                document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');

                const tabId = button.getAttribute('data-tab');
                document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
                document.getElementById(tabId).classList.add('active');

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

        // Add target alarm
        document.getElementById('addTargetAlarmBtn').addEventListener('click', () => {
            const targetPrice = document.getElementById('targetPrice').value;
            const direction = document.getElementById('targetDirection').value;

            if (targetPrice && this.selectedAsset) {
                this.addAlarm({
                    type: 'target',
                    ticker: this.selectedAsset,
                    targetPrice: targetPrice,
                    direction: direction
                });
                document.getElementById('targetPrice').value = '';
            }
        });

        // Add extreme alarm
        document.getElementById('addExtremeAlarmBtn').addEventListener('click', () => {
            const percentage = document.getElementById('percentFromExtreme').value;
            const extremeType = document.getElementById('extremeType').value;

            if (percentage && this.selectedAsset) {
                this.addAlarm({
                    type: 'extreme',
                    ticker: this.selectedAsset,
                    percentage: percentage,
                    extremeType: extremeType
                });
                document.getElementById('percentFromExtreme').value = '';
            }
        });

        // Timeframe unit change
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
                if (timeUnit === 'since_start' || timeValue) {
                    this.addAlarm({
                        type: 'timeframe',
                        ticker: this.selectedAsset,
                        percentage: percentage,
                        direction: direction,
                        timeValue: timeValue,
                        timeUnit: timeUnit
                    });
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

    addAsset(pair) {
        if (!pair.trim()) {
            this.showError('Please enter a trading pair');
            return;
        }

        this.updateStatus('Fetching pair info...', '');
        this.socket.emit('add_asset', { pair: pair });
    }

    removeAsset(ticker) {
        this.socket.emit('remove_asset', { ticker: ticker });
    }

    addAlarm(alarmData) {
        this.socket.emit('add_alarm', alarmData);
    }

    removeAlarm(alarmId) {
        this.socket.emit('remove_alarm', { alarmId: alarmId });
    }

    restartAlarm(alarmId) {
        this.socket.emit('restart_alarm', { alarmId: alarmId });
    }

    formatPairPrice(price, quote) {
        const stablecoins = ['USDT', 'USDC', 'USD', 'BUSD', 'DAI', 'TUSD', 'USDD', 'USDP'];
        const isStablecoin = stablecoins.includes(quote.toUpperCase());

        if (isStablecoin) {
            if (price >= 1000) return `$${price.toFixed(2)}`;
            if (price >= 1) return `$${price.toFixed(4)}`;
            if (price >= 0.01) return `$${price.toFixed(6)}`;
            return `$${price.toFixed(8)}`;
        } else {
            if (price >= 1) return price.toFixed(6);
            if (price >= 0.0001) return price.toFixed(8);
            return price.toFixed(10);
        }
    }

    renderAssets() {
        const assetsList = document.getElementById('assetsList');

        if (Object.keys(this.assets).length === 0) {
            assetsList.innerHTML = '<p class="placeholder">No pairs added yet</p>';
            return;
        }

        assetsList.innerHTML = '';

        Object.values(this.assets).forEach(asset => {
            const assetItem = document.createElement('div');
            assetItem.className = 'asset-item';

            const changeClass = asset.change24h >= 0 ? 'positive' : 'negative';
            const changeSymbol = asset.change24h >= 0 ? '+' : '';

            // Count alarms
            let alarmCount = 0;
            Object.values(this.alarms).forEach(alarm => {
                if (alarm.ticker === asset.ticker) alarmCount++;
            });

            const priceDisplay = this.formatPairPrice(asset.price, asset.quote);

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
                    <button class="btn-small btn-secondary" onclick="app.showAlarmsFor('${asset.ticker}')">Alarms</button>
                    <button class="btn-small btn-danger" onclick="app.removeAsset('${asset.ticker}')">Remove</button>
                </div>
            `;

            assetsList.appendChild(assetItem);
        });
    }

    getAlarmDescription(alarm) {
        const asset = this.assets[alarm.ticker];

        switch (alarm.type) {
            case 'target':
                const directionText = alarm.direction === 'up' ? ' (from below)' :
                                     alarm.direction === 'down' ? ' (from above)' : '';
                const priceDisplay = asset ?
                    this.formatPairPrice(alarm.targetPrice, asset.quote) :
                    `$${alarm.targetPrice.toFixed(2)}`;
                return `Target price: ${priceDisplay}${directionText}`;

            case 'extreme':
                return `${alarm.percentage}% ${alarm.extremeType === 'max' ? 'down from max' : 'up from min'} price`;

            case 'timeframe':
                const moveDir = alarm.direction === 'up' ? 'up' :
                               alarm.direction === 'down' ? 'down' : 'change';

                if (alarm.timeUnit === 'since_start') {
                    return `${alarm.percentage}% ${moveDir} since start (resets on trigger)`;
                } else {
                    return `${alarm.percentage}% ${moveDir} in ${alarm.timeValue} ${alarm.timeUnit}`;
                }

            default:
                return 'Unknown alarm type';
        }
    }

    renderAlarms() {
        const activeAlarmsList = document.getElementById('activeAlarmsList');

        const assetAlarms = Object.values(this.alarms).filter(alarm => alarm.ticker === this.selectedAsset);

        if (assetAlarms.length === 0) {
            activeAlarmsList.innerHTML = '<p class="placeholder">No alarms configured</p>';
            return;
        }

        activeAlarmsList.innerHTML = '';

        assetAlarms.forEach(alarm => {
            const alarmItem = document.createElement('div');
            alarmItem.className = 'alarm-item' + (alarm.triggered ? ' triggered' : '');

            const resetting = alarm.resetting || false;

            alarmItem.innerHTML = `
                <div class="alarm-description">
                    ${this.getAlarmDescription(alarm)}
                    ${alarm.triggered ? ' <strong>(TRIGGERED)</strong>' : ''}
                    ${resetting ? ' <strong>(RESETTING...)</strong>' : ''}
                </div>
                <div>
                    <button class="btn-small btn-danger" ${resetting ? 'disabled' : ''} onclick="app.removeAlarm('${alarm.id}')">Remove</button>
                </div>
            `;

            activeAlarmsList.appendChild(alarmItem);
        });
    }

    renderAllActiveAlarms() {
        const tbody = document.querySelector('#allAlarmsTable tbody');
        tbody.innerHTML = '';

        // Group alarms by ticker
        const alarmsByTicker = {};
        Object.values(this.alarms).forEach(alarm => {
            if (!alarm.triggered || alarm.resetting) {
                if (!alarmsByTicker[alarm.ticker]) {
                    alarmsByTicker[alarm.ticker] = [];
                }
                alarmsByTicker[alarm.ticker].push(alarm);
            }
        });

        // Render each group
        Object.entries(alarmsByTicker).forEach(([ticker, alarms]) => {
            const asset = this.assets[ticker];
            if (!asset) return;

            alarms.forEach((alarm, index) => {
                const row = document.createElement('tr');

                row.innerHTML = `
                    <td>${index === 0 ? asset.name : ''}</td>
                    <td>${this.getAlarmDescription(alarm)}</td>
                    <td>N/A</td>
                    <td>
                        <button class="btn-small btn-danger" onclick="app.removeAlarm('${alarm.id}')">Remove</button>
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

    showAlarmsFor(ticker) {
        this.selectedAsset = ticker;
        const asset = this.assets[ticker];

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

    triggerAlarm(alarmData) {
        const { alarm, asset, message, direction } = alarmData;

        this.activeAlarm = alarmData;
        this.showAlarmModal(message, direction, alarm);
        this.playAlarmSound();
        this.flashPageTitle();
    }

    showAlarmModal(message, direction, alarm) {
        const modal = document.getElementById('alarmModal');
        const messageEl = document.getElementById('alarmMessage');
        const directionEl = document.getElementById('alarmDirection');
        const buttonsEl = document.getElementById('alarmButtons');

        messageEl.innerHTML = message.replace(/\n/g, '<br>');

        if (direction === 'up') {
            directionEl.innerHTML = '↑';
            directionEl.className = 'alarm-direction up';
        } else if (direction === 'down') {
            directionEl.innerHTML = '↓';
            directionEl.className = 'alarm-direction down';
        } else {
            directionEl.innerHTML = '';
            directionEl.className = 'alarm-direction';
        }

        // Reset buttons
        buttonsEl.innerHTML = '<button id="dismissAlarmBtn" class="btn-dismiss">DISMISS ALARM</button>';

        // Add restart button for target alarms
        if (alarm && alarm.type === 'target') {
            const restartBtn = document.createElement('button');
            restartBtn.className = 'btn-dismiss';
            restartBtn.style.marginLeft = '12px';
            restartBtn.textContent = 'RESTART (60s)';
            restartBtn.onclick = () => {
                this.restartAlarm(alarm.id);
                this.dismissAlarm();
            };
            buttonsEl.appendChild(restartBtn);
        }

        // Re-attach dismiss event
        document.getElementById('dismissAlarmBtn').onclick = () => this.dismissAlarm();

        modal.classList.add('active');
    }

    hideAlarmModal() {
        const modal = document.getElementById('alarmModal');
        modal.classList.remove('active');
    }

    async playAlarmSound() {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }

        this.alarmSoundPlaying = true;

        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }

        this.alarmOscillator = this.audioContext.createOscillator();
        this.alarmGain = this.audioContext.createGain();

        this.alarmOscillator.connect(this.alarmGain);
        this.alarmGain.connect(this.audioContext.destination);

        this.alarmOscillator.type = 'sawtooth';
        this.alarmOscillator.frequency.value = 880;
        this.alarmGain.gain.value = 0.6;

        this.alarmOscillator.start();

        let pulseCount = 0;
        this.alarmPulseInterval = setInterval(async () => {
            if (!this.activeAlarm) {
                this.stopAlarmSound();
                return;
            }

            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }

            if (pulseCount % 2 === 0) {
                this.alarmGain.gain.value = 0.6;
                this.alarmOscillator.frequency.value = 880;
            } else {
                this.alarmGain.gain.value = 0;
            }

            pulseCount++;
        }, 150);
    }

    stopAlarmSound() {
        if (this.alarmPulseInterval) {
            clearInterval(this.alarmPulseInterval);
            this.alarmPulseInterval = null;
        }

        if (this.alarmOscillator) {
            try {
                this.alarmOscillator.stop();
            } catch (e) {
                // Already stopped
            }
            this.alarmOscillator.disconnect();
            this.alarmOscillator = null;
        }

        if (this.alarmGain) {
            this.alarmGain.disconnect();
            this.alarmGain = null;
        }

        this.alarmSoundPlaying = false;
    }

    flashPageTitle() {
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

    dismissAlarm() {
        this.stopAlarmSound();
        this.stopTitleFlash();
        this.hideAlarmModal();
        this.activeAlarm = null;
        this.alarmSoundPlaying = false;
    }

    triggerTestAlarm() {
        const message = 'This is a test alarm!<br><br>You can adjust your system volume and verify the alarm sound is working correctly.';
        this.activeAlarm = { alarm: { type: 'test' }, message: message, direction: null };
        this.showAlarmModal(message, null, null);
        this.playAlarmSound();
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
}

// Initialize the application
const app = new CryptoAlarmClient();
