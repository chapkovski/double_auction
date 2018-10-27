from otree.api import Currency as c, currency_range
from ._builtin import Page, WaitPage
from .models import Constants
import random


class Market(Page):
    def vars_for_template(self):
        bidsize, asksize = random.randint(4,10),random.randint(4,10)
        a = random.sample(range(100), bidsize)
        b = random.sample(range(100), bidsize)
        bids=zip(a, b)
        a = random.sample(range(100), asksize)
        b = random.sample(range(100), asksize)
        asks= zip(a, b)
        repsize = random.randint(3,6)
        a = random.sample(range(100), repsize)
        b = random.sample(range(100), repsize)
        c = random.sample(range(100), repsize)

        repository= zip(a, b,c)
        return {
            'bids': bids,
            'asks':asks,
            'repository':repository
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
