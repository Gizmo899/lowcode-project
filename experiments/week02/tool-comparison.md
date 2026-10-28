# Week 2 — AI Tool Comparison

## The requirement

Build a Flask web application that serves a contact form at `/contact` with name, email and message fields. Validation must happen on the server, not only in the browser: any empty field must be rejected with an error saying what is missing, the email address must be checked for valid format, and a successful submission must show a confirmation message. Nothing needs to be stored yet. (The prompt's "service aside" is a typo for "server side"; both tools read it that way.)

## Prompts used

The same prompt was given to both tools, unedited.

### Claude

```
write a web appllication with flask. 
A contact form that is rendered at /contact. I want fields for name, email and message.  The app has to validate whether the email address is a valid format.  Validation has to be done service aside.  If any field is empty I want the app to reject it and return an error message as to what is missing.  If it is successful, then display a confirmation message. 
No need to store data at the moment.
```

### Gemini

```
write a web appllication with flask. 
A contact form that is rendered at /contact. I want fields for name, email and message.  The app has to validate whether the email address is a valid format.  Validation has to be done service aside.  If any field is empty I want the app to reject it and return an error message as to what is missing.  If it is successful, then display a confirmation message. 
No need to store data at the moment.
```

## Scores

| Criterion | Claude | Gemini | Manus |
|---|---|---|---|
| Correctness | 4 | 3 | — |
| Code quality | 4 | 3 | — |
| Completeness | 5 | 4 | — |
| Security | 3 | 2 | — |

Scale: 1 (broken) to 5 (nothing to fix). Manus was not scored because no output was supplied for it.

Basis: both apps were run with Flask 3.1's test client against identical inputs: 6 empty, whitespace-only and missing-field cases, 18 email formats (4 valid, 14 malformed), script-injection payloads, a 2 MB request body and a 100,000-character hostile email.

- **Correctness.** Both handle every empty-field case and the success path. They differ on email format. Claude correctly handled 13 of 18 addresses and Gemini 9 of 18. Gemini's regex rejects a valid address with a `+` tag (`al.o+tag@sub.example.co.uk`) and accepts 8 of the 14 malformed ones.
- **Code quality.** Claude splits validation into `validate_contact()`, which returns `(values, errors)` and can be tested without a request. Gemini puts everything in one route function and describes its regex as "standard" when it isn't.
- **Completeness.** Both meet every stated requirement and keep the user's input on error. Claude also gives per-field errors linked to each input, uses `novalidate` so the server always decides, and returns 400 on rejection. Gemini returns 200 on rejection and has one combined error string.
- **Security.** Neither is vulnerable to XSS (Jinja autoescaping held for both) or showed catastrophic regex backtracking. Both leave `debug=True` in `__main__` and have no CSRF protection. Gemini also hard-codes a `secret_key`.

## What each got wrong

**Claude.** The email regex is looser than it looks: it accepts `al..o@example.com`, `.al@example.com` and `al@-example.com`. It also rejects valid internationalised addresses (`é@example.com`, `al@exämple.com`). Its own code comment says to swap in `email-validator` for stricter checking, which is the right fix. `debug=True` is hard-coded, there is no CSRF token, and name and message have no application-level length limit (only Flask's default form-size cap protects them). It also added things nobody asked for, such as a `/` redirect and dark-mode CSS, so there is more to read than a "no storage yet" brief needs. The success page is rendered directly from the POST, so refreshing re-submits the form.

**Gemini.** The regex `^[\w\.-]+@[\w\.-]+\.\w+$` is wrong in both directions. It rejects plus-addressing (`al.o+tag@sub.example.co.uk`), which real users have, and it accepts `al@example..com`, `al@.example.com`, `al@example.c`, `al@example.123` and `al@exa_mple.com`. It hard-codes `app.secret_key = 'super_secret_key_for_flash'` even though nothing uses sessions or `flash`, so the comment is misleading and the key becomes a real weakness the moment sessions are added. A rejected submission returns HTTP 200, the email field is `type="text"` (no email keyboard on mobile), and errors are one string with no link to the field at fault and no ARIA attributes. Like Claude's version, it keeps `debug=True`, has no CSRF protection and renders success straight from the POST.

**Manus.** Not assessed; no output was supplied.

## Which I kept, and why

I kept Claude's version (`app.py` and `contact.html`). The deciding criterion is correctness, because the email check is the only non-trivial requirement in the brief. In testing Claude's validator got 13 of 18 addresses right against Gemini's 9 of 18. Gemini's also turns away valid `+` addresses, which would silently lose real messages, while Claude's mistakes are mostly over-acceptance of odd addresses and rejection of rare internationalised ones. Code quality is the second reason: `validate_contact()` is a separate function that returns its results, so it can be unit-tested without Flask, whereas Gemini's checks are inline in the route. Security was a tie-breaker, since Claude has no hard-coded secret. Gemini's one real advantage is its single-sentence "missing: Name, Email" message, which matches the prompt's wording most literally and is worth borrowing. Before shipping either one I would replace the regex with `email-validator`, turn `debug` off outside local development and add CSRF protection with Flask-WTF.
