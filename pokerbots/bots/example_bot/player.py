'''
Example HopAI Pokerbots submission.

Copy this entire folder (including skeleton/) to bots/<your_team_name>/
and implement your strategy in get_action().
'''
from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import GameState, TerminalState, RoundState
from skeleton.states import NUM_ROUNDS, STARTING_STACK, BIG_BLIND, SMALL_BLIND
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot


class Player(Bot):

    def __init__(self):
        pass

    def handle_new_round(self, game_state, round_state, active):
        # game_state.bankroll     — cumulative chips won/lost so far
        # game_state.round_num    — current round (1 to NUM_ROUNDS)
        # round_state.hands[active] — your two hole cards
        pass

    def handle_round_over(self, game_state, terminal_state, active):
        # terminal_state.deltas[active] — chips won/lost this round
        # terminal_state.previous_state — RoundState when hand ended
        pass

    def get_action(self, game_state, round_state, active):
        '''
        Return your action here. Called every time it's your turn.

        Useful fields:
          round_state.legal_actions()          — set of legal action types
          round_state.hands[active]            — your hole cards
          round_state.deck[:round_state.street]— board cards revealed so far
          round_state.pips[active]             — your chips in pot this street
          round_state.pips[1-active]           — opponent chips in pot
          round_state.stacks[active]           — your remaining stack
          round_state.raise_bounds()           — (min_raise, max_raise)
          game_state.bankroll                  — running total
        '''
        legal_actions = round_state.legal_actions()

        # ── Your strategy goes here ────────────────────────────────
        # This default bot always checks or calls (never folds or raises).
        if CheckAction in legal_actions:
            return CheckAction()
        return CallAction()


if __name__ == '__main__':
    run_bot(Player(), parse_args())
