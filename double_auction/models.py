from otree.api import (
    models, widgets, BaseConstants, BaseSubsession, BaseGroup, BasePlayer,
    Currency as c, currency_range
)
import random
import json
from django.db import models as djmodels
from django.db.models import F, Q, Sum, ExpressionWrapper
from django.db.models.signals import post_save, pre_save

from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from django.core.exceptions import ObjectDoesNotExist
from channels import Group as ChannelGroup

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
    initial_quantity = 1  # TODO: to change later for multiple quantities


class Subsession(BaseSubsession):
    def creating_session(self):
        for g in self.get_groups():
            for c in g.get_sellers():
                # we create slots for both sellers and buyers, but for sellers we fill them with items
                # and also pregenerate costs. For buyers they are initially empty
                for i in range(Constants.units_per_seller):
                    slot = c.slots.create(cost=random.randint(0, 10))
                    item = Item(slot=slot, quantity=Constants.initial_quantity)
                    item.save()

            for b in g.get_buyers():
                for i in range(Constants.units_per_buyer):
                    b.endowment = random.randrange(100, 200)
                    b.slots.create(value=random.randint(0, 10))


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

    def get_items(self):
        return Item.objects.filter(slot__owner=self)

    def get_slots(self):
        return self.slots.all()

    def has_free_slots(self):
        return self.slots.filter(item__isnull=True).exists()

    def get_free_slot(self):
        if self.has_free_slots():
            return self.slots.filter(item__isnull=True).order_by('-value').first()

    def get_full_slots(self):
        return self.slots.filter(item__isnull=False)

    def get_repo_context(self):
        repository = self.get_slots()
        if self.role() == 'seller':
            r = repository.annotate(price=F('item__contract__price'),
                                    profit=ExpressionWrapper(
                                        (F('item__contract__price') - F('cost')) * F('item__quantity'),
                                        output_field=models.FloatField()),
                                    quantity=F('item__quantity'),
                                    ).order_by('cost')

        else:
            r = repository.annotate(price=F('item__contract__price'),
                                    profit=ExpressionWrapper(
                                        (F('value') - F('item__contract__price')) * F('item__quantity'),
                                        output_field=models.FloatField()),
                                    quantity=F('item__quantity'),
                                    ).order_by('value')

        return r

    def get_repo_html(self):

        return mark_safe(render_to_string('double_auction/includes/repo_to_render.html', {
            'repository': self.get_repo_context()
        }))

    def get_form_context(self):
        if self.role() == 'buyer':
            no_statements = not self.get_bids().exists()
            no_slots_or_funds = self.endowment <= 0 or not self.has_free_slots()
        else:
            no_slots_or_funds = not self.get_full_slots().exists()
            no_statements = not self.get_asks().exists()
        return {'no_slots_or_funds ': no_slots_or_funds,
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
        full_slots = self.get_full_slots().order_by('cost')
        if full_slots.exists():
            return full_slots.first().item

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
        num_items_available = Item.objects.filter(slot__owner=instance.player).aggregate(num_items=Sum('quantity'))
        if num_items_available['num_items'] < int(instance.quantity):
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
                Contract.create(bid=bid,
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
            if item:
                Contract.create(bid=instance,
                                ask=ask,
                                price=min([float(instance.price), ask.price]),
                                item=item)
            else:
                # todo: deal with it
                print('NOTHING TO SELL')


class Slot(djmodels.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = djmodels.ForeignKey(to=Player, related_name="slots", )
    cost = models.FloatField(doc='this is defined for sellers only', null=True)
    value = models.FloatField(doc='for buyers only', null=True)


class Item(djmodels.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    slot = djmodels.OneToOneField(to=Slot, related_name='item')
    quantity = models.IntegerField()


class Contract(djmodels.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # the o2o field to item should be reconsidered if we make quantity flexible
    item = djmodels.OneToOneField(to=Item)
    bid = djmodels.OneToOneField(to=Bid)
    ask = djmodels.OneToOneField(to=Ask)
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
        buyer = bid.player
        seller = ask.player
        if buyer.has_free_slots():
            item.slot = buyer.get_free_slot()
        ask.save()
        bid.save()
        item.save()
        contract_parties = [buyer, seller]
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
