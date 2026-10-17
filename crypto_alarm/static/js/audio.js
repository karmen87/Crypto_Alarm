// Pulsing alarm tone using the Web Audio API.

const PULSE_MS = 150;
const VOLUME = 0.6;

export class AlarmSound {
    #ctx = null;
    #osc = null;
    #gain = null;
    #timer = null;

    /** Browsers only allow audio after a user gesture; call this from a click handler. */
    unlock() {
        if (!this.#ctx) {
            this.#ctx = new (window.AudioContext || window.webkitAudioContext)();
        }
    }

    async start() {
        this.unlock();
        this.stop();
        if (this.#ctx.state === 'suspended') await this.#ctx.resume();

        this.#osc = this.#ctx.createOscillator();
        this.#gain = this.#ctx.createGain();
        this.#osc.connect(this.#gain);
        this.#gain.connect(this.#ctx.destination);
        this.#osc.type = 'sawtooth';
        this.#osc.frequency.value = 880;
        this.#gain.gain.value = VOLUME;
        this.#osc.start();

        let on = true;
        this.#timer = setInterval(() => {
            on = !on;
            this.#gain.gain.value = on ? VOLUME : 0;
        }, PULSE_MS);
    }

    stop() {
        clearInterval(this.#timer);
        this.#timer = null;
        if (this.#osc) {
            try {
                this.#osc.stop();
            } catch {
                // already stopped
            }
            this.#osc.disconnect();
            this.#osc = null;
        }
        if (this.#gain) {
            this.#gain.disconnect();
            this.#gain = null;
        }
    }
}
