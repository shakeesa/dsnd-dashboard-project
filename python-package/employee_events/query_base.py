from .sql_execution import QueryMixin


class QueryBase(QueryMixin):
    """Provide queries shared by employee and team entities."""

    name = ""

    def names(self):
        return []

    def _entity_identifiers(self):
        if self.name not in {"employee", "team"}:
            raise ValueError(f"Unsupported query entity: {self.name!r}")
        return self.name, f"{self.name}_id"

    def event_counts(self, entity_id):
        entity_name, id_column = self._entity_identifiers()
        sql_query = f"""
            SELECT employee_events.event_date AS event_date,
                   SUM(employee_events.positive_events) AS positive_events,
                   SUM(employee_events.negative_events) AS negative_events
              FROM {entity_name}
              JOIN employee_events
                ON {entity_name}.{id_column} = employee_events.{id_column}
             WHERE {entity_name}.{id_column} = ?
             GROUP BY employee_events.event_date
             ORDER BY employee_events.event_date ASC
        """
        return self.pandas_query(sql_query, (entity_id,))

    def notes(self, entity_id):
        entity_name, id_column = self._entity_identifiers()
        sql_query = f"""
            SELECT notes.note_date AS note_date,
                   notes.note AS note
              FROM {entity_name}
              JOIN notes
                ON {entity_name}.{id_column} = notes.{id_column}
             WHERE {entity_name}.{id_column} = ?
             ORDER BY notes.note_date ASC, notes."index" ASC
        """
        return self.pandas_query(sql_query, (entity_id,))
