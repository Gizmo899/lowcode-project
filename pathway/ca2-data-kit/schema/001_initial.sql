-- schema/001_initial.sql
-- Builds the Job Application Tracker database exactly as described in docs/data-model.md.
-- SQLite syntax. Dates are TEXT in the form YYYY-MM-DD.
-- PRAGMA foreign_keys = ON is NOT written here: every connection must run it through get_connection() in db.py.
-- A date is checked with: date(x) IS x. That is true only for a real calendar date written as YYYY-MM-DD.


-- =====================================================================
-- user: one person with an account (jobseeker or adviser)
-- =====================================================================
CREATE TABLE user (
    id INTEGER PRIMARY KEY,            -- PRIMARY KEY: a unique number for each person
    full_name TEXT NOT NULL                          -- NOT NULL: a name is required
        CHECK (length(trim(full_name)) > 0),         -- CHECK: the name must not be blank
    email TEXT NOT NULL                              -- NOT NULL: an email is required
        COLLATE NOCASE                               -- COLLATE NOCASE: Anna@x.com and anna@x.com count as the same email
        UNIQUE,                                      -- UNIQUE: one email belongs to one account, whatever the role
    password_hash TEXT NOT NULL,                     -- NOT NULL: the scrambled password is required (never the real one)
    phone TEXT                                       -- optional field
        UNIQUE                                       -- UNIQUE: no two people share a phone number (many can leave it empty)
        CHECK (phone IS NULL OR length(trim(phone)) > 0),  -- CHECK: a blank phone must be NULL, never empty text
    role TEXT NOT NULL                               -- NOT NULL: every person has a role
        CHECK (role IN ('jobseeker', 'adviser')),    -- CHECK: only these two roles exist
    assigned_adviser_id INTEGER                      -- optional: the jobseeker's chosen adviser (empty = awaiting adviser)
        REFERENCES user(id) ON DELETE SET NULL,      -- REFERENCES: must be a real user. SET NULL: if that adviser is deleted, the link empties and the jobseeker stays (Delete rule 2)
    CHECK (role = 'jobseeker' OR assigned_adviser_id IS NULL)  -- CHECK: only a jobseeker can have an assigned adviser
);

CREATE TRIGGER trg_user_role_never_changes
BEFORE UPDATE OF role ON user
WHEN NEW.role IS NOT OLD.role                        -- rule applies only when the role is being changed
BEGIN
    SELECT RAISE(ABORT, 'A role can never be changed after the account is created');  -- refuse the change
END;

CREATE TRIGGER trg_user_adviser_must_be_adviser_insert
BEFORE INSERT ON user
WHEN NEW.assigned_adviser_id IS NOT NULL             -- rule applies only when an adviser is being linked
BEGIN
    SELECT CASE
        WHEN (SELECT role FROM user WHERE id = NEW.assigned_adviser_id) IS NOT 'adviser'  -- the linked person must have the role adviser
        THEN RAISE(ABORT, 'The assigned adviser must be a user with the role adviser')    -- refuse otherwise
    END;
END;

CREATE TRIGGER trg_user_adviser_must_be_adviser_update
BEFORE UPDATE OF assigned_adviser_id ON user
WHEN NEW.assigned_adviser_id IS NOT NULL             -- rule applies only when an adviser is being linked
BEGIN
    SELECT CASE
        WHEN (SELECT role FROM user WHERE id = NEW.assigned_adviser_id) IS NOT 'adviser'  -- the linked person must have the role adviser
        THEN RAISE(ABORT, 'The assigned adviser must be a user with the role adviser')    -- refuse otherwise
    END;
END;

CREATE TRIGGER trg_user_adviser_choice_is_once_only
BEFORE UPDATE OF assigned_adviser_id ON user
WHEN OLD.assigned_adviser_id IS NOT NULL             -- there is already an adviser...
 AND NEW.assigned_adviser_id IS NOT NULL             -- ...and a new adviser is being put in directly...
 AND NEW.assigned_adviser_id != OLD.assigned_adviser_id  -- ...that is a different one
BEGIN
    SELECT RAISE(ABORT, 'The adviser choice cannot be switched to a different adviser');  -- refuse the switch (emptying the link is still allowed)
END;


-- =====================================================================
-- cv: one CV file uploaded by one jobseeker, plus the adviser's decision
-- =====================================================================
CREATE TABLE cv (
    id INTEGER PRIMARY KEY,            -- PRIMARY KEY: a unique number for each CV
    jobseeker_id INTEGER NOT NULL                    -- NOT NULL: every CV has an owner
        REFERENCES user(id) ON DELETE CASCADE,       -- REFERENCES: the owner must be a real user. CASCADE: deleting the jobseeker deletes their CVs (Delete rule 1)
    title TEXT NOT NULL                              -- NOT NULL: a title is required
        CHECK (length(trim(title)) > 0),             -- CHECK: the title must not be blank
    file_name TEXT NOT NULL,                         -- NOT NULL: the original file name is required
    file_type TEXT NOT NULL                          -- NOT NULL: the file type is required
        CHECK (file_type IN ('pdf', 'doc', 'docx')), -- CHECK: only Word or PDF files
    file_data BLOB NOT NULL                          -- NOT NULL: the file itself is required
        CHECK (typeof(file_data) = 'blob'            -- CHECK: it must be stored as a file (bytes), so the size check counts bytes
           AND length(file_data) BETWEEN 1 AND 1048576),  -- CHECK: not empty, and at most 1,048,576 bytes (1 MB)
    uploaded_at TEXT NOT NULL DEFAULT (date('now'))  -- NOT NULL: filled in automatically with today's date
        CHECK (date(uploaded_at) IS uploaded_at),    -- CHECK: a real date written as YYYY-MM-DD
    status TEXT NOT NULL DEFAULT 'waiting_for_review'  -- NOT NULL: starts as waiting_for_review
        CHECK (status IN ('waiting_for_review', 'approved', 'rejected')),  -- CHECK: only these three stages
    decided_by INTEGER                               -- optional: the adviser who decided (empty until a decision)
        REFERENCES user(id) ON DELETE SET NULL,      -- REFERENCES: must be a real user. SET NULL: if that adviser is deleted, the CV stays and only this link empties (Delete rule 3)
    decided_at TEXT                                  -- optional: the decision date (empty until a decision)
        CHECK (decided_at IS NULL OR date(decided_at) IS decided_at),  -- CHECK: if given, a real date written as YYYY-MM-DD
    comment TEXT                                     -- optional: the adviser's comment on a rejection
        CHECK (comment IS NULL OR length(trim(comment)) > 0),  -- CHECK: a comment must not be blank (leave it NULL instead)
    CHECK (                                          -- CHECK: the status and the decision fields must agree
        (status = 'waiting_for_review'               -- waiting: no decision, no adviser, no comment
            AND decided_by IS NULL AND decided_at IS NULL AND comment IS NULL)
        OR (status = 'approved'                      -- approved: has a decision date, never a comment
            AND decided_at IS NOT NULL AND comment IS NULL)
        OR (status = 'rejected'                      -- rejected: has a decision date, comment is optional
            AND decided_at IS NOT NULL)
    )
);

CREATE TRIGGER trg_cv_owner_must_be_jobseeker_insert
BEFORE INSERT ON cv
BEGIN
    SELECT CASE
        WHEN (SELECT role FROM user WHERE id = NEW.jobseeker_id) IS NOT 'jobseeker'  -- the owner must have the role jobseeker
        THEN RAISE(ABORT, 'A CV must belong to a jobseeker')                          -- refuse otherwise
    END;
END;

CREATE TRIGGER trg_cv_owner_must_be_jobseeker_update
BEFORE UPDATE OF jobseeker_id ON cv
BEGIN
    SELECT CASE
        WHEN (SELECT role FROM user WHERE id = NEW.jobseeker_id) IS NOT 'jobseeker'  -- the owner must have the role jobseeker
        THEN RAISE(ABORT, 'A CV must belong to a jobseeker')                          -- refuse otherwise
    END;
END;

CREATE TRIGGER trg_cv_new_cv_starts_waiting
BEFORE INSERT ON cv
WHEN NEW.status != 'waiting_for_review'              -- rule applies when a CV is added already decided
BEGIN
    SELECT RAISE(ABORT, 'A new CV must start as waiting_for_review');  -- refuse: a new CV always starts waiting
END;

CREATE TRIGGER trg_cv_decider_must_be_owners_adviser
BEFORE UPDATE OF decided_by ON cv
WHEN NEW.decided_by IS NOT NULL                      -- rule applies when an adviser is being recorded as decider
BEGIN
    SELECT CASE
        WHEN NEW.decided_by IS NOT (SELECT assigned_adviser_id FROM user WHERE id = NEW.jobseeker_id)  -- must be the adviser assigned to the CV's owner
        THEN RAISE(ABORT, 'Only the adviser assigned to the CV owner can decide this CV')             -- refuse otherwise
    END;
END;

CREATE TRIGGER trg_cv_decision_needs_owners_adviser
BEFORE UPDATE OF status ON cv
WHEN OLD.status = 'waiting_for_review'               -- the CV was waiting...
 AND NEW.status != 'waiting_for_review'              -- ...and is now being decided
BEGIN
    SELECT CASE
        WHEN NEW.decided_by IS NULL                  -- a decision must name the adviser...
          OR NEW.decided_by IS NOT (SELECT assigned_adviser_id FROM user WHERE id = NEW.jobseeker_id)  -- ...and it must be the owner's assigned adviser
        THEN RAISE(ABORT, 'A decision must be recorded by the adviser assigned to the CV owner')      -- refuse otherwise
    END;
END;


-- =====================================================================
-- job_application: one job that one jobseeker has applied for
-- =====================================================================
CREATE TABLE job_application (
    id INTEGER PRIMARY KEY,            -- PRIMARY KEY: a unique number for each application
    jobseeker_id INTEGER NOT NULL                    -- NOT NULL: every application has an owner
        REFERENCES user(id) ON DELETE CASCADE,       -- REFERENCES: the owner must be a real user. CASCADE: deleting the jobseeker deletes their applications (Delete rule 1)
    company_name TEXT NOT NULL                       -- NOT NULL: the company is required
        CHECK (length(trim(company_name)) > 0),      -- CHECK: must not be blank
    job_title TEXT NOT NULL                          -- NOT NULL: the job title is required
        CHECK (length(trim(job_title)) > 0),         -- CHECK: must not be blank
    date_applied TEXT NOT NULL                       -- NOT NULL: the date applied is required
        CHECK (date(date_applied) IS date_applied),  -- CHECK: a real date written as YYYY-MM-DD (a future date is refused by the app, not here)
    status TEXT NOT NULL DEFAULT 'applied'           -- NOT NULL: starts as applied
        CHECK (status IN ('applied', 'interview', 'rejected', 'withdrawn')),  -- CHECK: only these four stages
    advert_url TEXT                                  -- optional: link to the job advert
        CHECK (advert_url IS NULL                    -- CHECK: either empty...
            OR ((advert_url LIKE 'http://%' OR advert_url LIKE 'https://%')  -- ...or starting with http:// or https://...
                AND instr(advert_url, ' ') = 0)),    -- ...and containing no spaces
    notes TEXT                                       -- optional: the jobseeker's own notes (no rule)
);

CREATE TRIGGER trg_job_application_owner_must_be_jobseeker_insert
BEFORE INSERT ON job_application
BEGIN
    SELECT CASE
        WHEN (SELECT role FROM user WHERE id = NEW.jobseeker_id) IS NOT 'jobseeker'  -- the owner must have the role jobseeker
        THEN RAISE(ABORT, 'A job application must belong to a jobseeker')             -- refuse otherwise
    END;
END;

CREATE TRIGGER trg_job_application_owner_must_be_jobseeker_update
BEFORE UPDATE OF jobseeker_id ON job_application
BEGIN
    SELECT CASE
        WHEN (SELECT role FROM user WHERE id = NEW.jobseeker_id) IS NOT 'jobseeker'  -- the owner must have the role jobseeker
        THEN RAISE(ABORT, 'A job application must belong to a jobseeker')             -- refuse otherwise
    END;
END;

CREATE TRIGGER trg_job_application_new_starts_applied
BEFORE INSERT ON job_application
WHEN NEW.status != 'applied'                         -- rule applies when an application is added at another stage
BEGIN
    SELECT RAISE(ABORT, 'A new job application must start as applied');  -- refuse: a new application always starts as applied
END;


-- =====================================================================
-- follow_up_reminder: one planned follow-up nudge for one application
-- =====================================================================
CREATE TABLE follow_up_reminder (
    id INTEGER PRIMARY KEY,            -- PRIMARY KEY: a unique number for each reminder
    application_id INTEGER NOT NULL                  -- NOT NULL: every reminder belongs to an application
        REFERENCES job_application(id) ON DELETE CASCADE,  -- REFERENCES: must be a real application. CASCADE: deleting the application deletes its reminders (matches Delete rule 1)
    due_on TEXT NOT NULL                             -- NOT NULL: the due date is required
        CHECK (date(due_on) IS due_on),              -- CHECK: a real date written as YYYY-MM-DD
    status TEXT NOT NULL DEFAULT 'pending'           -- NOT NULL: starts as pending
        CHECK (status IN ('pending', 'sent', 'skipped')),  -- CHECK: only these three states
    processed_on TEXT                                -- optional: the date it was sent or skipped
        CHECK (processed_on IS NULL OR date(processed_on) IS processed_on),  -- CHECK: if given, a real date written as YYYY-MM-DD
    created_on TEXT NOT NULL DEFAULT (date('now'))   -- NOT NULL: filled in automatically with today's date
        CHECK (date(created_on) IS created_on),      -- CHECK: a real date written as YYYY-MM-DD
    CHECK (                                          -- CHECK: the state and the processed date must agree
        (status = 'pending' AND processed_on IS NULL)           -- pending: not processed yet
        OR (status IN ('sent', 'skipped') AND processed_on IS NOT NULL)  -- sent or skipped: has a processed date
    )
);

CREATE UNIQUE INDEX idx_one_pending_reminder_per_application
    ON follow_up_reminder(application_id)            -- UNIQUE: at most one row per application...
    WHERE status = 'pending';                        -- ...among the pending ones, so two waiting nudges can never exist


-- =====================================================================
-- notification: one short in-app message for one jobseeker
-- =====================================================================
CREATE TABLE notification (
    id INTEGER PRIMARY KEY,            -- PRIMARY KEY: a unique number for each notification
    user_id INTEGER NOT NULL                         -- NOT NULL: every notification has an owner
        REFERENCES user(id) ON DELETE CASCADE,       -- REFERENCES: the owner must be a real user. CASCADE: deleting the jobseeker deletes their notifications (Delete rule 1)
    kind TEXT NOT NULL                               -- NOT NULL: the kind is required
        CHECK (kind IN ('nudge', 'digest', 'cv_decision')),  -- CHECK: only these three kinds
    message TEXT NOT NULL                            -- NOT NULL: the message is required
        CHECK (length(trim(message)) > 0),           -- CHECK: must not be blank
    created_at TEXT NOT NULL                         -- NOT NULL: the creation date is required (the app supplies it)
        CHECK (date(created_at) IS created_at),      -- CHECK: a real date written as YYYY-MM-DD
    is_read INTEGER NOT NULL DEFAULT 0               -- NOT NULL: starts as unread
        CHECK (is_read IN (0, 1))                    -- CHECK: only 0 (unread) or 1 (read)
);

CREATE TRIGGER trg_notification_owner_must_be_jobseeker_insert
BEFORE INSERT ON notification
BEGIN
    SELECT CASE
        WHEN (SELECT role FROM user WHERE id = NEW.user_id) IS NOT 'jobseeker'  -- the owner must have the role jobseeker
        THEN RAISE(ABORT, 'A notification must belong to a jobseeker')           -- refuse otherwise
    END;
END;

CREATE TRIGGER trg_notification_owner_must_be_jobseeker_update
BEFORE UPDATE OF user_id ON notification
BEGIN
    SELECT CASE
        WHEN (SELECT role FROM user WHERE id = NEW.user_id) IS NOT 'jobseeker'  -- the owner must have the role jobseeker
        THEN RAISE(ABORT, 'A notification must belong to a jobseeker')           -- refuse otherwise
    END;
END;
