# Threat analysis (STRIDE): Job Application Tracker

STRIDE stands for six kinds of threat: **S**poofing (pretending to be someone), **T**ampering (changing data), **R**epudiation (denying an action), **I**nformation disclosure (data seen by the wrong person), **D**enial of service (making the app unusable) and **E**levation of privilege (getting powers you should not have).

Every flow in `docs/data-flow.md` crosses at least one trust boundary, so every flow (F1 to F9) is analysed below with all six letters. Where a letter does not apply, the table says why. Rule references (Rule 1, and so on) point to `docs/data-model.md`.

Anything marked "(GUESS: please check)" is something I assumed and you have not confirmed.

## F1 Users to web app: sign-up and sign-in (TB1)

| | Threat | What protects us |
|---|---|---|
| S | Someone signs in as another person using a guessed or reused password | Passwords stored only as hashes. Password rules. Same error for an unknown email and a wrong password. Limiting failed attempts is recommended (open point B) |
| T | A forged form field, for example a role or adviser id the person should not have | The server accepts only the two allowed roles. The role can never change afterwards (database rule). The chosen adviser must have the role adviser (database rule) |
| R | A person denies having registered or signed in | Accepted for this project: low impact. No sign-in history is stored (open point C) |
| I | Passwords or cookies read in transit. Error messages show whether an email exists | HTTPS in deployment. Secure, HTTP-only session cookies. Sign-in errors never say which part was wrong. Sign-up must say an email is taken, which cannot be avoided |
| D | Floods of sign-ups or sign-in attempts | Limit failed attempts (open point B). Request size limit. Rate limits at the web server in deployment |
| E | Registering as an adviser to get adviser powers | An adviser only sees jobseekers who chose them (database rule plus scoped queries), so a new adviser sees nothing at first. Remaining risk: a careless jobseeker picks a fake adviser (open point A) |

## F2 Web app to users: pages, cookies, downloads (TB1, TB4)

| | Threat | What protects us |
|---|---|---|
| S | A fake copy of the site tricks people into typing their password | HTTPS with a valid certificate in deployment |
| T | Page content altered in transit, or stored text turning into script in a page | HTTPS. Templates escape all output automatically |
| R | Not applicable: a response is not an action by a person | Nothing needed |
| I | A user is shown another person's data, for example through a wrong id in the address or a wrong query | Every query is limited by the signed-in user. Advisers only load linked jobseekers. A record that is not yours gives a 404 page. A CV download checks the owner or linked adviser every time. No Python error pages shown. Tests for each role |
| D | Repeated downloads of large files | 1 MB CV limit. Rate limits at the web server in deployment |
| E | A jobseeker opens an adviser page, or the reverse | The role is checked on the server for every page. Hiding a button is never used as protection |

## F3 Jobseeker to web app: changes (TB1)

| | Threat | What protects us |
|---|---|---|
| S | A forged request from another site using a signed-in jobseeker's session (CSRF) | A CSRF token on every form that changes data. SameSite session cookies |
| T | A malicious or oversized CV, invalid values, SQL injection, script typed into notes | 1 MB limit. File type and content check (Word or PDF). Parameterised queries only. Database CHECK rules. Escaped output. Advert links must start with http:// or https:// |
| R | A jobseeker denies changing an application | Accepted for this project: only current values are stored. A change history is a possible enhancement (open point C) |
| I | Changing an id in the form to read or edit someone else's record | Every read, edit and delete uses both the record id and the owner id. Other people's records give a 404 page |
| D | Repeated uploads fill the database | 1 MB per CV. Request size cap. A limit on CVs per jobseeker could be added (GUESS: please check) |
| E | A jobseeker approves their own CV, or switches adviser after choosing | Status and decision fields from a jobseeker are ignored. Only the linked adviser can be recorded as decider (database rule). The adviser choice is once only (database rule) |

## F4 Adviser to web app: viewing and deciding (TB1, TB4)

| | Threat | What protects us |
|---|---|---|
| S | A forged request using an adviser's session (CSRF) | CSRF token and SameSite cookies, as in F3 |
| T | An adviser decides the CV of a jobseeker who is not linked to them, or sends an invalid decision | Database rule: a decision can only come from the adviser linked to the CV's owner. Decision values limited by CHECK |
| R | An adviser denies a decision | The CV records who decided (`decided_by`), when (`decided_at`), the outcome and any comment. Weak point: `decided_by` becomes empty if the adviser's link is removed (Delete rule 3), though the date and outcome stay |
| I | An adviser reads data of jobseekers who are not linked to them, or a jobseeker's phone number | Adviser queries only load jobseekers whose adviser is that adviser. Adviser queries never select the phone number. Application notes are visible to the linked adviser by design. Other jobseekers give a 404 page |
| D | Excessive requests from an adviser account | Same limits as F3 |
| E | An adviser edits applications or other people's data | Adviser pages have no code that changes applications. The only adviser write is a CV decision, protected by the database rule above. Tests try each forbidden action |

## F5 Web app and database (TB2, TB4)

| | Threat | What protects us |
|---|---|---|
| S | Another program uses the database file | File permissions so only the app's OS account can read or write it |
| T | SQL injection, broken references, invalid values | Parameterised queries. Foreign keys switched on for every connection through `get_connection()`. CHECK rules. Role rules in the database |
| R | No record of who changed what | Decisions keep who and when. A full audit log is not in the data model (open point C) |
| I | The database file is copied or read | File permissions. Disk encryption on the host. Protected backups. The file holds all personal data and the CV files |
| D | The database is locked or becomes too big | Busy timeout so the app and the script wait for each other. Size limits on CVs. Monitor file size |
| E | The app uses more power than it needs | SQLite has no per-user permissions. Protection comes from scoped queries and database rules. A read-only connection for advisers is possible (GUESS: please check if you want it) |

## F6 OS scheduler to automation script (TB3)

| | Threat | What protects us |
|---|---|---|
| S | Someone else starts the script or edits the scheduler entry | The script runs under the app's own OS account. It is never reachable from a web page |
| T | The script file is replaced with a harmful one | File permissions. The script is under version control |
| R | No evidence that the automations ran | Run output goes to the log file (F8). A run-history table is a possible addition (open point D) |
| I | Not applicable: the start signal carries no personal data | Nothing needed |
| D | The script runs too often, or runs twice at once | Every step is safe to repeat: one waiting reminder per application, digest check, reminders marked sent or skipped once |
| E | The script has more access than it needs | It runs as the app account only and creates notifications and updates reminders only |

## F7 Automation script and database (TB2)

| | Threat | What protects us |
|---|---|---|
| S | Not applicable: the script connects through the same helper as the app, no separate identity exists | Same file permissions as F5 |
| T | A re-run creates duplicate or false notifications | A database rule allows only one waiting reminder per application. The digest check. Reminders are marked sent or skipped in the same step as the notification |
| R | See F6 | See F6 |
| I | A notification shown to the wrong person, or too much data in a message | A notification's owner is the application's owner. Messages hold only the minimum (company and job title, CV title and outcome). The decision comment is never copied |
| D | Many due reminders processed at once | Only waiting reminders that are due are processed. A batch limit can be added |
| E | The script writes as any user | It creates notifications and updates reminders only. The tidy-up deletes only old read notifications and finished reminders |

## F8 Automation script to log file (TB2)

| | Threat | What protects us |
|---|---|---|
| S | Not applicable: the file is written by the script's own account | File permissions |
| T | The log is edited to hide something | File permissions. The log is evidence only, not the record of the data |
| R | The log is the evidence that runs happened | Kept for the period in `docs/data-protection.md` |
| I | Personal data written into the log | The script logs counts only. `*.log` is in `.gitignore` so logs are never committed |
| D | The log grows until the disk is full | Old logs removed after the retention period |
| E | Not applicable: a text file gives no extra rights | Nothing needed |

## F9 Operator and host to database and log file (TB2)

| | Threat | What protects us |
|---|---|---|
| S | Someone pretends to be the operator | Operating system login security. Only named people have access |
| T | Direct edits to the database that skip the app's checks | The database rules (CHECK, foreign keys, role rules) still apply, as long as foreign keys are on. Restrict who has access |
| R | The operator changes data and nobody can tell | Accepted for this project. A real service would log operator access |
| I | The operator, or a stolen computer, can read all personal data and the password hashes | File permissions, disk encryption, as few people as possible with access, protected backups |
| D | The database is deleted or damaged by mistake | Regular backups, with an expiry period (see `docs/data-protection.md`) |
| E | The web app runs under a powerful operator account | The app runs under its own limited OS account |

## Open points (not in the data model yet)

- **A. Who can become an adviser?** Anyone can register as an adviser, as in the existing app. A fake adviser only sees jobseekers who choose them, but a jobseeker could be tricked. Options: an invitation code held in an environment variable, or accounts created by hand. Not decided.
- **B. Limiting failed sign-ins.** This needs the app to remember failed attempts, so a small table. The existing app has one (`login_attempts`). It is not in this data model yet.
- **C. Change history.** Without it, a user can deny an edit and a deleted adviser leaves no name on old decisions. It would conflict with the privacy goal of removing data on deletion, so it is a trade-off.
- **D. Run history.** A small table recording each automation run (the existing app has `automation_runs`). Not in this data model yet.
- **E. Deployment tasks.** HTTPS, a production web server, malware scanning of uploaded CVs, rate limits and backups are production work, not part of the data model.
