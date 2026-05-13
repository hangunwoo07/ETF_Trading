# ETF Trading Bot

Automated ETF trading bot for the Kiwoom Securities API. The app connects to the Kiwoom REST API and websocket API, subscribes to market-time and ETF real-time feeds, selects the ETF with the largest recent transaction value from a fixed watchlist, and places market buy orders when the selected ETF rises by at least 1%.

This project is still in active development. Review the strategy and mock/live mode carefully before running it with a real account.

## Project Structure

```text
main.py
  Entry point. Loads environment variables, defines the ETF watchlist, creates Supervisor, and runs it forever.

Supervisor.py
  Lifecycle wrapper. Creates KiwoomClient, KiwoomWebsocketClient, and TradingBot, then restarts the bot after errors.

TradingBot.py
  Strategy flow. Waits for market preparation time, selects an ETF, checks deposit, registers real-time ETF data, handles market-time and price messages, and places buy orders.

KiwoomClient.py
  Synchronous REST client for token issuance, deposit lookup, ETF daily data, buy orders, and sell orders.

KiwoomWebsocket.py
  Async websocket client for login, PING handling, sending messages, receiving messages, and registering/removing real-time feeds.
```

## Requirements

- Python `>=3.14`
- Kiwoom API credentials
- Network access to Kiwoom mock or live API endpoints

Dependencies are declared in [pyproject.toml](./pyproject.toml):

- `python-dotenv`
- `requests`
- `websockets`
- `asyncio`

## Environment

Create a `.env` file in the project root:

```env
APP_KEY=your_app_key
SECRET_KEY=your_secret_key
IS_MOCK=True
```

Use `IS_MOCK=True` for the Kiwoom mock API. Use `IS_MOCK=False` only when you intentionally want to connect to the live API.

## Install

If you use `uv`:

```bash
uv sync
```

Or with plain Python tooling:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run

```bash
python3 main.py
```

Or, if using `uv`:

```bash
uv run python main.py
```

## Runtime Flow

1. `main.py` loads `.env` and creates a fixed ETF watchlist.
2. `Supervisor` creates:
   - `KiwoomClient`
   - `KiwoomWebsocketClient`
   - `TradingBot`
3. `TradingBot.run()` connects the websocket and logs in.
4. The bot registers market-time feed type `0s`.
5. The bot waits until market status code `215` becomes `"0"` for market preparation.
6. The bot selects the ETF with the largest recent transaction value using `get_biggest_etf_volume()`.
7. The bot checks available deposit.
8. The bot registers ETF real-time feed type `0B`.
9. Once market status code `215` becomes `"3"`, the bot handles real-time messages.
10. If ETF percent change field `12` is `+1.0` or greater, the bot places a market buy order.
11. If market status code `215` becomes `"4"`, the bot treats the market as closed and starts the next cycle.

## Kiwoom Message Types Used

| Type | Meaning in this project |
| --- | --- |
| `0s` | Market-time/status messages |
| `0B` | ETF real-time price/change messages |
| `PING` | Websocket heartbeat; echoed automatically by `KiwoomWebsocketClient.receive_message()` |

Market status currently uses value key `215`:

| Code | Meaning in bot |
| --- | --- |
| `"0"` | Market preparation |
| `"3"` | Market open |
| `"4"` | Market closed |

## Strategy Summary

The current strategy is intentionally simple:

- Build a fixed ETF watchlist in `main.py`.
- Before market open, call `get_biggest_etf_volume(etf_list, track_range=5)`.
- Choose the ETF with the largest summed `acc_trde_prica` over the recent daily records returned by Kiwoom.
- During market open, watch real-time ETF messages.
- Buy when percent change field `12` starts with `+` and is at least `1.0`.
- Quantity is calculated as:

```python
deposit // etf_price
```

## Safety Notes

- `KiwoomClient` uses synchronous `requests` calls. `TradingBot.handle_realtime_message()` already uses `asyncio.to_thread()` for `buy_etf()` so the websocket event loop is not blocked by the order request.
- Other REST calls, such as `get_biggest_etf_volume()` and `check_deposit()`, are still synchronous.
- `Supervisor` restarts the same `TradingBot` instance after an exception. A future improvement should recreate the REST client, websocket client, and bot on each restart so stale websocket/token state does not leak across restarts.
- `sell_etf()` exists but is not currently wired into the main trading loop.
- Live trading can place real market orders. Keep `IS_MOCK=True` until the strategy and failure handling are verified.

## Development Notes

Basic syntax check:

```bash
python3 -m py_compile main.py Supervisor.py TradingBot.py KiwoomClient.py KiwoomWebsocket.py
```

Useful next improvements:

- Return structured results from realtime handlers instead of raw strings.
- Add quantity validation before placing buy orders.
- Recreate clients inside `Supervisor.run_forever()` after crashes.
- Add a `close()` method to `KiwoomWebsocketClient`.
- Add tests for message parsing and strategy decisions.
- Move the ETF watchlist out of `main.py` into config.
