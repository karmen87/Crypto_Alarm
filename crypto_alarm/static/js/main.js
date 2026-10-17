// Entry point: wires the socket, the forms and the views together.

import { $ } from './dom.js';
import { AlarmSound } from './audio.js';
import { AlarmModal } from './modal.js';
import { Views } from './views.js';

const state = {
    assets: {},
    alarms: {},
    feed: { mode: 'connecting' },
    connected: false,
    selected: null, // ticker whose alarms are being configured
};

const socket = io();
const sound = new AlarmSound();

const modal = new AlarmModal(sound, {
    onAck: (alarmId) => socket.emit('ack_alarm', { alarmId }),
    onRestart: (alarmId) => socket.emit('restart_alarm', { alarmId }),
});

const views = new Views(state, {
    openAlarms: showAlarmsFor,
    removeAsset: (ticker) => socket.emit('remove_asset', { ticker }),
    removeAlarm: (alarmId) => socket.emit('remove_alarm', { alarmId }),
});

// Coalesce bursts of events into one render per frame.
let renderQueued = false;
function render() {
    if (renderQueued) return;
    renderQueued = true;
    requestAnimationFrame(() => {
        renderQueued = false;
        if (state.selected && !state.assets[state.selected]) showOverview();
        views.renderAll();
        renderStatus();
    });
}

// --- status ------------------------------------------------------------------------------

const FEED_STATUS = {
    stream: ['Live', 'active'],
    polling: ['Live (REST fallback)', 'warn'],
    connecting: ['Connecting to Binance...', 'warn'],
    down: ['Binance feed down', 'error'],
    idle: ['Connected', 'active'],
};

function renderStatus() {
    document.body.classList.toggle('offline', !state.connected);
    const [text, level] = state.connected
        ? (FEED_STATUS[state.feed.mode] ?? FEED_STATUS.idle)
        : ['Disconnected', 'error'];
    $('statusText').textContent = text;
    $('statusDot').className = `status-dot ${level}`;
}

function showError(message) {
    $('assetError').textContent = message;
}

// --- navigation --------------------------------------------------------------------------

function showAlarmsFor(ticker) {
    state.selected = ticker;
    $('addPairSection').hidden = true;
    $('overviewSection').hidden = true;
    $('alarmsSection').hidden = false;
    render();
}

function showOverview() {
    state.selected = null;
    $('addPairSection').hidden = false;
    $('overviewSection').hidden = false;
    $('alarmsSection').hidden = true;
    render();
}

function selectTab(button) {
    for (const tab of document.querySelectorAll('.tab-button')) {
        const active = tab === button;
        tab.classList.toggle('active', active);
        tab.setAttribute('aria-selected', String(active));
        $(tab.dataset.tab).classList.toggle('active', active);
    }
}

// --- socket events -----------------------------------------------------------------------

function applyState(data) {
    state.assets = data.assets;
    state.alarms = data.alarms;
    state.feed = data.feed ?? state.feed;
}

socket.on('connect', () => {
    state.connected = true;
    render();
});

socket.on('disconnect', () => {
    state.connected = false;
    render();
});

socket.on('initial_state', (data) => {
    applyState(data);
    render();
});

socket.on('price_update', (data) => {
    applyState(data);
    render();
});

socket.on('asset_added', ({ asset }) => {
    state.assets[asset.ticker] = asset;
    $('assetTicker').value = '';
    showError('');
    setAdding(false);
    render();
});

socket.on('asset_removed', ({ ticker }) => {
    delete state.assets[ticker];
    for (const [id, alarm] of Object.entries(state.alarms)) {
        if (alarm.ticker === ticker) delete state.alarms[id];
    }
    render();
});

socket.on('alarm_added', ({ alarm }) => {
    state.alarms[alarm.id] = alarm;
    render();
});

socket.on('alarm_removed', ({ alarmId }) => {
    delete state.alarms[alarmId];
    render();
});

socket.on('alarm_restarted', ({ alarmId }) => {
    if (state.alarms[alarmId]) state.alarms[alarmId].resetting = true;
    render();
});

socket.on('alarm_triggered', (event) => modal.show(event));

socket.on('error', ({ message }) => {
    showError(message);
    setAdding(false);
});

// --- forms -------------------------------------------------------------------------------

function setAdding(adding) {
    const button = $('addAssetForm').querySelector('button');
    button.disabled = adding;
    button.textContent = adding ? 'Adding...' : 'Add pair';
}

$('addAssetForm').addEventListener('submit', (e) => {
    e.preventDefault();
    const pair = $('assetTicker').value.trim();
    if (!pair) return;
    showError('');
    setAdding(true);
    socket.emit('add_asset', { pair });
});

function bindAlarmForm(formId, build) {
    $(formId).addEventListener('submit', (e) => {
        e.preventDefault();
        if (!state.selected) return;
        showError('');
        socket.emit('add_alarm', { ticker: state.selected, ...build() });
        e.target.reset();
        syncTimeframeInputs();
    });
}

bindAlarmForm('targetForm', () => ({
    type: 'target',
    targetPrice: $('targetPrice').value,
    direction: $('targetDirection').value,
}));

bindAlarmForm('extremeForm', () => ({
    type: 'extreme',
    percentage: $('percentFromExtreme').value,
    extremeType: $('extremeType').value,
}));

bindAlarmForm('timeframeForm', () => ({
    type: 'timeframe',
    percentage: $('percentMove').value,
    direction: $('moveDirection').value,
    timeValue: $('timeframeValue').value,
    timeUnit: $('timeframeUnit').value,
}));

// "Since start" has no time amount.
function syncTimeframeInputs() {
    const sinceStart = $('timeframeUnit').value === 'since_start';
    const input = $('timeframeValue');
    input.disabled = sinceStart;
    input.required = !sinceStart;
    input.placeholder = sinceStart ? 'N/A' : 'Time';
    if (sinceStart) input.value = '';
}
$('timeframeUnit').addEventListener('change', syncTimeframeInputs);

$('resetExtremesBtn').addEventListener('click', () => {
    if (state.selected) socket.emit('reset_extremes', { ticker: state.selected });
});

$('backToAssetsBtn').addEventListener('click', showOverview);

for (const tab of document.querySelectorAll('.tab-button')) {
    tab.addEventListener('click', () => {
        selectTab(tab);
        render();
    });
}

$('testAlarmBtn').addEventListener('click', () => {
    sound.unlock();
    modal.showTest();
});

// Browsers only allow audio after a user gesture.
document.addEventListener('click', () => sound.unlock(), { once: true });

renderStatus();
