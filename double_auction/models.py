from otree.api import (
    models, widgets, BaseConstants, BaseSubsession, BaseGroup, BasePlayer,
    Currency as c, currency_range
)

author = 'Your name here'

doc = """
Your app description
"""


class Constants(BaseConstants):
    name_in_url = 'double_auction'
    players_per_group = None
    num_rounds = 1


class Subsession(BaseSubsession):
    def creating_session(self):
        print('AAAA', self.session.config)
        print(MyModel.objects.all())
        # for i in range(5):
        #     MyModel.objects.create(setting='aaa{}'.format(i))


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    pass


from django.db import models as djmodels


class MyModel(djmodels.Model):
    setting = models.StringField()
