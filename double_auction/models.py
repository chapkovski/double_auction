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
    time_per_round = 30000
    multiple_unit_trading = True
    price_max_numbers = 10
    price_digits = 2


class Subsession(BaseSubsession):
    def creating_session(self):

        for g in self.get_groups():
            for c in g.get_sellers():
                for i in range(100):
                    c.sellerrepositorys.create(quantity=1, cost=random.randint(0, 10))
                for i in range(10):
                    c.asks.create(price=random.random(), quantity=random.randint(0, 10))
                    # todo: think about quantity

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
        return Bid.active_statements.filter(player__group=self).order_by('-created_at')

    def get_asks(self):
        return Ask.active_statements.filter(player__group=self).order_by('-created_at')

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
        bests = self.get_asks().order_by('price')
        if bests.exists():
            return bests.first()

    def best_bid(self):
        bests = self.get_bids().order_by('price')
        if bests.exists():
            return bests.last()


class Player(BasePlayer):
    endowment = models.CurrencyField()

    def role(self):
        if self.id_in_group == 1:
            return 'seller'
        else:
            return 'buyer'

    def get_repo(self):
        return self.sellerrepositorys.filter(sold=False)

    def get_repo_html(self):
        ...

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

    def item_to_sell(self):
        repos = self.get_repo()
        if repos.exists():
            # todo: think about sorting here
            # todo: if repos do not exist return someting
            print('RRRRR', repos)
            return repos[0]


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
    # TODO: move both sginsls (ask, bid) under one method
    @classmethod
    def post_create(cls, sender, instance, created, *args, **kwargs):
        if not created:
            return
        print('IM IN SIGNAL!! of ASK')
        group = instance.player.group
        bids = Bid.active_statements.filter(player__group=group, price__gte=instance.price).order_by('created_at')
        if bids.exists():
            bid = bids.last()  ## think about it??
            item = instance.player.item_to_sell()
            print('&&&&&&&&&', item)
            # we convert to float because in the bd decimals are stored as strings (at least in post_save they are)
            c = Contract(bid=bid,
                         ask=instance,
                         price=min([bid.price, float(instance.price)]),
                         item=item)
            instance.active = False
            bid.active = False
            item.sold = True
            instance.save()
            bid.save()
            item.save()


class Bid(BaseStatement):
    @classmethod
    def post_create(cls, sender, instance, created, *args, **kwargs):
        if not created:
            return
        group = instance.player.group
        asks = Ask.active_statements.filter(player__group=group, price__lte=instance.price).order_by('created_at')
        if asks.exists():
            ask = asks.last()  ## think about it??
            # todo: redo all this mess
            item = ask.player.item_to_sell()
            print('******', item)
            Contract(bid=instance,
                     ask=ask,
                     price=min([float(instance.price), ask.price]),
                     item=instance.player.item_to_sell())
            instance.active = False
            ask.active = False
            item.sold = True
            instance.save()
            ask.save()
            item.save()


class SellerRepository(BaseRecord):
    cost = models.FloatField()
    sold = models.BooleanField(initial=False)


class BuyerRepository(BaseRecord):
    value = models.FloatField()


class Contract(djmodels.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    item = djmodels.ForeignKey(to=SellerRepository)
    bid = djmodels.ForeignKey(to=Bid)
    ask = djmodels.ForeignKey(to=Ask)
    price = djmodels.DecimalField(max_digits=Constants.price_max_numbers, decimal_places=Constants.price_digits)

    def get_seller(self):
        return self.ask.player

    def get_buyer(self):
        return self.bid.player

    def __str__(self):
        return '{}. Price:{}, Quantity:{}. BID by: {}. ASK BY: {}'. \
            format(self.__class__.__name__, str(self.price), self.item.quantity, self.bid.player.id, self.ask.player.id)

    @classmethod
    def post_create(cls, sender, instance, created, *args, **kwargs):
        print('IM IN PRE!!! SIGNAL OF CONTRACT!!!!')
        if not created:
            return
        bid, ask, item = instance.bid, instance.ask, instance.item
        print('IM IN SIGNAL OF CONTRACT!!!!')
        bid.active = False
        ask.active = False
        item.sold = True
        ask.save()
        bid.save()
        item.save()


post_save.connect(Ask.post_create, sender=Ask)
post_save.connect(Bid.post_create, sender=Bid)
# post_save.connect(Contract.post_create, sender=Contract)
