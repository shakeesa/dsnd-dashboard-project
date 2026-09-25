from fasthtml.common import Caption, Table, Tbody, Td, Th, Thead, Tr

from .base_component import BaseComponent


class DataTable(BaseComponent):
    caption = "Data"

    def build_component(self, entity_id, model):
        if not model.name:
            return None

        data = self.component_data(entity_id, model)
        header = Tr(*(Th(column, scope="col") for column in data.columns))
        rows = [
            Tr(*(Td(value) for value in data_row))
            for data_row in data.to_numpy()
        ]

        return Table(
            Caption(self.caption),
            Thead(header),
            Tbody(*rows),
        )
