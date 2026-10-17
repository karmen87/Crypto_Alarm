// The alarm dialog: one at a time, queued, keyboard-accessible, with sound and a flashing title.

import { $, h } from './dom.js';

const ARROWS = { up: '▲ UP', down: '▼ DOWN' };

export class AlarmModal {
    /**
     * @param {AlarmSound} sound
     * @param {{ onAck: (alarmId: string) => void, onRestart: (alarmId: string) => void }} actions
     */
    constructor(sound, { onAck, onRestart }) {
        this.sound = sound;
        this.onAck = onAck;
        this.onRestart = onRestart;
        this.root = $('alarmModal');
        this.current = null;
        this.queue = [];
        this.returnFocus = null;
        this.flashTimer = null;
        this.originalTitle = document.title;

        this.root.addEventListener('keydown', (e) => this.#onKey(e));
    }

    /** Show an alarm event; if one is already showing, queue it (duplicates are ignored). */
    show(event) {
        const id = event.alarm?.id;
        if (this.current) {
            const seen = this.current.alarm?.id === id || this.queue.some((q) => q.alarm?.id === id);
            if (id === undefined || !seen) this.queue.push(event);
            return;
        }
        this.current = event;
        this.#render(event);
        this.returnFocus = document.activeElement;
        this.root.hidden = false;
        this.root.classList.add('active');
        this.root.querySelector('button').focus();
        this.sound.start();
        this.#flashTitle();
    }

    showTest() {
        this.show({
            alarm: { type: 'test' },
            message: 'This is a test alarm!\n\nAdjust your system volume and check that the sound is working.',
            direction: null,
        });
    }

    dismiss() {
        const event = this.current;
        if (!event) return;

        this.sound.stop();
        clearInterval(this.flashTimer);
        this.flashTimer = null;
        document.title = this.originalTitle;
        this.root.classList.remove('active');
        this.root.hidden = true;
        this.current = null;
        this.returnFocus?.focus?.();

        // Tell the server this alarm was seen so it isn't replayed to the next client that connects.
        if (event.alarm?.id) this.onAck(event.alarm.id);

        const next = this.queue.shift();
        if (next) this.show(next);
    }

    #render(event) {
        $('alarmMessage').textContent = event.message;

        const arrow = $('alarmDirection');
        arrow.textContent = ARROWS[event.direction] ?? '';
        arrow.className = 'alarm-direction' + (event.direction ? ` ${event.direction}` : '');

        const buttons = [h('button', { class: 'btn-dismiss', onclick: () => this.dismiss() }, 'DISMISS ALARM')];
        if (event.alarm?.type === 'target') {
            buttons.push(
                h(
                    'button',
                    {
                        class: 'btn-dismiss',
                        onclick: () => {
                            this.onRestart(event.alarm.id);
                            this.dismiss();
                        },
                    },
                    'RESTART (60s)',
                ),
            );
        }
        $('alarmButtons').replaceChildren(...buttons);
    }

    #flashTitle() {
        let alert = true;
        this.flashTimer = setInterval(() => {
            document.title = alert ? '\u{1F6A8} ALARM TRIGGERED! \u{1F6A8}' : '⚠️ PRICE ALARM ⚠️';
            alert = !alert;
        }, 1000);
    }

    /** Keep Tab inside the dialog; Escape dismisses. */
    #onKey(e) {
        if (e.key === 'Escape') {
            this.dismiss();
            return;
        }
        if (e.key !== 'Tab') return;

        const buttons = [...this.root.querySelectorAll('button')];
        const first = buttons[0];
        const last = buttons[buttons.length - 1];
        if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
        }
    }
}
