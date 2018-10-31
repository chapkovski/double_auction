from otree.api import (
    models, widgets, BaseConstants, BaseSubsession, BaseGroup, BasePlayer,
    Currency as c, currency_range
)
from django.db import models as djmodels
import random
from django.db.models.signals import post_save, pre_save
from django.db.models import Q
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from django.core.exceptions import ObjectDoesNotExist
from channels import Group as ChannelGroup
import json
from .exceptions import NotEnoughFunds, NotEnoughItemsToSell

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
            for b in g.get_buyers():
                b.endowment = random.randrange(100, 200)
            for c in g.get_sellers():
                for i in range(10):
                    c.repos.create(quantity=1, cost=random.randint(0, 10))
                for i in range(10):
                    c.asks.create(price=random.randrange(3, 6), quantity=1)
                    # todo: think about quantity

            for b in g.get_buyers():
                for i in range(10):
                    b.bids.create(price=random.randrange(0, 5), quantity=1)


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
        return self.repos.all()

    def get_repo_html(self):
        repository = self.get_repo()
        return mark_safe(render_to_string('double_auction/includes/repo_to_render.html', {
            'repository': repository
        }))

    def get_form_context(self):
        if self.role() == 'buyer':
            no_statements = not self.get_bids().exists()
            no_repo_or_funds = self.endowment is None or self.endowment <= 0
        else:
            no_repo_or_funds = not self.get_repo().exists()
            no_statements = not self.get_asks().exists()
        return {'no_repo_or_funds': no_repo_or_funds,
                'no_statements': no_statements, }

    def get_form_html(self):
        context = self.get_form_context()
        context['player'] = self
        return mark_safe(render_to_string('double_auction/includes/form_to_render.html', context))

    def get_contracts(self):
        return Contract.objects.filter(Q(bid__player=self) | Q(ask__player=self))

    def get_bids(self):
        return self.bids.all()

    def get_asks(self):
        return self.asks.all()

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
            # todo: if repos do not exist return something
            print('RRRRR', repos)
            return repos[0]

    def get_personal_channel_name(self):
        return '{}_{}'.format(self.role(), self.id)


class BaseRecord(djmodels.Model):
    quantity = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    player = djmodels.ForeignKey(to=Player,
                                 related_name="%(class)ss", )

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
    @classmethod
    def pre_save(cls, sender, instance, *args, **kwargs):
        if instance.player.get_repo().count() < int(instance.quantity):
            raise NotEnoughItemsToSell

    # TODO: move both sginsls (ask, bid) under one method
    @classmethod
    def post_save(cls, sender, instance, created, *args, **kwargs):
        if not created:
            return
        group = instance.player.group
        bids = Bid.active_statements.filter(player__group=group, price__gte=instance.price).order_by('created_at')
        if bids.exists():
            bid = bids.last()  ## think about it??
            item = instance.player.item_to_sell()
            if item:
                # we convert to float because in the bd decimals are stored as strings (at least in post_save they are)
                c = Contract.create(bid=bid,
                                    ask=instance,
                                    price=min([bid.price, float(instance.price)]),
                                    item=item)
            else:
                print('NOTHING TO SELL')


class Bid(BaseStatement):
    @classmethod
    def pre_save(cls, sender, instance, *args, **kwargs):
        if instance.player.endowment <= float(instance.price) * int(instance.quantity):
            raise NotEnoughFunds

    @classmethod
    def post_save(cls, sender, instance, created, *args, **kwargs):
        if not created:
            return
        group = instance.player.group
        asks = Ask.active_statements.filter(player__group=group, price__lte=instance.price).order_by('created_at')
        if asks.exists():
            ask = asks.last()  ## think about it??
            # todo: redo all this mess
            item = ask.player.item_to_sell()
            print('******', item)
            if item:
                c = Contract.create(bid=instance,
                                    ask=ask,
                                    price=min([float(instance.price), ask.price]),
                                    item=item)
            else:
                # todo: deal with it
                print('NOTHING TO SELL')


class Repo(BaseRecord):
    cost = models.FloatField()
    value = models.FloatField()


class Contract(djmodels.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    item = djmodels.ForeignKey(to=Repo)
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
    def create(cls, item, bid, ask, price):
        contract = cls(item=item, bid=bid, ask=ask, price=price)
        bid.active = False
        ask.active = False
        item.player = bid.player
        ask.save()
        bid.save()
        item.save()
        contract_parties = [ask.player, bid.player]
        for p in contract_parties:
            group = ChannelGroup(p.get_personal_channel_name())
            group.send(
                {'text': json.dumps({
                    'repo': p.get_repo_html()
                })}
            )
        return contract


post_save.connect(Ask.post_save, sender=Ask)
post_save.connect(Bid.post_save, sender=Bid)
pre_save.connect(Ask.pre_save, sender=Ask)
pre_save.connect(Bid.pre_save, sender=Bid)
