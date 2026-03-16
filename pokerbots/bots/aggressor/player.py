'''
aggressor — Pure Maniac
Always raises to the maximum legal amount.
Obliterates passive bots; bleeds against tight re-raisers.
'''
from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import GameState, TerminalState, RoundState
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot


class Player(Bot):

    def __init__(self):
        pass

    def handle_new_round(self, game_state, round_state, active):
        pass

    def handle_round_over(self, game_state, terminal_state, active):
        pass

    def get_action(self, game_state, round_state, active):
        legal_actions = round_state.legal_actions()

        # Always try to raise to max
        if RaiseAction in legal_actions:
            _, max_raise = round_state.raise_bounds()
            return RaiseAction(max_raise)

        if CheckAction in legal_actions:
            return CheckAction()
        return CallAction()


if __name__ == '__main__':
    run_bot(Player(), parse_args())
