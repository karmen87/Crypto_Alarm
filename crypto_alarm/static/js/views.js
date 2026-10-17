// Rendering. Every list is reconciled by key, so a price update only touches the text that changed.

import { $, h, reconcile, setText } from './dom.js';

const percentText = (value) => (value == null ? 'N/A' : `${value.toFixed(2)}%`);

export class Views {
    /**
     * @param {object} state shared client state (assets, alarms, selected)
     * @param {{ openAlarms, removeAsset, removeAlarm }} actions
     */
    constructor(state, actions) {
        this.state = state;
        this.actions = actions;
    }

    renderAll() {
        this.renderAssets();
        this.renderAllAlarms();
        this.renderConfig();
    }

    renderAssets() {
        const assets = Object.values(this.state.assets);
        const alarmCounts = {};
        for (const alarm of Object.values(this.state.alarms)) {
            alarmCounts[alarm.ticker] = (alarmCounts[alarm.ticker] ?? 0) + 1;
        }

        reconcile(
            $('assetsList'),
            assets,
            (asset) => asset.ticker,
            (asset) => this.#createAssetRow(asset),
            (el, asset) => this.#updateAssetRow(el, asset, alarmCounts[asset.ticker] ?? 0),
        );
        $('assetsPlaceholder').hidden = assets.length > 0;
    }

    #createAssetRow(asset) {
        const refs = {
            name: h('div', { class: 'asset-name' }),
            meta: h('span'),
            badge: h('span', { class: 'stale-badge', hidden: true }, 'stale'),
            price: h('div', { class: 'price-value' }),
            change: h('div'),
        };
        const el = h(
            'div',
            { class: 'asset-item' },
            h('div', { class: 'asset-info' }, refs.name, h('div', { class: 'asset-ticker' }, refs.meta, refs.badge)),
            h('div', { class: 'asset-price' }, refs.price, refs.change),
            h(
                'div',
                { class: 'asset-actions' },
                h(
                    'button',
                    {
                        class: 'btn-small btn-secondary',
                        'aria-label': `Alarms for ${asset.name}`,
                        onclick: () => this.actions.openAlarms(asset.ticker),
                    },
                    'Alarms',
                ),
                h(
                    'button',
                    {
                        class: 'btn-small btn-danger',
                        'aria-label': `Remove ${asset.name}`,
                        onclick: () => this.actions.removeAsset(asset.ticker),
                    },
                    'Remove',
                ),
            ),
        );
        el.refs = refs;
        return el;
    }

    #updateAssetRow(el, asset, alarmCount) {
        const { refs } = el;
        const plural = alarmCount === 1 ? '' : 's';
        setText(refs.name, asset.name);
        setText(refs.meta, `${asset.ticker} • ${alarmCount} alarm${plural}`);
        refs.badge.hidden = !asset.stale;
        el.classList.toggle('stale', asset.stale);
        setText(refs.price, asset.priceText);

        const up = asset.change24h >= 0;
        setText(refs.change, `${up ? '+' : ''}${asset.change24h.toFixed(2)}%`);
        refs.change.className = `price-change ${up ? 'positive' : 'negative'}`;
    }

    /** The "All active alarms" table: untriggered (or restarting) alarms, grouped by pair. */
    renderAllAlarms() {
        const groups = new Map();
        for (const alarm of Object.values(this.state.alarms)) {
            if (alarm.triggered && !alarm.resetting) continue;
            if (!this.state.assets[alarm.ticker]) continue;
            if (!groups.has(alarm.ticker)) groups.set(alarm.ticker, []);
            groups.get(alarm.ticker).push(alarm);
        }
        const rows = [...groups.values()].flatMap((alarms) =>
            alarms.map((alarm, i) => ({ alarm, first: i === 0 })),
        );

        reconcile(
            document.querySelector('#allAlarmsTable tbody'),
            rows,
            (row) => row.alarm.id,
            (row) => this.#createAllAlarmsRow(row.alarm),
            (el, row) => {
                const { refs } = el;
                setText(refs.name, row.first ? this.state.assets[row.alarm.ticker].name : '');
                setText(refs.description, row.alarm.description);
                setText(refs.percent, percentText(row.alarm.percentToTrigger));
                el.classList.toggle('alarm-group', row.first);
            },
        );
        $('allAlarmsPlaceholder').hidden = rows.length > 0;
    }

    #createAllAlarmsRow(alarm) {
        const refs = { name: h('td'), description: h('td'), percent: h('td') };
        const el = h(
            'tr',
            {},
            refs.name,
            refs.description,
            refs.percent,
            h(
                'td',
                {},
                h('button', { class: 'btn-small btn-danger', onclick: () => this.actions.removeAlarm(alarm.id) }, 'Remove'),
            ),
        );
        el.refs = refs;
        return el;
    }

    /** The per-pair alarm configuration view: header text and the pair's alarm list. */
    renderConfig() {
        const asset = this.state.assets[this.state.selected];
        if (!asset) return;

        setText($('selectedAssetName'), `${asset.name} (${asset.ticker})`);
        setText($('extremesText'), `Max ${asset.maxPriceText} · Min ${asset.minPriceText}`);

        const alarms = Object.values(this.state.alarms).filter((a) => a.ticker === asset.ticker);
        reconcile(
            $('activeAlarmsList'),
            alarms,
            (alarm) => alarm.id,
            (alarm) => this.#createAlarmRow(alarm),
            (el, alarm) => {
                const { refs } = el;
                el.classList.toggle('triggered', alarm.triggered);
                setText(refs.description, alarm.description);
                setText(refs.flag, alarm.triggered ? (alarm.resetting ? 'RESETTING...' : 'TRIGGERED') : '');
                refs.remove.disabled = alarm.resetting;
            },
        );
        $('activeAlarmsPlaceholder').hidden = alarms.length > 0;
    }

    #createAlarmRow(alarm) {
        const refs = {
            description: h('span'),
            flag: h('strong'),
            remove: h('button', { class: 'btn-small btn-danger', onclick: () => this.actions.removeAlarm(alarm.id) }, 'Remove'),
        };
        const el = h(
            'div',
            { class: 'alarm-item' },
            h('div', { class: 'alarm-description' }, refs.description, ' ', refs.flag),
            h('div', {}, refs.remove),
        );
        el.refs = refs;
        return el;
    }
}
