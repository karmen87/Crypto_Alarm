# Roadmap

Planned work for Crypto Price Alarm, roughly in priority order. Hour figures are rough estimates.

## 1. Authentication (~6–8 h)

The server has no login today and binds to `127.0.0.1` by default (see the README).

- [ ] Single-user login with a password set through an environment variable
- [ ] Protect the HTTP routes and the Socket.IO connection, keeping `/healthz` public
- [ ] Session handling and logout
- [ ] Document safe use of `0.0.0.0` once login is in place

## 2. Test coverage for untested parts (~8–10 h)

The current unit tests cover the alarm rules and the monitor.

- [ ] Notifier: ntfy, Telegram and webhook delivery, retries, and the 30 s repeat suppression
- [ ] Price feed: WebSocket reconnect with backoff and the REST fallback for stale pairs
- [ ] Binance client: rate-limit handling (HTTP 418/429 and `Retry-After`)
- [ ] Socket.IO event handlers in `web.py`
- [ ] Browser UI smoke tests

## 3. Configurable tuning values (~2–3 h)

- [ ] Move hard-coded values to environment variables: stale-price limit (2 min), target-alarm
      restart cooldown (60 s), notification repeat window (30 s), fallback polling interval
- [ ] Document them in `.env.example` and the docs site

## 4. New alarm types (~10–15 h)

- [ ] Technical-indicator alarms, e.g. RSI crossing a level or a moving-average crossover
- [ ] Statistical alarms, e.g. price z-score or a volatility spike over a window
- [ ] UI forms and "% till trigger" display for the new types
- [ ] Tests and documentation for each new type

## 5. Release and maintenance tooling (~4–6 h)

- [ ] Automated dependency updates
- [ ] Dependency vulnerability scanning in CI
- [ ] Publish the Docker image to a container registry
- [ ] Tagged releases with a changelog

**Estimated total: about 30–40 hours.**
