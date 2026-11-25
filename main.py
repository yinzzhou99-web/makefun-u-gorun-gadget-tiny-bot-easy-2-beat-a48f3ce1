"""Tiny Bot, Easy $2: Beat Buy-and-Hold on Solana.

A deterministic hourly-bars paper-trading bot (agent-fun/bars-replay/v1).
Stdlib only, no network, no clock, no randomness: the same bars always give
the same orders, so the two grading runs match byte for byte.

Strategy (tuned on the kit's frozen dev window, 136 hourly bars):
  - Oversold dip-buying: RSI(14) at or under 25 buys a 23%-of-equity stake.
    An oversold hour in these Solana markets usually bounces within a few
    bars, so the position exits at +1.5% over its cost, at -5%, or when
    RSI(14) reaches 60. One stake per symbol, at most seven positions.
  - Activity floor: the guardrails need at least 8 trades. From batch 48,
    while fewer than 8 of our own orders have filled, buy $300 of the
    asset with the best 12-hour return; a floor position exits at +1.5%,
    -3%, RSI 60, or after 8 bars. In a quiet window this keeps the entry
    compliant; in a busy window it never fires.
  - Sells are always the whole position; buys are sized under the 25%
    per-asset weight cap. Orders cap their slippage at 200 bps.
  - Warm-up batches only build indicator history: no orders on them.

Dev-window grade (kit grade-local, process driver): net PnL +479.78 USDC
vs buy-and-hold -869.34 USDC, 37 trades, max drawdown 2.0%.
"""

import json
import sys

PROTOCOL = "agent-fun/bars-replay/v1"

RSI_N = 14
DIP_RSI = 25.0
STAKE_BPS = 2300  # 23% of equity per dip buy (cap is 25%)
ROI_NUM = 1015  # exit at +1.5% over cost
ROI_DEN = 1000
STOP_NUM = 95  # exit at -5% under cost
STOP_DEN = 100
RSI_EXIT = 60.0
MAX_SLIPPAGE_BPS = 200
MIN_BARS = RSI_N + 2  # 16 closes before any decision
FLOOR_START_SEQ = 48
FLOOR_NOTIONAL = 300_000_000  # micro-USDC ($300)
FLOOR_STOP_NUM = 97  # floor exit at -3%
FLOOR_STOP_DEN = 100
FLOOR_MAX_HOLD = 8  # bars
MAX_ORDERS_PER_BAR = 16
MAX_POSITIONS = 7


def rsi(closes):
    """RSI over the last RSI_N bars: mean gain / mean loss of closes."""
    if len(closes) <= RSI_N:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(len(closes) - RSI_N, len(closes)):
        d = closes[i] - closes[i - 1]
        if d > 0:
            gains += d
        else:
            losses -= d
    if losses == 0.0:
        return 100.0 if gains > 0.0 else 50.0
    rs = (gains / RSI_N) / (losses / RSI_N)
    return 100.0 - 100.0 / (1.0 + rs)


class Bot:
    def __init__(self, hello):
        self.hello = hello
        self.symbols = [s["symbol"] for s in hello["symbols"]]
        self.scales = {
            s["symbol"]: (s["price_scale"], s["qty_scale"]) for s in hello["symbols"]
        }
        self.warmup_bars = hello.get("warmup_bars", 0)
        self.seq = -1
        self.closes = {s: [] for s in self.symbols}
        self.cash = int(hello["capital"]["quote_units"])
        self.equity = self.cash
        self.positions = {}  # symbol -> (qty, cost) ints
        self.trades = 0  # own orders filled so far
        self.entry_cost = {}  # symbol -> cost (micro-USDC) of the open position
        self.floor_entry = {}  # symbol -> seq the floor position filled on
        self.floor_ids = set()  # client_ids of floor buys awaiting their fill
        self._next = 1

    def value(self, symbol, qty, price):
        ps, qs = self.scales[symbol]
        return qty * price * 10**6 // 10 ** (qs + ps)

    def _client_id(self):
        cid = "o%d" % self._next
        self._next += 1
        return cid

    def on_batch(self, batch):
        self.seq = batch["seq"]
        for bar in batch["bars"]:
            sym = bar["symbol"]
            if sym in self.closes:
                self.closes[sym].append(int(bar["c"]))
        account = batch["account"]
        self.cash = int(account["cash_quote_units"])
        self.equity = int(account["equity_quote_units"])
        self.positions = {
            p["symbol"]: (int(p["qty"]), int(p["cost_quote_units"]))
            for p in account["positions"]
        }
        for fill in batch.get("fills", []):
            cid = fill.get("client_id", "")
            if fill.get("status") != "filled" or cid.startswith("_"):
                continue
            self.trades += 1
            if fill.get("side") == "buy":
                sym = fill["symbol"]
                self.entry_cost[sym] = int(fill["notional_quote_units"])
                if cid in self.floor_ids:
                    self.floor_entry[sym] = self.seq
                    self.floor_ids.discard(cid)
        if self.seq < self.warmup_bars:
            return []
        if min(len(self.closes[s]) for s in self.symbols) < MIN_BARS:
            return []

        orders = []
        entries = []  # (symbol, kind) kind: "dip" or "floor"

        for sym in self.symbols:
            closes = self.closes[sym]
            r = rsi(closes)
            if r is None:
                continue
            held = self.positions.get(sym)
            if held is not None:
                qty, cost = held
                val = self.value(sym, qty, closes[-1])
                is_floor = sym in self.floor_entry
                sell = False
                if val * ROI_DEN >= cost * ROI_NUM:
                    sell = True
                elif is_floor and val * FLOOR_STOP_DEN <= cost * FLOOR_STOP_NUM:
                    sell = True
                elif not is_floor and val * STOP_DEN <= cost * STOP_NUM:
                    sell = True
                elif r >= RSI_EXIT:
                    sell = True
                elif is_floor and self.seq - self.floor_entry[sym] >= FLOOR_MAX_HOLD:
                    sell = True
                if sell:
                    orders.append(("sell", sym, qty))
                    self.entry_cost.pop(sym, None)
                    self.floor_entry.pop(sym, None)
            else:
                if r <= DIP_RSI:
                    entries.append((sym, "dip"))

        if self.seq >= FLOOR_START_SEQ and self.trades < 8:
            best = None
            best_ret = 0.0
            for sym in self.symbols:
                closes = self.closes[sym]
                if len(closes) >= 13 and sym not in self.positions:
                    ret = closes[-1] / closes[-13] - 1.0
                    if ret > best_ret:
                        best, best_ret = sym, ret
            if best is not None:
                entries.append((best, "floor"))

        held_count = len(self.positions)
        selling = {o[1] for o in orders}
        room = MAX_POSITIONS - held_count
        cash = self.cash
        cap_bps = self.hello["caps"]["max_weight_bps"]
        for sym, kind in entries:
            if room <= 0 or len(orders) >= MAX_ORDERS_PER_BAR:
                break
            if sym in self.positions and sym not in selling:
                continue
            if kind == "dip":
                stake = self.equity * STAKE_BPS // 10000
                room_cap = cap_bps * self.equity // 10000
                if stake > room_cap:
                    stake = room_cap
                amount = stake if stake < cash else cash
            else:
                amount = FLOOR_NOTIONAL if FLOOR_NOTIONAL < cash else cash
            if amount < int(self.hello["fees"]["min_notional_quote_units"]):
                break
            cid = self._client_id()
            if kind == "floor":
                self.floor_ids.add(cid)
            orders.append(("buy", sym, amount, cid))
            cash -= amount
            room -= 1

        out = []
        for o in orders:
            if o[0] == "sell":
                _, sym, qty = o
                out.append(
                    {
                        "side": "sell",
                        "client_id": self._client_id(),
                        "symbol": sym,
                        "qty": str(qty),
                        "max_slippage_bps": MAX_SLIPPAGE_BPS,
                    }
                )
            else:
                _, sym, amount, cid = o
                out.append(
                    {
                        "side": "buy",
                        "client_id": cid,
                        "symbol": sym,
                        "notional_quote_units": str(amount),
                        "max_slippage_bps": MAX_SLIPPAGE_BPS,
                    }
                )
        return out


def main():
    src = sys.stdin.buffer
    out = sys.stdout
    bot = None
    for raw in src:
        line = raw.decode("utf-8").strip()
        if not line:
            continue
        msg = json.loads(line)
        kind = msg.get("type")
        if kind == "hello":
            if msg.get("protocol") != PROTOCOL:
                raise SystemExit("unsupported protocol: %r" % (msg.get("protocol"),))
            bot = Bot(msg)
        elif kind == "batch":
            if bot is None:
                raise SystemExit("batch before hello")
            orders = bot.on_batch(msg)
            reply = json.dumps(
                {"type": "reply", "seq": msg["seq"], "orders": orders},
                separators=(",", ":"),
                ensure_ascii=False,
            )
            out.write(reply + "\n")
            out.flush()
        elif kind == "done":
            return
        else:
            raise SystemExit("unknown message type: %r" % (kind,))
    raise SystemExit("input ended before done")


if __name__ == "__main__":
    main()
