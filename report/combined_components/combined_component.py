from copy import deepcopy

from fastcore.xml import FT
from fasthtml.common import Div


class CombinedComponent:
    children = []
    outer_div_type = Div(cls="container")

    def __call__(self, userid, model):
        called_children = self.call_children(userid, model)
        div_args = self.div_args(userid, model)

        return self.outer_div(called_children, div_args)

    def call_children(self, userid, model):
        called = []
        for child in self.children:
            render_child = deepcopy(child)
            if isinstance(render_child, FT):
                called.append(render_child())
            else:
                called.append(render_child(userid, model))

        return called

    def div_args(self, userid, model):
        return {}

    def outer_div(self, children, div_args):
        outer_div = deepcopy(self.outer_div_type)
        outer_div.children = ()
        return outer_div(*children, **div_args)
