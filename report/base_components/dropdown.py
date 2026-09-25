from fasthtml.common import Div, Label, Option, Select

from .base_component import BaseComponent


class Dropdown(BaseComponent):
    def __init__(self, id="selector", name="entity-selection", label=""):
        self.id = id
        self.name = name
        self.label = label

    def build_component(self, entity_id, model):
        options = []
        for index, (text, value) in enumerate(
            self.component_data(entity_id, model)
        ):
            selected = str(value) == str(entity_id) or (
                entity_id is None and index == 0
            )
            option = Option(text, value=value, selected=selected)
            options.append(option)

        return Select(*options, id=self.id, name=self.name)

    def outer_div(self, child):
        return Div(
            Label(self.label, _for=self.id),
            child,
            id=f"{self.id}-wrapper",
        )
