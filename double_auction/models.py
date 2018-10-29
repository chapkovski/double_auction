from otree.api import (
    models, widgets, BaseConstants, BaseSubsession, BaseGroup, BasePlayer,
    Currency as c, currency_range
)
from django.db import models as djmodels
import random
from django.db.models.signals import post_save
from django.db.models import Q
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from django.core.exceptions import ObjectDoesNotExist

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
    price_max_numbers = 10
    price_digits = 2


class Subsession(BaseSubsession):
    def creating_session(self):

        for g in self.get_groups():
            for c in g.get_sellers():
                for i in range(10):
                    c.asks.create(price=random.random(), quantity=random.randint(0, 10))

            for b in g.get_buyers():
                for i in range(10):
                    b.bids.create(price=random.random(), quantity=random.randint(0, 10))


class Group(BaseGroup):
    def get_channel_group_name(self):
        return 'double_auction_group_{}'.format(self.pk)

    def get_players_by_role(self, role):
        return [p for p in self.get_players() if p.role() == role]

    def get_buyers(self):
        return self.get_players_by_role('buyer')

    def get_sellers(self):
        return self.get_players_by_role('seller')

    def get_contracts(self):
        return Contract.objects.filter(Q(bid__player__group=self) | Q(ask__player__group=self))

    def get_bids(self):
        return Bid.active_statements.filter(player__in=self.get_buyers()).order_by('-created_at')

    def get_asks(self):
        return Ask.active_statements.filter(player__in=self.get_sellers()).order_by('-created_at')

    def get_bids_html(self):
        bids = self.get_bids()
        return mark_safe(render_to_string('double_auction/includes/bids_to_render.html', {
            'bids': bids
        }))

    def get_asks_html(self):
        asks = self.get_asks()
        return mark_safe(render_to_string('double_auction/includes/asks_to_render.html', {
            'asks': asks
        }))

    def get_spread_html(self):
        return mark_safe(render_to_string('double_auction/includes/spread_to_render.html', {
            'group': self,
        }))

    def non_empty_buyer_exists(self) -> bool:
        ...

    def non_empty_seller_exists(self) -> bool:
        ...

    def is_market_closed(self) -> bool:
        return not all(self.non_empty_buyer_exists(), self.non_empty_seller_exists())

    def best_ask(self):
        bests = self.get_asks().order_by('-price')
        if bests.exists():
            return bests.first()

    def best_bid(self):
        bests = self.get_bids().order_by('price')
        if bests.exists():
            return bests.first()


class Player(BasePlayer):
    endowment = models.CurrencyField()

    def role(self):
        if self.id_in_group == 1:
            return 'seller'
        else:
            return 'buyer'

    def get_contracts(self):
        return Contract.objects.filter(Q(bid__player=self) | Q(ask__player=self))

    def get_bids(self):
        ...

    def get_asks(self):
        ...

    def is_buyer_repository_available(self):
        ...

    def seller_has_money(self):
        ...

    def action_name(self):
        if self.role() == 'buyer':
            return 'bid'
        return 'ask'

    def get_last_statement(self):
        try:
            if self.role() == 'seller':
                return self.asks.filter(active=True).latest('created_at')
            else:
                return self.bids.filter(active=True).latest('created_at')
        except ObjectDoesNotExist:
            # todo: think a bit what happens if last bid is non existent?
            return


class Base(djmodels.Model):
    quantity = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseRecord(Base):
    player = djmodels.ForeignKey(
        to=Player,
        related_name="%(class)ss",
    )

    class Meta:
        abstract = True


class ActiveStatementManager(djmodels.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(active=True)


class BaseStatement(BaseRecord):
    price = djmodels.DecimalField(max_digits=Constants.price_max_numbers, decimal_places=Constants.price_digits)
    # initially all bids and asks are active. when the contracts are created with their participation they got passive
    active = models.BooleanField(initial=True)
    active_statements = ActiveStatementManager()

    class Meta:
        abstract = True

    def __str__(self):
        return '{}. Price:{}, Quantity:{}. Created at: {}. Updated at: {}'. \
            format(self.__class__.__name__, self.price, self.quantity, self.created_at, self.updated_at)

    def as_dict(self):
        return {'price': str(self.price),
                'quantity': self.quantity}


class Ask(BaseStatement):
    pass


class Bid(BaseStatement):
    pass


class SellerRepository(BaseRecord):
    cost = models.FloatField()
    sold = models.BooleanField(initial=False)


class BuyerRepository(BaseRecord):
    value = models.FloatField()


class Contract(Base):
    bid = djmodels.ForeignKey(to=Bid)
    ask = djmodels.ForeignKey(to=Ask)
    price = djmodels.DecimalField(max_digits=Constants.price_max_numbers, decimal_places=Constants.price_digits)

    @classmethod
    def post_create(cls, sender, instance, created, *args, **kwargs):
        if not created:
            return
        # when contract is created bid and ask that are involved get passive
        instance.bid.active = False
        instance.bid.save()
        instance.ask.active = False
        instance.save()


post_save.connect(Contract.post_create, sender=Contract)
