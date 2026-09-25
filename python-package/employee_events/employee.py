from .query_base import QueryBase


class Employee(QueryBase):
    """Query employee-level names, events, notes, and model features."""

    name = "employee"

    def names(self):
        sql_query = """
            SELECT first_name || ' ' || last_name AS full_name,
                   employee_id
              FROM employee
             ORDER BY employee_id ASC
        """
        return self.query(sql_query)

    def username(self, entity_id):
        sql_query = """
            SELECT first_name || ' ' || last_name AS full_name
              FROM employee
             WHERE employee_id = ?
             ORDER BY employee_id ASC
        """
        return self.query(sql_query, (entity_id,))

    def model_data(self, entity_id):
        sql_query = """
            SELECT SUM(employee_events.positive_events) AS positive_events,
                   SUM(employee_events.negative_events) AS negative_events
              FROM employee
              JOIN employee_events
                ON employee.employee_id = employee_events.employee_id
             WHERE employee.employee_id = ?
        """
        return self.pandas_query(sql_query, (entity_id,))
