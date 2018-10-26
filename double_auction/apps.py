from django.apps import AppConfig


#
# def closure_mapping(func):
#     closures, names = func.__closure__, func.__code__.co_freevars
#     return {n: c.cell_contents for n, c in zip(names, closures)}
#
#
# def repatch_filter_expression():
#     original_resolve = closure_mapping(FilterExpression.resolve)['original_resolve']
#
#     def resolve(self, context, ignore_failures=True):
#         return original_resolve(self, context, ignore_failures=True)
#
#     FilterExpression.resolve = resolve

def repatch_session_config():
    from otree.session import SessionConfig
    original_custom_editable_fields = SessionConfig.custom_editable_fields
    original_editable_field_html = SessionConfig.editable_field_html

    def updating_custom_editable_fields(self):
        oldies = original_custom_editable_fields(self)
        self['Privet'] = 'hello'
        if 'Privet' not in oldies:
            oldies.append('Privet')
        return oldies

    def updating_editable_field_html(self, field_name):
        print(field_name)
        if field_name == 'Privet':
            a="""
            <tr><td><b>Configuration name</b><td><select name="double_auction.Privet" required="" id="id_Privet" class="form-control">
  <option value="999" selected="" class="form-control">--hhh---</option>

  <option value="777" class="form-control">777</option>

</select></td>
            """
            return a# todo - a list here from MyModel
        else:
            ...
        oldone = original_editable_field_html(self, field_name)
        return oldone

    SessionConfig.custom_editable_fields = updating_custom_editable_fields
    SessionConfig.editable_field_html = updating_editable_field_html


class MyAppConfig(AppConfig):
    name = 'double_auction'

    def ready(self):
        repatch_session_config()
