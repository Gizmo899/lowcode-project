# Job Application Tracker: PoC Specification

**Status:** Draft v1, compiled from a 20-question discovery interview
**Purpose:** Input document for generating a working proof-of-concept (PoC)
**Audience:** The person or tool building the PoC

---

## 1. Overview

The Job Application Tracker is a web application that helps **jobseekers** manage their job search and lets **career advisers** review and sign off jobseekers' CVs.

The core app covers:

- Sign-up and log-in for two user types: **Jobseekers** and **Career advisers**
- Recording **job applications**, with **contact details** and **deadlines** of job offers
- Recording a **CV** (file upload) and an adviser **sign-off** on it
- Showing each application's **outcome**

Two automations sit on top of the core app:

- A **scheduled** weekly pipeline digest
- A **triggered** follow-up nudge when an employer has not replied after an application

### Scope decision

The PoC covers the **full feature set**, with the **Week 03 items as the first milestone**:

> Week 03: Jobseekers, Career advisers, sign-in members, record a CV, show the application outcome.

See Section 3 (Milestones) for the build order.

---

## 2. Decision log (interview answers)

| # | Topic | Decision |
|---|-------|----------|
| 1 | Scope | Full feature set; Week 03 items are milestone 1 |
| 2 | Tech stack | Python (Flask) + SQLite + simple frontend |
| 3 | Authentication | Email + password, hashed passwords, session cookies |
| 4 | Role assignment | Anyone can sign up as a jobseeker; advisers need approval (see #20) |
| 5 | Adviser–jobseeker link | No assignment: any adviser can see and review any jobseeker |
| 6 | Application fields | Core + location, work mode, salary range, CV version used, cover letter used |
| 7 | Pipeline stages | Saved → Applied → Interview → Offer → final outcome (Accepted, Rejected, Withdrawn, No reply) |
| 8 | Contacts model | Standalone contact book; a contact can be linked to several applications |
| 9 | Contact fields | Name, company, email, phone, job title/role, LinkedIn URL, notes |
| 10 | Deadline display | Dashboard widget "Upcoming deadlines", a list sorted by date |
| 11 | Recording a CV | Upload a file (PDF/DOCX) with a title and version label |
| 12 | CV approval workflow | Submitted → Approved or Changes requested (comment required); jobseeker uploads a new version to resubmit |
| 13 | Approval vs. applications | No restriction: any CV version can be attached; approval status shown as a badge |
| 14 | Outcome display | Colour-coded outcome badge on each application in the list and detail page |
| 15 | Weekly digest content | Counts per pipeline stage + deadlines due in the next 7 days |
| 16 | Weekly digest delivery | Every Monday 08:00; shown in-app on a "Digest" page, stored in the database |
| 17 | Nudge trigger | 7 days after the application date, if the status is still "Applied" |
| 18 | Nudge format | In-app notification with a suggested follow-up message template the jobseeker can copy |
| 19 | Adviser capabilities | Review queue + read-only access to every jobseeker's profile, CVs and applications (with outcomes) |
| 20 | Adviser onboarding | Advisers sign up freely as "pending"; an admin account approves them before they can log in as advisers |

---

## 3. Milestones (build order)

### Milestone 1: Week 03 (foundation)
- Project skeleton, database, seed data
- Registration, login, logout; roles (jobseeker, adviser, admin)
- Adviser sign-up as "pending" and admin approval page
- Jobseeker: upload and list CVs (title, version label, file); status shows "Submitted"
- Jobseeker: create, edit, list, view and delete applications (all fields except contact linking and CV attachment) with stage and **colour-coded outcome badge**

### Milestone 2: Core app
- Contact book (create, edit, list, delete) and linking contacts to applications
- Attach a CV version (and a cover letter reference) to an application
- Dashboard with the "Upcoming deadlines" widget

### Milestone 3: Approval step
- Adviser review queue; approve or request changes (comment required)
- Adviser read-only views of jobseekers, their CVs and applications (with outcomes)
- CV status badges shown to jobseekers and on applications

### Milestone 4: Automations
- Weekly pipeline digest (scheduled) and the "Digest" page
- Follow-up nudge (triggered) with notification list, unread counter and copyable template

---

## 4. Technology

| Concern | Choice |
|---------|--------|
| Language / framework | Python 3.11+, **Flask** (chosen over FastAPI for server-rendered pages) |
| Templating / frontend | Jinja2 server-rendered pages, plain CSS or a lightweight CSS library (e.g. Pico.css), minimal vanilla JS (copy-to-clipboard only) |
| Database | SQLite via SQLAlchemy |
| Auth | Flask-Login (session cookies); password hashing with Werkzeug (`generate_password_hash`) |
| Forms / CSRF | Flask-WTF |
| Scheduling | APScheduler (`BackgroundScheduler`, in-process) |
| File storage | Local disk, `instance/uploads/` |
| Configuration | Environment variables / `.env` (see Section 12) |

**Scheduler note:** with Flask's debug reloader the scheduler can start twice. Start it only in the reloader's child process (`WERKZEUG_RUN_MAIN == "true"`) or run with `use_reloader=False`.

---

## 5. Users, roles and permissions

### 5.1 Roles

| Role | How obtained | Account status values |
|------|--------------|-----------------------|
| **Jobseeker** | Self-registration | `active` |
| **Career adviser** | Self-registration, then approval by an admin | `pending` → `active` or `rejected` |
| **Admin** | Seeded account (not self-registerable) | `active` |

The admin role is a minimal support role implied by the adviser-approval decision (#20). Its only feature is approving or rejecting advisers.

### 5.2 Authentication rules
- Sign-up fields: full name, email (unique, case-insensitive), password (minimum 8 characters), role choice (**Jobseeker** or **Career adviser**).
- Passwords are stored only as hashes. Sessions use HttpOnly, SameSite=Lax cookies.
- Login with email + password.
- A `pending` adviser who logs in sees: *"Your adviser account is awaiting admin approval."* and gets no session access. A `rejected` adviser sees a rejection message.
- After login, users land on their role's home page (Section 8).

### 5.3 Permission matrix

| Capability | Jobseeker | Adviser | Admin |
|-----------|:---------:|:-------:|:-----:|
| Manage own applications | ✅ | ❌ | ❌ |
| Manage own contacts | ✅ | ❌ | ❌ |
| Upload own CVs | ✅ | ❌ | ❌ |
| View own deadlines widget, digests, notifications | ✅ | ❌ | ❌ |
| View any jobseeker's profile, CVs, applications (read-only, with outcomes) | ❌ | ✅ | ❌ |
| Download any jobseeker's CV file | ❌ | ✅ | ❌ |
| Approve or request changes on a CV | ❌ | ✅ | ❌ |
| View jobseekers' contacts | ❌ | ❌ | ❌ |
| Approve or reject pending advisers | ❌ | ❌ | ✅ |

Every route must enforce these rules server-side. A jobseeker must never be able to access another jobseeker's records by changing an ID in the URL (return 404 or 403).

---

## 6. Data model

All timestamps are stored as UTC. Dates (`date_applied`, `deadline`) are stored as calendar dates.

### `users`
| Field | Type | Notes |
|-------|------|-------|
| id | integer PK | |
| email | text, unique | stored lower-case |
| password_hash | text | |
| full_name | text | |
| role | enum | `jobseeker`, `adviser`, `admin` |
| status | enum | `active`, `pending`, `rejected` |
| created_at | datetime | |

### `cvs`
Each upload is a separate record (a new "version").

| Field | Type | Notes |
|-------|------|-------|
| id | integer PK | |
| jobseeker_id | FK → users | |
| title | text | e.g. "Marketing CV" |
| version_label | text | e.g. "v2" |
| original_filename | text | |
| stored_filename | text | random name on disk |
| mime_type | text | |
| status | enum | `submitted`, `approved`, `changes_requested` (default `submitted`) |
| reviewer_id | FK → users, nullable | adviser who reviewed |
| reviewed_at | datetime, nullable | |
| review_comment | text, nullable | required when status is `changes_requested` |
| uploaded_at | datetime | |

### `applications`
| Field | Type | Notes |
|-------|------|-------|
| id | integer PK | |
| jobseeker_id | FK → users | |
| company | text | required |
| job_title | text | required |
| job_url | text, nullable | |
| location | text, nullable | |
| work_mode | enum, nullable | `remote`, `hybrid`, `on_site` |
| salary_range | text, nullable | free text, e.g. "€45k–€55k" |
| date_applied | date, nullable | set when stage becomes `applied` |
| deadline | date, nullable | application deadline of the job offer |
| notes | text, nullable | |
| stage | enum | `saved`, `applied`, `interview`, `offer` (default `saved`) |
| outcome | enum, nullable | `accepted`, `rejected`, `withdrawn`, `no_reply`; null = still open |
| cv_id | FK → cvs, nullable | CV version used |
| cover_letter_ref | text, nullable | free-text label of the cover letter used (see Section 14) |
| nudge_due_at | datetime, nullable | set when the nudge should fire |
| nudge_sent_at | datetime, nullable | set once the nudge has been created |
| created_at / updated_at | datetime | |

### `contacts`
| Field | Type | Notes |
|-------|------|-------|
| id | integer PK | |
| jobseeker_id | FK → users | |
| name | text | required |
| company | text, nullable | |
| email | text, nullable | |
| phone | text, nullable | |
| job_title | text, nullable | role of the contact |
| linkedin_url | text, nullable | |
| notes | text, nullable | |

### `application_contacts` (many-to-many link)
| Field | Type |
|-------|------|
| application_id | FK → applications |
| contact_id | FK → contacts |

Primary key: (application_id, contact_id). Both records must belong to the same jobseeker.

### `notifications`
| Field | Type | Notes |
|-------|------|-------|
| id | integer PK | |
| user_id | FK → users | recipient |
| type | enum | `follow_up_nudge` (extensible) |
| application_id | FK → applications, nullable | |
| title | text | |
| body | text | contains the follow-up template for nudges |
| is_read | boolean | default false |
| created_at | datetime | |

### `digests`
| Field | Type | Notes |
|-------|------|-------|
| id | integer PK | |
| jobseeker_id | FK → users | |
| week_start | date | the Monday the digest covers |
| stage_counts | JSON | `{"saved": n, "applied": n, "interview": n, "offer": n}` |
| upcoming_deadlines | JSON | list of `{application_id, company, job_title, deadline}` |
| generated_at | datetime | |

Unique constraint on (`jobseeker_id`, `week_start`) so a digest is never generated twice for the same week.

---

## 7. Functional requirements

### 7.1 Sign-up, login, logout (Milestone 1)
- **FR-1** A visitor can register as a Jobseeker (immediately `active`) or as a Career adviser (`pending`).
- **FR-2** A user can log in and out. Invalid credentials show a generic error.
- **FR-3** Adviser accounts that are not `active` cannot access any adviser page.
- **FR-4** An admin sees a list of `pending` advisers and can **Approve** (→ `active`) or **Reject** (→ `rejected`).

### 7.2 Job applications (Milestones 1–2)
- **FR-5** A jobseeker can create, view, edit and delete their own applications using the fields in Section 6.
- **FR-6** The application list shows company, job title, stage, outcome badge, deadline and CV badge (once attached). It can be sorted by deadline and by date applied.
- **FR-7** **Stage rules:** stages are `saved → applied → interview → offer`. When an application moves to `applied`, `date_applied` defaults to today (editable) and `nudge_due_at` is set to `date_applied + 7 days`.
- **FR-8** **Outcome rules:** an outcome (`accepted`, `rejected`, `withdrawn`, `no_reply`) is set through a select field on the edit form. An application with an outcome is *closed*. `accepted` is only allowed from stage `offer`; the other outcomes are allowed from any stage. Clearing the outcome re-opens the application.
- **FR-9** **Outcome display:** the outcome appears as a colour-coded badge on every application in the list and on the detail page. Suggested colours: Accepted = green, Rejected = red, Withdrawn = grey, No reply = amber. Open applications show their stage instead of an outcome badge.
- **FR-10** A jobseeker can attach one of their own CV versions and enter a free-text cover letter reference on an application.

### 7.3 Contacts (Milestone 2)
- **FR-11** A jobseeker can create, edit, list and delete contacts in a standalone contact book.
- **FR-12** A jobseeker can link and unlink contacts to an application from the application detail page. A contact can be linked to many applications, and an application can have many contacts.
- **FR-13** The application detail page lists linked contacts with their details. A contact's page lists the applications it is linked to.

### 7.4 Deadlines (Milestone 2)
- **FR-14** The jobseeker dashboard has an **"Upcoming deadlines"** widget: a plain list sorted by deadline date (ascending).
- **FR-15** The widget includes applications that have a deadline of today or later and no outcome (open applications). Each row shows company, job title and deadline date, and links to the application. Show at most 10 rows, with an empty-state message when there are none.
- Colour-coded urgency, a calendar view and reminder banners are **out of scope** (decision #10).

### 7.5 Recording a CV (Milestone 1)
- **FR-16** A jobseeker uploads a CV file (**PDF or DOCX**, max 5 MB) with a **title** and a **version label**. All three are required.
- **FR-17** Every upload creates a new CV record with status `submitted`. Records are immutable after upload (no replace, no edit of the file).
- **FR-18** The "My CVs" page lists all of the jobseeker's CV versions with title, version label, upload date, status badge, and the adviser's comment if changes were requested. Files can be downloaded by the owner.
- **FR-19** To resubmit after "Changes requested", the jobseeker uploads a **new version** (a new record). The old record keeps its status and comment as history.

### 7.6 CV approval (Milestone 3)
- **FR-20** Advisers see a **review queue** listing all CVs with status `submitted` (oldest first), showing jobseeker name, title, version label and upload date.
- **FR-21** On a CV review page, the adviser can download the file and choose:
  - **Approve**: status → `approved`, optional comment.
  - **Request changes**: status → `changes_requested`, comment **required**.
- **FR-22** A review records `reviewer_id` and `reviewed_at`. A reviewed CV cannot be reviewed again.
- **FR-23** The CV status is shown as a badge: Submitted, Approved, Changes requested. The badge appears on the My CVs page and next to the attached CV on an application.
- **FR-24** **No gating:** approval status does not restrict attaching a CV to an application (decision #13).

### 7.7 Adviser read-only access (Milestone 3)
- **FR-25** Advisers have a "Jobseekers" page listing every jobseeker. Each jobseeker page shows their profile (name, email, sign-up date), CV versions with statuses and comments, and applications with stage and outcome badge.
- **FR-26** An adviser can open any application in a read-only detail view (including outcome). Contacts are not shown to advisers.
- **FR-27** Advisers cannot edit, comment on, or delete jobseeker data. No cross-jobseeker analytics are required.

---

## 8. Screens and routes

### Public
| Route | Purpose |
|-------|---------|
| `GET/POST /register` | Sign up (role choice: Jobseeker / Career adviser) |
| `GET/POST /login` | Log in |
| `POST /logout` | Log out |

### Jobseeker
| Route | Purpose |
|-------|---------|
| `GET /dashboard` | Home: "Upcoming deadlines" widget, quick links, latest notifications |
| `GET /applications` | Application list (stage / outcome badges) |
| `GET/POST /applications/new` | Create application |
| `GET /applications/<id>` | Detail: fields, outcome badge, linked contacts, CV |
| `GET/POST /applications/<id>/edit` | Edit (incl. stage, outcome, CV, cover letter ref) |
| `POST /applications/<id>/delete` | Delete |
| `POST /applications/<id>/contacts` | Link or unlink contacts |
| `GET /contacts`, `GET/POST /contacts/new`, `GET/POST /contacts/<id>/edit`, `POST /contacts/<id>/delete` | Contact book |
| `GET/POST /cvs` | My CVs list + upload form |
| `GET /cvs/<id>/download` | Download (owner or adviser only) |
| `GET /notifications`, `POST /notifications/<id>/read` | Notification list, mark as read |
| `GET /digests`, `GET /digests/<id>` | Digest list and detail |

### Adviser
| Route | Purpose |
|-------|---------|
| `GET /adviser/reviews` | Review queue of `submitted` CVs |
| `GET/POST /adviser/cvs/<id>` | CV review page: download, approve, request changes |
| `GET /adviser/jobseekers` | All jobseekers |
| `GET /adviser/jobseekers/<id>` | Jobseeker profile, CVs, applications |
| `GET /adviser/applications/<id>` | Read-only application detail |

### Admin
| Route | Purpose |
|-------|---------|
| `GET /admin/advisers` | Pending advisers; `POST` approve / reject |

### Navigation
- **Jobseeker:** Dashboard · Applications · Contacts · My CVs · Digest · 🔔 Notifications (unread count) · Logout
- **Adviser:** Review queue · Jobseekers · Logout
- **Admin:** Pending advisers · Logout

---

## 9. Automations

### 9.1 Weekly pipeline digest (scheduled)

| Item | Specification |
|------|---------------|
| Schedule | Every **Monday at 08:00**, in the timezone from `APP_TIMEZONE` (default `UTC`) |
| Recipients | Every `active` jobseeker (advisers and admins get no digest) |
| Delivery | Stored in the `digests` table and shown on the in-app **Digest** page. No email is sent. |
| Content | (1) **Count of open applications per stage**: Saved, Applied, Interview, Offer. Closed applications are excluded. (2) **Deadlines due in the next 7 days**: open applications with a deadline from today through today + 7 days, sorted by date, showing company, job title and date. |
| Empty case | A digest is still generated when counts are all zero, with a "No deadlines this week" message |
| Idempotency | One digest per jobseeker per week (unique constraint); re-running the job must not create duplicates |
| Page | `/digests` lists digests newest first; `/digests/<id>` shows the counts and deadline list. The dashboard may link to the latest digest. |

### 9.2 Follow-up nudge (triggered)

| Item | Specification |
|------|---------------|
| Trigger event | An application moves to stage `applied` (or is created as `applied`). The app sets `nudge_due_at = date_applied + 7 days`. |
| Firing | A periodic job (every hour) finds applications where `nudge_due_at <= now`, `nudge_sent_at` is null, `stage = applied` and `outcome` is null. |
| Cancel conditions | If the stage changes away from `applied` or an outcome is set before the due time, no nudge is sent. If `date_applied` is edited, `nudge_due_at` is recomputed. |
| Frequency | **Once** per application (no repeats). `nudge_sent_at` is set when the notification is created. |
| Delivery | An **in-app notification** (type `follow_up_nudge`) for the jobseeker, shown in the notifications list and as an unread counter in the nav |
| Content | Title: "No reply yet from {company}". Body: a copyable follow-up message template (below), with a **Copy** button on the notification page and a link to the application. |

**Follow-up template**

```
Subject: Following up on my application – {job_title}

Dear {contact_name or "Hiring Team"},

I applied for the {job_title} position at {company} on {date_applied} and
wanted to follow up to confirm that my application was received. I remain
very interested in the role and would welcome the chance to discuss my
experience. Please let me know if you need any further information.

Kind regards,
{jobseeker_full_name}
```

`{contact_name}` uses the first contact linked to the application; if there is none, use "Hiring Team".

### 9.3 Testing aids (developer-facing, not in the user interface)
Because real schedules are slow to demonstrate, provide Flask CLI commands:
- `flask run-digest`: generate this week's digests now
- `flask run-nudges`: process due nudges now

The seed data (Section 11) includes an application applied 8 days ago so the nudge can be demonstrated immediately.

---

## 10. Non-functional requirements

**Security**
- Server-side authorisation on every route (Section 5.3); scope all jobseeker queries by `jobseeker_id`.
- CSRF protection on all state-changing forms; all state changes use POST.
- Password hashing; no plaintext secrets; `SECRET_KEY` from environment.
- File uploads: allow only `.pdf` and `.docx` (check extension and MIME type), 5 MB limit, random stored filenames, files stored outside the static folder and served only through authorised routes.

**Usability**
- Responsive, server-rendered UI that works on desktop and mobile widths.
- English interface; dates shown as `DD Mon YYYY`.
- Flash messages for success and error feedback; inline form validation errors.

**Data and privacy**
- PoC runs locally with demo data only; no real personal data should be used.
- Compliance work (data export, account deletion, retention) is out of scope for the PoC.

**Reliability**
- Scheduled jobs are idempotent (safe to re-run).
- Database created and seeded automatically on first run (`flask init-db` or equivalent).

---

## 11. Seed / demo data

| Account | Email | Role / status | Password |
|---------|-------|---------------|----------|
| Admin | admin@example.com | admin, active | `admin123` (demo only) |
| Adviser | adviser1@example.com | adviser, active | `adviser123` |
| Adviser | adviser2@example.com | adviser, **pending** | `adviser123` |
| Jobseeker | jobseeker1@example.com | jobseeker, active | `jobseeker123` |
| Jobseeker | jobseeker2@example.com | jobseeker, active | `jobseeker123` |

Seed content for the jobseekers:
- 6–8 applications across all four stages and all four outcomes
- At least 2 open applications with deadlines in the next 7 days
- **1 application at stage `applied` with `date_applied` 8 days ago** and no outcome (nudge demo)
- 3 CV records, one in each status (`submitted`, `approved`, `changes_requested` with comment); small placeholder PDF files
- 3–4 contacts, some linked to more than one application
- 1 pre-generated digest

---

## 12. Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `SECRET_KEY` | Session signing | required |
| `DATABASE_URL` | SQLite path | `sqlite:///instance/app.db` |
| `UPLOAD_DIR` | CV storage | `instance/uploads` |
| `MAX_UPLOAD_MB` | Upload limit | `5` |
| `APP_TIMEZONE` | Scheduler timezone | `UTC` |
| `NUDGE_DELAY_DAYS` | Days before a nudge | `7` |

---

## 13. Suggested project structure

```
job-tracker/
├── app/
│   ├── __init__.py          # app factory, extensions, scheduler start
│   ├── models.py            # SQLAlchemy models (Section 6)
│   ├── auth/                # register, login, logout, admin approval
│   ├── jobseeker/           # applications, contacts, cvs, dashboard, digests, notifications
│   ├── adviser/             # review queue, jobseeker views
│   ├── automations.py       # weekly digest + nudge jobs + CLI commands
│   ├── templates/           # Jinja2 templates (base, role-specific)
│   └── static/              # CSS, tiny JS (copy button)
├── instance/                # app.db, uploads/ (git-ignored)
├── seed.py                  # demo data (Section 11)
├── requirements.txt
├── .env.example
└── README.md                # setup + how to demo the automations
```

---

## 14. Assumptions and open decisions

These were not covered explicitly by the interview. The PoC will follow the assumptions below unless corrected.

1. **Admin role:** introduced as a third, minimal role to support adviser approval (#20).
2. **Cover letter:** recorded as a free-text reference/label on the application, not as a file upload.
3. **`accepted` outcome** is only allowed from stage `offer` (the other outcomes from any stage).
4. **Deadline widget** includes all open applications with a deadline of today or later, regardless of stage. *Possible refinement:* only stage `saved`, since a deadline matters less once applied.
5. **Contacts are private** to the jobseeker; advisers cannot see them.
6. **CVs cannot be deleted or edited** after upload (keeps the review history); applications and contacts can be deleted.
7. **Digest recipients** are jobseekers only; advisers get no digest.
8. **Digest counts** cover open stages only; closed applications are excluded.
9. **Timezone** for the Monday 08:00 schedule is configurable (`APP_TIMEZONE`, default UTC).
10. **Nudge fires once** and uses a periodic check (hourly) rather than one-off scheduled tasks, so it survives app restarts.
11. **No CV-review notification** is sent to jobseekers; they see the status badge and comment on My CVs.
12. **Password reset and email verification** are not included in the PoC.
13. **Testing CLI commands** (`run-digest`, `run-nudges`) are included for demos even though no "run now" button is requested.

---

## 15. Out of scope for the PoC

- Sending real emails (digest and nudge are in-app only)
- Calendar view, colour-coded deadline urgency, deadline reminder banners
- Outcome date/notes, outcome statistics or success-rate dashboards
- Adviser comments on applications, adviser–jobseeker assignment, cross-jobseeker overview
- Gating applications on CV approval; revoking an approval
- Repeated or configurable nudges
- Interaction logs, "last contacted" tracking or contact types
- Application source/channel field
- Password reset, email verification, social login, multi-factor authentication
- Data export, account deletion, analytics, internationalisation

---

## 16. Acceptance criteria

### Milestone 1 (Week 03)
- [ ] A visitor can register as a jobseeker and log in immediately.
- [ ] A visitor can register as an adviser; login is blocked with a "pending" message until the admin approves.
- [ ] The admin can approve or reject a pending adviser; an approved adviser can then log in.
- [ ] A jobseeker can upload a PDF/DOCX CV with title and version label; non-PDF/DOCX files and files over 5 MB are rejected.
- [ ] The CV list shows each version with status "Submitted".
- [ ] A jobseeker can create an application with all Section 6 fields, move it through stages, and set an outcome.
- [ ] The outcome shows as a colour-coded badge in the application list and detail page.
- [ ] A jobseeker cannot view another jobseeker's applications or CVs by editing the URL.

### Milestone 2
- [ ] Contacts can be created, edited, deleted, and linked to multiple applications.
- [ ] A CV version and cover letter reference can be attached to an application.
- [ ] The dashboard's "Upcoming deadlines" list shows open applications with future deadlines, sorted by date.

### Milestone 3
- [ ] The adviser review queue lists submitted CVs; an adviser can approve, or request changes with a mandatory comment.
- [ ] The reviewed CV's status badge and comment appear for the jobseeker; resubmission works via a new upload.
- [ ] Advisers can view any jobseeker's profile, CVs, and applications (with outcomes) read-only, and cannot see contacts or edit anything.

### Milestone 4
- [ ] `flask run-digest` creates one digest per active jobseeker with correct stage counts and 7-day deadlines; running it twice creates no duplicates.
- [ ] The scheduler is configured for Monday 08:00 and the Digest page lists stored digests.
- [ ] `flask run-nudges` creates exactly one notification for the seeded 8-day-old "Applied" application and none for applications with an outcome or a different stage.
- [ ] The notification shows the follow-up template with a working Copy button and an unread counter in the nav.
