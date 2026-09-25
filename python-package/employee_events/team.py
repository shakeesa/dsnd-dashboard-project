from .query_base import QueryBase


class Team(QueryBase):
    """Query team-level names, events, notes, and member model features."""

    name = "team"

    def names(self):
        sql_query = """
            SELECT team_name,
                   team_id
              FROM team
             ORDER BY team_id ASC
        """
        return self.query(sql_query)

    def username(self, entity_id):
        sql_query = """
            SELECT team_name
              FROM team
             WHERE team_id = ?
             ORDER BY team_id ASC
        """
        return self.query(sql_query, (entity_id,))

    def model_data(self, entity_id):
        sql_query = """
            SELECT SUM(employee_events.positive_events) AS positive_events,
                   SUM(employee_events.negative_events) AS negative_events
              FROM team
              JOIN employee_events
                ON team.team_id = employee_events.team_id
             WHERE team.team_id = ?
             GROUP BY employee_events.employee_id
             ORDER BY employee_events.employee_id ASC
        """
        return self.pandas_query(sql_query, (entity_id,))
