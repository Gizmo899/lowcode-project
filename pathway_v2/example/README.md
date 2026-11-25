# Worked example: club equipment loans

The lecturer's on-screen example for Session 5. It is laid out like a student's CA2 repository, so you can see what "done" looks like.

| File | What it shows |
|---|---|
| `docs/data-model.md` | The design, written first: entities, fields, rules, the delete rule with its reason, a Mermaid diagram, and what changed after testing |
| `schema/001_initial.sql` | The schema built from that design |
| `schema/002_add_due_date.sql` | A second migration, applied to a database that already has loans in it |
| `db.py` | The data layer: one `get_connection()` with the PRAGMA, `?` placeholders everywhere, `None` for not found |
| `app.py` | A tiny Flask app (list loans, lend an item, 404 for a missing loan) |
| `tests/test_constraints.py` | Tests that prove each rule rejects bad data, the FK trap, RESTRICT, and persistence |

## Try it (from inside this `example` folder)

Mac (use `python` instead of `python3` on Windows):

```text
python3 ../tools/migrate.py app.db
python3 ../tools/check_db.py app.db --src .
python3 -m unittest -v
python3 app.py
```

`app.py` needs Flask (`pip install flask`). Everything else uses only what comes with Python. If Flask is not installed, the two web tests are skipped and the rest still run.
