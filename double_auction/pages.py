from otree.api import Currency as c, currency_range
from ._builtin import Page, WaitPage
from .models import Constants
import random


class Market(Page):
    timeout_seconds = Constants.time_per_round

    def vars_for_template(self):
        tempasks = [{'price': 1, 'quantity': '2'}, {'price': 1, 'quantity': '2'}]

        return {
            'bids': self.group.get_bids(),
            'asks': self.group.get_asks(),
            'repository': self.player.get_repo()
        }


class ResultsWaitPage(WaitPage):
    def after_all_players_arrive(self):
        pass


class Results(Page):
    pass


page_sequence = [
    Market,
    ResultsWaitPage,
    Results
]
