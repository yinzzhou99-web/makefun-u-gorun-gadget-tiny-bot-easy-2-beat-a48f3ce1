# makefun-u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1

[![make.fun · u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1?utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)
[![rank](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/yinzzhou99-web/makefun-u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/rank.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)
[![reward](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/yinzzhou99-web/makefun-u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/reward.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1?utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)

**Tiny Bot, Easy $2: Beat Buy-and-Hold on Solana** — a deterministic hourly-bars
paper-trading bot for FARTCOIN, JITOSOL, POPCAT, RAY, SOL, WETH and WIF.

## Strategy

- **Oversold dip-buying:** RSI(14) at or under 25 buys a 23%-of-equity stake
  (under the 25% per-asset cap). Oversold hours in these Solana markets
  usually bounce within a few bars.
- **Quick exits:** sell the whole position at +1.5% over cost, at −5%, or
  when RSI(14) reaches 60. One stake per symbol, at most seven positions.
- **Activity floor:** the guardrails need at least 8 trades. From batch 48,
  while fewer than 8 of our orders have filled, buy $300 of the asset with
  the best 12-hour return; a floor position exits at +1.5%, −3%, RSI 60,
  or after 8 bars. In a busy window it never fires.
- **Deterministic:** stdlib only, no network, no clock, no randomness — the
  same bars always give the same orders, so the two grading runs match
  byte for byte.

## Results (kit dev window, grade-local)

- Net PnL **+479.78 USDC** vs buy-and-hold −869.34 USDC
- 37 trades, max drawdown 2.0%, 0 rejected orders

## Run

```sh
python3 main.py  # speaks agent-fun/bars-replay/v1 on stdin/stdout
```
