# Week 3 — AI Code Review

Reviewed by: Claude (Claude Sonnet 5.5, Anthropic) Date: 2026-11-21

## Findings

| # | File:line | What it says is wrong | Is it real? | Action |
|---|---|---|---|---|
| 1 | auth.py:78,105-106; register.html:9,14; auth.py:65-67 | Anyone can register as a career adviser with no vetting, and adviser names and IDs are shown to anonymous visitors. A jobseeker who picks a self-made adviser gives them name, email, phone, CV and applications, and the assignment is permanent. | yes — reproduced: unauthenticated adviser registration returned 302 and the name appeared on /register | TBD |
| 2 | app.py:20 | SECRET_KEY falls back to a hard-coded public value, and .env is never loaded, so following the README can run on the default key. | yes — reproduced: forged an adviser session cookie and got 200 on /adviser/dashboard | TBD |
| 3 | auth.py:16-18, 21-33, 62 | Login throttle is keyed on email plus IP, so rotating IPs bypasses it. Behind a proxy without ProxyFix all clients share one IP, so anyone can lock out a victim. No limit on /register. login_attempts is never pruned. | yes — reproduced: 12 of 12 guesses with rotating IPs got 401, and 5 from one IP was blocked. Proxy lockout and table growth are by reading the code | TBD |
| 4 | auth.py:162, 128-135 | Account enumeration: no password hash is computed for unknown emails, and a duplicate registration is distinguishable from a new one. | yes — reproduced: 81 ms known email vs 2 ms unknown. Duplicate register returned 200, new returned 302 | TBD |
| 5 | security.py:26-47; jobseekers.py:93, 145-155; applications.py:81 | Sessions are never revalidated against the DB. After account closure a session on another device still works and causes 500s. | yes — reproduced: 500 on /profile and on POST /applications/new with a stale session | TBD |
| 6 | auth.py:82; jobseekers.py:69; advisers.py:78; adviser_jobseeker.html:5-6; adviser_dashboard.html:6 | Email validation is only `"@" in email`, and the value is placed in mailto: links the adviser clicks. Email can be changed without a password. | yes — reproduced: "@" and "a@b.com?bcc=x@y.test" were accepted. The mailto effect is by reading the templates | TBD |
| 7 | security.py:22 | hmac.compare_digest raises TypeError on a non-ASCII csrf_token, giving a 500 instead of a 400. | yes — reproduced: POST with csrf_token "é" returned 500 | TBD |
| 8 | app.py:54-65; cv_management.py:141-147 | No Cache-Control on authenticated pages, so PII can reappear via Back after logout. CV download uses no-cache rather than no-store or private. | yes — reproduced: no Cache-Control header on /adviser/dashboard. Download sent "no-cache, max-age=0" | TBD |
| 9 | cv_management.py:18-24, 38-40, 80-87 | Upload checks are weaker than they look: octet-stream is allowed for every type and the MIME is client-supplied. Any OLE2 file passes as .doc, PDF is a prefix check only, and there is no per-user quota. | yes — by reading the code | TBD |
| 10 | jobseekers.py:144-154 | Account closure deletes the DB rows first, then swallows unlink errors with no log. The filenames are gone, so the "operator can retry" comment is false and CV files can be orphaned. | yes — by reading the code | TBD |
| 11 | register.html:23; applications.html:7; profile.html:7; adviser_profile.html:6 | app.js is loaded only on the register page, so data-confirm dialogs never run. Deleting an application is one click. | yes — by grep: app.js is referenced only in register.html | TBD |
| 12 | applications.py:30-33, 56, 85, 120; jobseekers.py:42; advisers.py:58 | Dates are validated with date.fromisoformat but the raw string is stored. On Python 3.11+ other ISO formats pass, which breaks ORDER BY date_applied. | yes — reproduced: "20241231" was stored as-is | TBD |
| 13 | cv_management.py:72; cv.html:6; adviser_jobseeker.html:7 | secure_filename drops non-ASCII names and the [:180] cut can remove the extension. The file icon label is derived from the text after the last dot. | yes — reproduced: "简历.pdf" became "pdf", and a 200-char name lost ".pdf" | TBD |
| 14 | run_automations.py:3; applications.py:41-44; README.md:84 | Reminders are due after 7 days but the job runs weekly on Monday, so they can fire up to 6 days late. due_at is now + 7, not date_applied + 7. | yes — by reading the code and README | TBD |
| 15 | automation_tasks.py:19-22, 28-35, 52-55, 102-106 | automation_runs is overwritten on a re-run, the reminder run_key is per second, and the digest makes an N+1 query per jobseeker. | yes — reproduced: a second weekly run replaced the first summary with created: 0 | TBD |
| 16 | advisers.py:152-159; jobseekers.py:124-129 | UPDATE rowcounts are not checked, so a review and notification can be written for a superseded CV, and success is flashed when 0 rows changed. | yes — by reading the code | TBD |
| 17 | security.py:31,42; auth.py:143-175 | login_required passes next but login never reads it. If it is wired up it will need an open-redirect check. | yes — reproduced: after login with ?next= the redirect went to / | TBD |
| 18 | auth.py:128-135; jobseekers.py:81-86; advisers.py:90-95, 174-177; app.py:83-102, 101; cv_management.py:65 | Broad `except Exception` with string matching instead of sqlite3.IntegrityError, and several handlers do not log. No 405 or 500 handler. "5 MB" is hard-coded though the limit is configurable. | yes — 405 page reproduced as unstyled. The rest is by reading | TBD |
| 19 | jobseeker_dashboard.html:21 | The CV icon is hard-coded to "PDF" for every file type. | yes — by reading the template | TBD |
| 20 | app.py:104-113; wsgi.py:5; run_automations.py:13; db.py:35-38; tests/test_app.py:9 | Importing app builds an app and runs the schema. wsgi and the automation script build a second one. Tests create the real instance DB. The schema runs on every start with no migration path. | yes — reproduced: running the tests created instance/job_tracker.sqlite | TBD |
| 21 | security.py:26-47; notifications.py:34-36; cv_management.py:115-117 | Auth guards are duplicated and inconsistent: some routes abort(401) instead of redirecting to login. | yes — reproduced: anonymous download returned a 401 page | TBD |
| 22 | jobseekers.py:21, 88 | SELECT u.* and SELECT * put password_hash into the template context. | yes — by reading the code | TBD |
| 23 | schema.sql:68, 80-81, 109, 125-126; db.py:14-17 | No index on several FK columns used by cascading deletes, and no WAL or journal setting for multi-worker use. | yes — by reading the schema and grepping its indexes | TBD |
| 24 | app.py:7, 28; jobseekers.py:10, 160-162; auth.py:174; applications.py:41-44; requirements.txt:1 | Small items: unused imports, `__import__("secrets")`, helper defined after use, duplicated timestamp code, a no-op TRUSTED_HOSTS, and unpinned dependencies with no WSGI server listed. | yes — pyflakes confirms the unused imports. The rest is by reading | TBD |
| 25 | tests/test_app.py:187-189, 210 | Tests cover happy paths only. No tests for throttling, upload rejection, download denial, 403s, account closure, reminder skipping, adviser-close block or multipart CSRF. One response is never closed. | yes — by reading the 7 tests, which all pass | TBD |

## What I fixed, and why
1st fix: app.py:20 | SECRET_KEY falls back to a hard-coded public value
Now there are no more built-in key, weak or example keys are refused too, the .env file now works and the docs no longer point at the trap.
The app uses a secret key to sign the login cookie. That is how it knows a cookie really came from the app and wasn’t made up by a visitor. Anyone who had read the code could use it to create a cookie that said “I am user 1, a career adviser”, and the app would accept it.
 
## What I am knowingly leaving, and why
(this is not a failing — naming it is the point)
 
## What the reviewer got wrong
(reviewers hallucinate too. Did it invent a problem, or miss an obvious one?)
