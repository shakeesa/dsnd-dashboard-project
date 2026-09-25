# employee-events

`employee_events` is the read-only Python query API used by the employee
performance and recruitment-risk dashboard. Its source distribution bundles the
canonical SQLite fixture, so callers do not need to locate the project checkout
or write SQL themselves.

```python
from employee_events import Employee, Team

employee = Employee()
print(employee.names())
print(employee.event_counts(1))
print(employee.notes(1))

team = Team()
print(team.names())
print(team.model_data(1))
```

The public API also exports `QueryMixin` and `QueryBase`. Query values are bound
as SQLite parameters. Every call opens the bundled database through a
package-relative SQLite URI in read-only mode, enables SQLite's query-only
guard, and closes its connection before returning or raising an error. SQLite
therefore rejects `INSERT`, `UPDATE`, `DELETE`, schema changes, and other
mutating statements instead of allowing callers to alter the canonical fixture.
