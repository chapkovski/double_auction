from channels.generic.websockets import JsonWebsocketConsumer
import random
from double_auction.models import Constants, Player, Group
import json


class MarketTracker(JsonWebsocketConsumer):
    url_pattern = (r'^/market_channel/(?P<player_pk>[0-9]+)/(?P<group_pk>[0-9]+)$')

    def clean_kwargs(self):
        self.player_pk = self.kwargs['player_pk']
        self.group_pk = self.kwargs['group_pk']

    def connection_groups(self, **kwargs):
        group_name = self.get_group().get_channel_group_name()
        return [group_name]

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

        # todo: validate correct price is inserted
        # todo: config quantity (more than 1 if settings are set for that)
        # todo: disabling buttons if new statements can't be made or no retraction possible (no bids are made)
        # todo: syncrhonize timers among the entire group!



        if msg['action'] == 'new_statement':
            if player.role() == 'buyer':
                player.bids.create(price=msg['price'], quantity=msg['quantity'])
            else:
                player.asks.create(price=msg['price'], quantity=msg['quantity'])




        if msg['action'] == 'retract_statement':
            to_del = player.get_last_statement()
            if to_del:
                to_del.delete()
        asks = group.get_asks_html()
        bids = group.get_bids_html()
        spread = group.get_spread_html()
        self.group_send(group.get_channel_group_name(), {'asks': asks,
                                                         'bids': bids,
                                                         'spread': spread})
        last_statement = player.get_last_statement()
        if last_statement:
            self.send({'last_statement': last_statement.as_dict()})
