from otree.api import (
    models, widgets, BaseConstants, BaseSubsession, BaseGroup, BasePlayer,
    Currency as c, currency_range
)
from django.db import models as djmodels
import random

author = 'Philipp Chapkovski (c) 2018 , Higher School of Economics, Moscow.' \
         'Chapkovski@gmail.com'

doc = """
A double auction for oTree.
A working paper with description is available here: http://chapkovski.github.io
Instructions are mostly taken from http://veconlab.econ.virginia.edu/da/da.php, Virginia University.
"""


class Constants(BaseConstants):
    name_in_url = 'double_auction'
    players_per_group = 3
    num_rounds = 1
    units_per_seller = 3
    units_per_buyer = 3
    time_per_round = 30
    multiple_unit_trading = True


class Subsession(BaseSubsession):
    def creating_session(self):
        for p in self.get_players():
            ask = p.asks.create(price=random.random(), quantity=random.randint(0, 10))
            bid = p.bids.create(price=random.random(), quantity=random.randint(0, 10))
        for g in self.get_groups():
            for c in g.get_sellers():
                c.sellerrepositorys.create(cost=random.random(), quantity=random.randint(0, 10))
            for b in g.get_buyers():
                b.buyerrepositorys.create(value=random.random(), quantity=random.randint(0, 10))

        for p in self.get_players():
            if p.role() == 'buyer':

                print('AAAA', p.buyerrepositorys.all())


class Group(BaseGroup):
    def get_players_by_role(self, role):
        return [p for p in self.get_players() if p.role() == role]

    def get_buyers(self):
        return self.get_players_by_role('buyer')

    def get_sellers(self):
        return self.get_players_by_role('seller')


class Player(BasePlayer):
    endowment = models.CurrencyField()

    def role(self):
        if self.id_in_group == 1:
            return 'seller'
        else:
            return 'buyer'


class BaseRecord(djmodels.Model):
    player = djmodels.ForeignKey(
        to=Player,
        related_name="%(class)ss",
    )

    quantity = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseStatement(BaseRecord):
    price = models.FloatField()

    class Meta:
        abstract = True

    def __str__(self):
        return '{}. Price:{}, Quantity:{}. Created at: {}. Updated at: {}'. \
            format(self.__class__.__name__, self.price, self.quantity, self.created_at, self.updated_at)


class Ask(BaseStatement):
    pass


class Bid(BaseStatement):
    pass


class SellerRepository(BaseRecord):
    cost = models.FloatField()
    sold = models.BooleanField(initial=False)


class BuyerRepository(BaseRecord):
    value = models.FloatField()


class Contracts(djmodels.Model):
    bid = djmodels.ForeignKey(to=Bid)
    ask = djmodels.ForeignKey(to=Ask)
    quantity = models.IntegerField()
    price = models.FloatField()
