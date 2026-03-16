# HopAI Pokerbots — Player Guide

Welcome to the HopAI Pokerbots competition! You'll write a Python bot that plays **heads-up No-Limit Texas Hold'em** against every other team's bot. The bot with the most chips at the end wins.

---

## Table of Contents

1. [How the game works](#1-how-the-game-works)
2. [Getting started](#2-getting-started)
3. [Bot API reference](#3-bot-api-reference)
4. [Example strategies](#4-example-strategies)
5. [Testing your bot](#5-testing-your-bot)
6. [How to submit](#6-how-to-submit)
7. [Tournament format and scoring](#7-tournament-format-and-scoring)
8. [Rules](#8-rules)
9. [Tips and strategy](#9-tips-and-strategy)
10. [FAQ](#10-faq)

---

## 1. How the game works

Each match is **1 000 hands** of heads-up No-Limit Texas Hold'em between two bots.

| Setting | Value |
|---------|-------|
| Starting stack | 400 chips |
| Small blind | 1 chip |
| Big blind | 2 chips |
| Hands per match | 1 000 |
| Game clock | 30 seconds total per bot |

### Street order

```
Preflop → Flop (3 cards) → Turn (1 card) → River (1 card) → Showdown
```

- Positions swap every hand.
- The small blind acts **first preflop**, **last postflop**.
- Min raise = previous bet + max(previous bet, big blind).
- If a player runs out of game clock, all future actions default to check/fold.

---

## 2. Getting started

### Requirements

```
Python 3.8+
eval7          (pip install eval7)
```

### Download the template

Ask the organizer for the starter zip, or download it from the submission page. Unzip it:

```
my_team/
├── player.py        ← implement your strategy here
├── commands.json    ← tells the engine how to run your bot
└── skeleton/        ← game library (do not modify)
    ├── actions.py
    ├── states.py
    ├── bot.py
    └── runner.py
```

`commands.json` should look like this — don't change it unless you know what you're doing:

```json
{
    "build": [],
    "run": ["python3", "player.py"]
}
```

---

## 3. Bot API reference

Your bot is a class that extends `Bot`. Implement these three methods:

### `handle_new_round(game_state, round_state, active)`

Called at the start of every hand. Use it to reset per-hand state.

```python
def handle_new_round(self, game_state, round_state, active):
    my_bankroll = game_state.bankroll   # chips won/lost so far this game
    round_num   = game_state.round_num  # 1 to 1000
    my_cards    = round_state.hands[active]  # your two hole cards
    big_blind   = bool(active)          # True if you are the big blind
```

### `handle_round_over(game_state, terminal_state, active)`

Called at the end of every hand. Use it to track opponent tendencies.

```python
def handle_round_over(self, game_state, terminal_state, active):
    my_delta     = terminal_state.deltas[active]    # chips won(+) or lost(-) this hand
    prev         = terminal_state.previous_state    # RoundState when hand ended
    street       = prev.street                      # 0=preflop, 3=flop, 4=turn, 5=river
    opp_cards    = prev.hands[1 - active]           # opponent's cards ([] if not shown)
```

### `get_action(game_state, round_state, active)` ← **the main one**

Called every time it's your turn. **Must return an action.**

```python
def get_action(self, game_state, round_state, active):
    legal_actions = round_state.legal_actions()
    # Returns a set containing any of: {CheckAction, CallAction, FoldAction, RaiseAction}

    street      = round_state.street          # 0=preflop 3=flop 4=turn 5=river
    my_cards    = round_state.hands[active]   # list of 2 eval7.Card objects
    board_cards = round_state.deck[:street]   # list of board cards revealed so far

    my_pip      = round_state.pips[active]    # chips I've put in this betting round
    opp_pip     = round_state.pips[1-active]  # chips opponent has put in
    my_stack    = round_state.stacks[active]  # my remaining chips
    opp_stack   = round_state.stacks[1-active]

    continue_cost = opp_pip - my_pip          # cost to stay in (0 if checked to you)
    pot_size      = (400 - my_stack) + (400 - opp_stack)  # total chips in play

    if RaiseAction in legal_actions:
        min_raise, max_raise = round_state.raise_bounds()
        return RaiseAction(min_raise)   # or any amount in [min_raise, max_raise]

    if CheckAction in legal_actions:
        return CheckAction()

    return CallAction()
```

### Actions

| Action | When available | Notes |
|--------|----------------|-------|
| `CheckAction()` | No bet to call | Free pass |
| `CallAction()` | Facing a bet/raise | Matches opponent's bet |
| `FoldAction()` | Facing a bet/raise | Forfeits the hand |
| `RaiseAction(amount)` | When either player can afford it | `amount` = **total** chips you're putting in this street, must be in `[min_raise, max_raise]` |

### Working with cards

Cards are `eval7.Card` objects. Access them like strings:

```python
card = my_cards[0]
str(card)       # e.g. "Ah" (Ace of hearts), "Td" (Ten of diamonds)
card.rank       # 'A', 'K', 'Q', 'J', 'T', '9', ..., '2'
card.suit       # 'h', 'd', 'c', 's'
```

Evaluate hand strength with eval7 (higher = stronger):

```python
import eval7

score = eval7.evaluate(board_cards + my_cards)  # needs exactly 7 cards
```

---

## 4. Example strategies

### Minimum viable bot (check/call everything)

```python
def get_action(self, game_state, round_state, active):
    legal_actions = round_state.legal_actions()
    if CheckAction in legal_actions:
        return CheckAction()
    return CallAction()
```

### Tight-aggressive: only play premium hands preflop

```python
PREMIUM = {('A','A'),('K','K'),('Q','Q'),('J','J'),
           ('A','K'),('A','Q'),('K','Q')}

def get_action(self, game_state, round_state, active):
    legal_actions = round_state.legal_actions()

    if round_state.street == 0:   # preflop
        ranks = tuple(sorted([str(c)[0] for c in round_state.hands[active]], reverse=True))
        if ranks in PREMIUM:
            if RaiseAction in legal_actions:
                _, max_r = round_state.raise_bounds()
                return RaiseAction(max_r // 2)   # half-pot raise
            return CallAction()
        # Weak hand
        if CheckAction in legal_actions:
            return CheckAction()
        return FoldAction()

    # Postflop: check/call
    if CheckAction in legal_actions:
        return CheckAction()
    return CallAction()
```

### Using eval7 for Monte Carlo equity estimation

```python
import eval7, random

def estimate_equity(hole, board, n=300):
    known = set(str(c) for c in hole + board)
    wins = 0
    for _ in range(n):
        deck = eval7.Deck()
        deck.shuffle()
        opp, fill = [], []
        for card in deck.cards:
            if str(card) in known:
                continue
            if len(opp) < 2:       opp.append(card)
            elif len(fill) < 5 - len(board): fill.append(card)
            if len(opp) == 2 and len(fill) == 5 - len(board):
                break
        full_board = board + fill
        mine = eval7.evaluate(full_board + hole)
        theirs = eval7.evaluate(full_board + opp)
        wins += 1 if mine > theirs else (0.5 if mine == theirs else 0)
    return wins / n

def get_action(self, game_state, round_state, active):
    legal_actions = round_state.legal_actions()
    hole  = list(round_state.hands[active])
    board = list(round_state.deck[:round_state.street])

    if board:   # only compute postflop
        equity = estimate_equity(hole, board)
        if equity > 0.6 and RaiseAction in legal_actions:
            min_r, max_r = round_state.raise_bounds()
            return RaiseAction(min_r)
        if equity < 0.35 and FoldAction in legal_actions:
            return FoldAction()

    if CheckAction in legal_actions:
        return CheckAction()
    return CallAction()
```

> **Clock warning:** Monte Carlo runs fast for 300 iterations (~1–2 ms) but you have only **30 seconds total** for the whole 1 000-hand game. Budget ~25 ms per decision maximum.

---

## 5. Testing your bot

### Run two bots against each other locally

From the `engine/` directory:

```bash
# Edit config.py to point to your two bots, then:
python engine.py
```

A `gamelog.txt` will appear in `engine/` with the full hand history.

### Self-play

Point both `PLAYER_1_PATH` and `PLAYER_2_PATH` in `engine/config.py` to the same bot folder to test it against itself.

### Timing your bot

```python
import time

def get_action(self, game_state, round_state, active):
    t0 = time.perf_counter()
    # ... your logic ...
    elapsed = time.perf_counter() - t0
    if elapsed > 0.02:
        print(f"WARNING: action took {elapsed:.3f}s", flush=True)
    return action
```

---

## 6. How to submit

### Step 1 — Get the URL from the organizer

When the organizer runs `python app.py`, their terminal prints something like:

```
│  Participants:  http://10.203.209.138:9000  │
```

That's the URL you open in your browser. **You must be on the same WiFi network** as the organizer's laptop. Ask them if you're unsure.

### Step 2 — Open the submission page

Go to `http://<that-ip>:<port>/submit` in any browser. You'll see the submission form.

### Step 3 — Zip your bot

Your zip must contain exactly two files at the top level:

```
my_team.zip
├── player.py        ← your bot code
└── commands.json    ← {"build":[],"run":["python3","player.py"]}
```

To create the zip:

```bash
# Mac / Linux — run this inside your bot folder
zip -j my_team.zip player.py commands.json

# Windows (PowerShell) — run this inside your bot folder
Compress-Archive -Path player.py,commands.json -DestinationPath my_team.zip
```

> Only `.py` and `.json` files are accepted. Do **not** include `skeleton/` — it is added automatically on the server.

### Step 4 — Submit

1. Type your team name (e.g. `team_rockets` — letters/numbers/underscores only)
2. Drag your zip onto the upload box, or click to browse
3. Click **Submit Bot**

You'll see a green confirmation message. **You can resubmit as many times as you want** before the tournament starts — only the latest submission is used.

### Check your submission

Once submitted, your team name will appear in the "Registered bots" list on the `/submit` page, and in the bot count on the main dashboard.

---

## 7. Tournament format and scoring

- **Format:** Round-robin — every bot plays every other bot **twice** (once as small blind, once as big blind).
- **Scoring:** Ranked by **total net chips** accumulated across all matches.
- **Tiebreaker:** Win count.
- **Match result:** The bot with more chips after 1 000 hands wins that match.
- **Example with 8 teams:** 8×7 = 56 total matches.

The live leaderboard updates after every match at the dashboard URL.

---

## 8. Rules

1. Your bot must respond within the per-hand clock budget. If you run out of time, all future actions default to check/fold. **You cannot recover lost clock.**
2. Only the files you submit are available to your bot. No internet access, no reading opponent files.
3. Bots may not hard-code match-specific data (e.g. pre-computed ranges per opponent are fine; reading the game log file during a match is not).
4. Any bot that crashes or fails to connect is forfeited for that match.
5. No modifying the `skeleton/` library.
6. The organizer's engine result is final.

---

## 9. Tips and strategy

### Think in expected value, not single hands

You play 1 000 hands. Variance evens out. A strategy that wins 0.5 chips/hand beats one that occasionally wins big but is losing overall.

### Preflop hand selection matters a lot

In heads-up, you're forced to play roughly 50% of pots (as the big blind you've already invested). The key question preflop is: **am I getting the right price to continue?**

### Track opponent tendencies

`handle_round_over` gives you the opponent's cards when there's a showdown. Log their bet sizes, which hands they showed down with, and adjust.

```python
def __init__(self):
    self.opp_showdowns = []   # (their cards, their bets)

def handle_round_over(self, game_state, terminal_state, active):
    opp_cards = terminal_state.previous_state.hands[1 - active]
    if opp_cards:   # they showed a hand
        self.opp_showdowns.append(opp_cards)
```

### Pot odds

Before calling a bet, check if the pot odds justify it:

```python
continue_cost = opp_pip - my_pip
pot           = (400 - my_stack) + (400 - opp_stack)
pot_odds      = continue_cost / (pot + continue_cost)
# Call if your equity > pot_odds
```

### Be careful with the game clock

- 30 seconds / 1 000 hands = **30 ms average per hand** (including all streets).
- A hand has at most ~8 betting decisions. That's ~3–4 ms per `get_action()` call.
- Monte Carlo at 200–300 iterations is fine. Anything heavier needs caching or precomputation.

---

## 10. FAQ

**Q: Can I use external libraries?**
Yes — anything that's pip-installable and available on the machine. `eval7` is pre-installed. If you need something else, contact the organizer.

**Q: Can my bot print debug output?**
Yes. Anything printed to stdout is saved to a log file (not visible to opponents). Use `print(..., flush=True)`.

**Q: What happens if my bot crashes mid-match?**
It forfeits the match. The opponent wins by default (bankroll = whatever chips were in play).

**Q: Can I submit multiple times?**
Yes. The latest submission before the tournament starts is used.

**Q: Are ties possible?**
Very unlikely with 1 000 hands, but yes. Both bots split the match.

**Q: Can I see the results?**
Yes — watch the live dashboard during the tournament.

---

Good luck! Questions? Find the organizers on the day. 🃏
