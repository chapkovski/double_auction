from channels.generic.websockets import JsonWebsocketConsumer
import random
from double_auction.models import Constants, Player, Group
import json
from double_auction.exceptions import NotEnoughFunds, NotEnoughItemsToSell


class MarketTracker(JsonWebsocketConsumer):
    url_pattern = (r'^/market_channel/(?P<player_pk>[0-9]+)/(?P<group_pk>[0-9]+)$')

    def clean_kwargs(self):
        self.player_pk = self.kwargs['player_pk']
        self.group_pk = self.kwargs['group_pk']

    def connection_groups(self, **kwargs):
        group_name = self.get_group().get_channel_group_name()
        personal_channel = self.get_player().get_personal_channel_name()
        return [group_name, personal_channel]

    def connect(self, message, **kwargs):
        print('someone connected')

    def disconnect(self, message, **kwargs):
        print('someone disconnected')

    def get_player(self):
        self.clean_kwargs()
        return Player.objects.get(pk=self.player_pk)

    def get_group(self):
        self.clean_kwargs()
        return Group.objects.get(pk=self.group_pk)

    def receive(self, text=None, bytes=None, **kwargs):
        self.clean_kwargs()
        msg = text
        print('WHAT I GOT EHRE???::::  ', msg)
        player = self.get_player()
        group = self.get_group()
        # todo: check if market is not yet closed - if yes, send a signal to proceed for all players
        # todo: check if a buyer has money left. if not, send a signal so he can be forwarded to wp
        # todo: check if a seller has items in repository left. If not, send a signal so he can be forwarded to wp
        # todo: check if contract can be done. If yes, update repo and money for both seller and buyer. Send them
        # ... both some info regarding their repos to update corresponding containers, money/profit/ areas
        # todo: remove bids and asks of passive players (those who have no money or items to sell)
        # todo: validate correct price is inserted
        # todo: config quantity (more than 1 if settings are set for that)

        # todo: syncrhonize timers among the entire group!



        if msg['action'] == 'new_statement':
            if player.role() == 'buyer':
                try:
                    player.bids.create(price=msg['price'], quantity=msg['quantity'])
                except NotEnoughFunds:
                    print('not enough funds')
            else:
                try:
                    player.asks.create(price=msg['price'], quantity=msg['quantity'])
                except NotEnoughItemsToSell:
                    print('not enough items to sell')

        if msg['action'] == 'retract_statement':
            to_del = player.get_last_statement()
            if to_del:
                to_del.delete()
        asks = group.get_asks_html()
        bids = group.get_bids_html()
        spread = group.get_spread_html()
        form = player.get_form_html()
        self.group_send(group.get_channel_group_name(), {'asks': asks,
                                                         'bids': bids,
                                                         'spread': spread,
                                                         'form': form})
        last_statement = player.get_last_statement()
        if last_statement:
            self.send({'last_statement': last_statement.as_dict()})
