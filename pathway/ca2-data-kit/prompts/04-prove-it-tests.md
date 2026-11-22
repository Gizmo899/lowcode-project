# Prompt 04: Prove it with tests

**When:** Lab 2, after the restart test passes. **Writes code?** Yes, test files only.

## Why this prompt is shaped like this

A constraint you have not tested is a constraint you are hoping for. **Specificity** matters most here: one test per rule, each trying to put BAD data in, because an agent left alone tends to write "happy path" tests that only check good data goes in. The **constraint** "do not change the app or schema to make a test pass" stops the agent quietly weakening your rules to get a green tick. These tests count towards the "automated tests that pass" requirement in CA2, and Session 7 builds on them.

## The prompt

```text
Read AGENTS.md, docs/data-model.md, schema/ and db.py.

Write tests in tests/test_constraints.py using Python's built-in unittest (they must also run
with pytest). Each test must create a fresh temporary database by running the files in
schema/ in number order, and must never touch app.db.

Write one test for EACH of these, each one trying to put BAD data in and checking it is REJECTED:
- a duplicate value in a UNIQUE field
- a value that breaks a CHECK rule
- a missing value in a required (NOT NULL) field
- a row pointing at a [PARENT] that does not exist (foreign key), using db.get_connection()
- my delete rule: [RESTRICT: deleting a parent with children is blocked / CASCADE: the
  children are deleted too / SET NULL: the children's link is emptied]
Also write:
- one test that saves a record, closes the connection, opens the file again and finds it
- one test that asking for an id that does not exist returns None (not an error)

Do not change my app, db.py or the schema to make a test pass. If a test fails, tell me why.
Tell me the exact command to run the tests on [Windows / Mac].
Then list any decision you made that I did not specify.
```

## After it answers

Run the tests (from the top folder of your project):

```text
Windows:  python -m unittest -v
Mac:      python3 -m unittest -v
```

If a test fails, read why before you let the agent "fix" it. A failing constraint test can mean your schema is missing a rule, which is a real finding. Commit when they pass: `git add tests` then `git commit -m "Add constraint tests (UNIQUE, CHECK, NOT NULL, FK, delete rule, persistence)"`.
