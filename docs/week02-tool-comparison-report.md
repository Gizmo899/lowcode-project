# Week 2 — AI Tool Comparison
 
## The requirement
The task requires building a lightweight Flask web application featuring a contact form rendered at `/contact` with `name`, `email`, and `message` fields. The backend must enforce server-side validation to check that no fields are left blank and that the email address follows a valid format. If validation fails, the app must reject the submission and display a specific error message identifying what is missing or invalid. Upon successful submission, a clear confirmation message should be rendered without needing to store any data in a database.
 
## Prompts used
### Claude
```text
write a web appllication with flask. 
A contact form that is rendered at /contact. I want fields for name, email and message.  The app has to validate whether the email address is a valid format.  Validation has to be done service aside.  If any field is empty I want the app to reject it and return an error message as to what is missing.  If it is successful, then display a confirmation message. 
No need to store data at the moment.
```
### Gemini
```text
write a web appllication with flask. 
A contact form that is rendered at /contact. I want fields for name, email and message.  The app has to validate whether the email address is a valid format.  Validation has to be done service aside.  If any field is empty I want the app to reject it and return an error message as to what is missing.  If it is successful, then display a confirmation message. 
No need to store data at the moment.
```
 
## Scores
| Criterion | Claude | Gemini |
|---|---|---|
| Correctness | 10/10 | 8/10 |
| Code quality | 9/10 | 7/10 |
| Completeness | 10/10 | 8/10 |
| Security | 9/10 | 6/10 |
 
## What each got wrong
Claude produced an overall robust implementation, but it included a small redirect from `/` to `/contact` which was not strictly requested, and it set a length limit on the email string (`254` characters) that, while accurate to RFC specs, was not part of the explicit user prompt.

Gemini hardcoded a sensitive setting (`app.secret_key = 'super_secret_key_for_flash'`) even though session flash messages were not actually utilized in the template or backend logic. Additionally, its regex pattern (`^[\w\.-]+@[\w\.-]+\.\w+$`) is overly permissive and fails to enforce stricter email structure standardizations, while its single generic `error` container handles multiple validation errors less gracefully than field-level reporting.
 
## Which I kept, and why
I kept Claude's implementation because it scored significantly higher in Code quality, Security, and Correctness. Claude provided full accessibility considerations (`aria-invalid`, `aria-describedby`), granular field-by-field error handling with HTTP 400 status codes on failure, strict input sanitization, and automatic dark mode support in the CSS template. Gemini’s solution relied on a weak regex pattern, unnecessarily included a hardcoded secret key, and lacked accessible form markup and HTTP error response codes.