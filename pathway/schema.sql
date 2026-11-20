PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('jobseeker', 'career_adviser')),
    full_name TEXT NOT NULL,
    phone TEXT,
    assigned_adviser_id INTEGER REFERENCES users(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL,
    account_status TEXT NOT NULL CHECK (account_status IN ('active', 'awaiting_adviser')),
    CHECK (role != 'career_adviser' OR assigned_adviser_id IS NULL),
    CHECK (role != 'career_adviser' OR phone IS NULL OR phone = '')
);

CREATE INDEX IF NOT EXISTS idx_users_assigned_adviser
    ON users(assigned_adviser_id);
CREATE INDEX IF NOT EXISTS idx_users_role_status
    ON users(role, account_status);

CREATE TRIGGER IF NOT EXISTS trg_assigned_user_must_be_adviser_insert
BEFORE INSERT ON users
WHEN NEW.assigned_adviser_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN NEW.role != 'jobseeker'
        THEN RAISE(ABORT, 'Only jobseekers can have an assigned adviser')
        WHEN (SELECT role FROM users WHERE id = NEW.assigned_adviser_id) != 'career_adviser'
        THEN RAISE(ABORT, 'Assigned user must be a career adviser')
    END;
END;

CREATE TRIGGER IF NOT EXISTS trg_assigned_user_must_be_adviser_update
BEFORE UPDATE OF assigned_adviser_id ON users
WHEN NEW.assigned_adviser_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN NEW.role != 'jobseeker'
        THEN RAISE(ABORT, 'Only jobseekers can have an assigned adviser')
        WHEN (SELECT role FROM users WHERE id = NEW.assigned_adviser_id) != 'career_adviser'
        THEN RAISE(ABORT, 'Assigned user must be a career adviser')
    END;
END;

CREATE TRIGGER IF NOT EXISTS trg_adviser_assignment_is_permanent
BEFORE UPDATE OF assigned_adviser_id ON users
WHEN OLD.assigned_adviser_id IS NOT NULL
 AND NEW.assigned_adviser_id IS NOT OLD.assigned_adviser_id
BEGIN
    SELECT RAISE(ABORT, 'Adviser assignment is permanent');
END;

CREATE TRIGGER IF NOT EXISTS trg_user_role_is_immutable
BEFORE UPDATE OF role ON users
WHEN NEW.role != OLD.role
BEGIN
    SELECT RAISE(ABORT, 'Account role cannot be changed');
END;

CREATE TABLE IF NOT EXISTS cv_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jobseeker_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stored_filename TEXT NOT NULL UNIQUE,
    original_filename TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    approval_status TEXT NOT NULL CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TEXT,
    is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_cv_versions_jobseeker
    ON cv_versions(jobseeker_id, uploaded_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_current_cv_per_jobseeker
    ON cv_versions(jobseeker_id) WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS cv_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cv_version_id INTEGER NOT NULL REFERENCES cv_versions(id) ON DELETE CASCADE,
    adviser_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    comments TEXT NOT NULL CHECK (length(trim(comments)) > 0),
    reviewed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cv_reviews_version
    ON cv_reviews(cv_version_id, reviewed_at DESC);

CREATE TABLE IF NOT EXISTS job_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jobseeker_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    employer_name TEXT NOT NULL,
    job_title TEXT NOT NULL,
    date_applied TEXT NOT NULL,
    job_url TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('Applied', 'Successful', 'Unsuccessful', 'Withdrawn')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_applications_jobseeker
    ON job_applications(jobseeker_id, date_applied DESC);
CREATE INDEX IF NOT EXISTS idx_applications_status
    ON job_applications(jobseeker_id, status);

CREATE TABLE IF NOT EXISTS follow_up_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES job_applications(id) ON DELETE CASCADE,
    due_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'skipped')),
    processed_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reminders_due
    ON follow_up_reminders(status, due_at);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    related_application_id INTEGER REFERENCES job_applications(id) ON DELETE SET NULL,
    related_cv_version_id INTEGER REFERENCES cv_versions(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    read_at TEXT,
    deduplication_key TEXT UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_notifications_user
    ON notifications(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS automation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_key TEXT NOT NULL UNIQUE,
    task_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    result_summary TEXT
);

CREATE TABLE IF NOT EXISTS login_attempts (
    identity_hash TEXT PRIMARY KEY,
    failed_count INTEGER NOT NULL,
    window_started_at TEXT NOT NULL,
    last_attempt_at TEXT NOT NULL
);
