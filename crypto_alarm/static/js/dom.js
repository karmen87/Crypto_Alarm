// Small DOM helpers. Text is always inserted as text nodes, never parsed as HTML.

export const $ = (id) => document.getElementById(id);

/** Build an element: h('button', { class: 'x', onclick: fn }, 'Label', otherNode). */
export function h(tag, props = {}, ...children) {
    const el = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
        if (key === 'class') el.className = value;
        else if (key.startsWith('on')) el.addEventListener(key.slice(2), value);
        else if (key.startsWith('aria-') || key === 'role') el.setAttribute(key, value);
        else el[key] = value;
    }
    el.append(...children);
    return el;
}

/** Assign text only when it changed, so unchanged nodes are left alone. */
export function setText(el, text) {
    if (el.textContent !== text) el.textContent = text;
}

/**
 * Keyed list update: reuses existing elements, creates missing ones, removes stale ones and
 * keeps order. Nothing is rebuilt when only values changed, so hover, focus and in-flight
 * clicks survive the frequent price updates.
 *
 *   create(item) -> Element     called once per new key
 *   update(el, item)            called on every pass
 */
export function reconcile(parent, items, keyOf, create, update) {
    const existing = new Map();
    for (const child of parent.children) existing.set(child.dataset.key, child);

    const wanted = new Set();
    items.forEach((item, index) => {
        const key = String(keyOf(item));
        wanted.add(key);

        let el = existing.get(key);
        if (!el) {
            el = create(item);
            el.dataset.key = key;
        }
        update(el, item);

        if (parent.children[index] !== el) parent.insertBefore(el, parent.children[index] ?? null);
    });

    for (const [key, el] of existing) {
        if (!wanted.has(key)) el.remove();
    }
}
