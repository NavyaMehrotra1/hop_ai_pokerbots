'''
balanced — Tight-Aggressive (TAG)

Preflop:
  - Premium hands (AA/KK/QQ/AK/AQ): raise 3x big blind
  - Playable hands (pairs 77+, broadway): call
  - Everything else: fold to any bet, check for free

Postflop:
  - Uses Monte Carlo simulation (eval7) to estimate equity
  - >65% equity: raise to 60% of pot
  - >45% equity: call
  - Otherwise: fold (or check for free)
'''
import random
import eval7

from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import GameState, TerminalState, RoundState
from skeleton.states import STARTING_STACK, BIG_BLIND
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot

RANK_ORDER = '23456789TJQKA'


def card_rank(card):
    return RANK_ORDER.index(str(card)[0])


def is_premium(hole):
    '''AA, KK, QQ, JJ, AK, AQ, KQ (any suit).'''
    r0, r1 = sorted([card_rank(c) for c in hole], reverse=True)
    # Pocket pair TT+
    if r0 == r1 and r0 >= RANK_ORDER.index('T'):
        return True
    # AK, AQ, KQ
    if r0 == 12 and r1 >= RANK_ORDER.index('Q'):
        return True
    return False


def is_playable(hole):
    '''77-99, broadway combos.'''
    r0, r1 = sorted([card_rank(c) for c in hole], reverse=True)
    if r0 == r1 and r0 >= RANK_ORDER.index('7'):
        return True
    if r0 >= RANK_ORDER.index('J') and r1 >= RANK_ORDER.index('T'):
        return True
    return False


def estimate_equity(hole, board, n_sim=200):
    '''Monte Carlo equity vs one random opponent hand.'''
    known = set(str(c) for c in hole + board)
    wins = 0
    for _ in range(n_sim):
        deck = eval7.Deck()
        deck.shuffle()
        # Draw opponent hand and remaining board cards
        remaining_board = []
        opp_hand = []
        for card in deck.cards:
            if str(card) in known:
                continue
            if len(opp_hand) < 2:
                opp_hand.append(card)
            elif len(remaining_board) < (5 - len(board)):
                remaining_board.append(card)
            if len(opp_hand) == 2 and len(remaining_board) == 5 - len(board):
                break
        full_board = board + remaining_board
        my_score  = eval7.evaluate(full_board + hole)
        opp_score = eval7.evaluate(full_board + opp_hand)
        if my_score > opp_score:
            wins += 1
        elif my_score == opp_score:
            wins += 0.5
    return wins / n_sim


class Player(Bot):

    def __init__(self):
        self._preflop_action_taken = False

    def handle_new_round(self, game_state, round_state, active):
        self._preflop_action_taken = False

    def handle_round_over(self, game_state, terminal_state, active):
        pass

    def get_action(self, game_state, round_state, active):
        legal_actions = round_state.legal_actions()
        street = round_state.street
        hole   = round_state.hands[active]
        board  = round_state.deck[:street]

        # ── Preflop ───────────────────────────────────────────────
        if street == 0:
            if is_premium(hole):
                if RaiseAction in legal_actions:
                    min_r, max_r = round_state.raise_bounds()
                    amount = min(min_r + 3 * BIG_BLIND, max_r)
                    return RaiseAction(amount)
                return CallAction()
            if is_playable(hole):
                if CheckAction in legal_actions:
                    return CheckAction()
                return CallAction()
            # Weak hand
            if CheckAction in legal_actions:
                return CheckAction()
            return FoldAction()

        # ── Postflop ──────────────────────────────────────────────
        equity = estimate_equity(list(hole), list(board))

        if equity > 0.65:
            if RaiseAction in legal_actions:
                min_r, max_r = round_state.raise_bounds()
                pot = (STARTING_STACK - round_state.stacks[0]) + (STARTING_STACK - round_state.stacks[1])
                bet = min(max(min_r, int(pot * 0.6)), max_r)
                return RaiseAction(bet)
            if CheckAction in legal_actions:
                return CheckAction()
            return CallAction()

        if equity > 0.45:
            if CheckAction in legal_actions:
                return CheckAction()
            return CallAction()

        if CheckAction in legal_actions:
            return CheckAction()
        return FoldAction()


if __name__ == '__main__':
    run_bot(Player(), parse_args())
