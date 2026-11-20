-- schema/001_initial.sql
-- Job Application Tracker: initial schema (SQLite), built from docs/data-model.md.
-- Dates are TEXT 'YYYY-MM-DD'. The two date-times are TEXT 'YYYY-MM-DD HH:MM:SS' (UTC):
-- user.temp_password_expires_at and cv.picked_up_at.
-- PRAGMA foreign_keys = ON and PRAGMA secure_delete = ON are set per connection
-- by get_connection() in db.py, not in this file.
--
-- Each table is followed by its indexes and triggers.
-- A trigger is a rule the database runs by itself before an INSERT, UPDATE or DELETE.
-- We use triggers for rules a CHECK cannot express, because they need to look at another row or table.
--
-- "Not blank" below means more than spaces: tabs and new lines count as blank too.
-- That is why the blank test is trim(x, ' ' || char(9) || char(10) || char(13)).

-- ---------------------------------------------------------------------------
-- user: a jobseeker, a career adviser, or the one admin
-- ---------------------------------------------------------------------------
CREATE TABLE user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,                           -- PRIMARY KEY: unique id, never reused

    full_name TEXT
        NOT NULL                                                    -- NOT NULL: a name is required
        CHECK (length(trim(full_name, ' ' || char(9) || char(10) || char(13))) > 0 -- CHECK: name is not blank
           AND length(full_name) <= 30),                            -- CHECK: at most 30 characters

    email TEXT
        NOT NULL                                                    -- NOT NULL: an email is required
        UNIQUE                                                      -- UNIQUE: no two users share an email
        CHECK (email = lower(email)                                 -- CHECK: saved in lower case
           AND length(email) - length(replace(email, '@', '')) = 1  -- CHECK: exactly one "@"
           AND instr(email, '@') > 1                                -- CHECK: something before the "@"
           AND email NOT GLOB '* *'                                 -- CHECK: no spaces
           AND substr(email, instr(email, '@') + 1, 1) <> '.'       -- CHECK: the character right after the "@" is not a dot
           AND substr(email, -1) <> '.'                             -- CHECK: does not end with a dot
           AND instr(substr(email, instr(email, '@') + 1), '.') > 0), -- CHECK: a dot after the "@"

    password_hash TEXT
        NOT NULL,                                                   -- NOT NULL: only the protected form is stored

    phone TEXT
        NOT NULL                                                    -- NOT NULL: a phone number is required
        UNIQUE                                                      -- UNIQUE: no two users share a phone number
        CHECK (length(phone) BETWEEN 12 AND 14                      -- CHECK: "+353" plus 8 to 10 digits
           AND phone GLOB '+353*'                                   -- CHECK: starts with +353
           AND substr(phone, 5) NOT GLOB '*[^0-9]*'),               -- CHECK: only digits after +353

    role TEXT
        NOT NULL                                                    -- NOT NULL: every user has a role
        CHECK (role IN ('jobseeker', 'career_adviser', 'admin')),   -- CHECK: one of the three allowed roles

    approval_status TEXT
        CHECK ((role = 'career_adviser'                             -- CHECK: an adviser is 'waiting' or 'approved'
                AND approval_status IS NOT NULL
                AND approval_status IN ('waiting', 'approved'))
            OR (role <> 'career_adviser'                            -- CHECK: a jobseeker or the admin has NULL
                AND approval_status IS NULL)),

    must_change_password INTEGER
        NOT NULL                                                    -- NOT NULL: always 0 or 1
        DEFAULT 0                                                   -- DEFAULT: starts at 0 (no forced change)
        CHECK (must_change_password IN (0, 1)),                     -- CHECK: only 0 or 1

    temp_password_expires_at TEXT
        CHECK ((must_change_password = 1                            -- CHECK: flag is 1, so a real date-time is filled in
                AND datetime(temp_password_expires_at) IS NOT NULL  -- CHECK: refuse impossible dates (datetime gives NULL)
                AND datetime(temp_password_expires_at) = temp_password_expires_at -- CHECK: exact YYYY-MM-DD HH:MM:SS form
                AND substr(temp_password_expires_at, 12, 2) <> '24')        -- CHECK: refuse hour 24 (SQLite lets it through)
            OR (must_change_password = 0                            -- CHECK: flag is 0, so it must be empty
                AND temp_password_expires_at IS NULL)),

    linkedin_url TEXT
        CHECK (linkedin_url IS NULL                                 -- CHECK: optional, but if given:
            OR ((linkedin_url GLOB 'http://*'                       -- CHECK: starts with http://
                 OR linkedin_url GLOB 'https://*')                  -- CHECK: or with https://
                AND linkedin_url NOT GLOB '* *'                     -- CHECK: no spaces
                AND linkedin_url LIKE '%linkedin.com%')),           -- CHECK: rough host test (Python checks the exact host)

    city TEXT
        CHECK (city IS NULL                                         -- CHECK: optional, but if given:
            OR (length(trim(city, ' ' || char(9) || char(10) || char(13))) > 0 -- CHECK: not blank
                AND length(city) <= 20))                            -- CHECK: at most 20 characters
);

CREATE UNIQUE INDEX user_one_admin ON user (role) WHERE role = 'admin'; -- UNIQUE: at most one row can have role 'admin'

CREATE TRIGGER user_admin_cannot_be_deleted
BEFORE DELETE ON user
WHEN OLD.role = 'admin'                                             -- RULE: only fires for the admin row
BEGIN
    SELECT RAISE(ABORT, 'The admin cannot be deleted');             -- RULE: the database refuses the delete
END;

CREATE TRIGGER user_role_is_fixed
BEFORE UPDATE OF role ON user
WHEN NEW.role <> OLD.role                                           -- RULE: only fires if the role would really change
BEGIN
    SELECT RAISE(ABORT, 'A user''s role cannot be changed');        -- RULE: a role is chosen once and never changes
END;

CREATE TRIGGER user_approval_only_forward
BEFORE UPDATE OF approval_status ON user
WHEN OLD.approval_status IS NOT NEW.approval_status                 -- RULE: only fires if the status would really change
 AND NOT (OLD.approval_status IS 'waiting'                          -- RULE: the one allowed move is waiting ...
          AND NEW.approval_status IS 'approved')                    -- RULE: ... to approved
BEGIN
    SELECT RAISE(ABORT, 'Approval can only move from waiting to approved');
END;

-- ---------------------------------------------------------------------------
-- cv: one CV file uploaded by one jobseeker, with its review record
-- file_data is the LAST column on purpose: SQLite stores a big file in extra pages, and
-- reading any column that comes after it (such as review_status) means reading past the file.
-- ---------------------------------------------------------------------------
CREATE TABLE cv (
    id INTEGER PRIMARY KEY AUTOINCREMENT,                           -- PRIMARY KEY: unique id, never reused

    jobseeker_id INTEGER
        NOT NULL                                                    -- NOT NULL: every CV has an owner
        REFERENCES user (id) ON DELETE CASCADE,                     -- REFERENCES: owner is a user; deleting the owner deletes the CV

    title TEXT
        NOT NULL                                                    -- NOT NULL: a title is required
        CHECK (length(trim(title, ' ' || char(9) || char(10) || char(13))) > 0 -- CHECK: title is not blank
           AND length(title) <= 30),                                -- CHECK: at most 30 characters

    file_name TEXT
        NOT NULL                                                    -- NOT NULL: a file name is required
        CHECK (length(file_name) <= 255                             -- CHECK: at most 255 characters
           AND (lower(file_name) LIKE '_%.pdf'                      -- CHECK: ends in .pdf ...
             OR lower(file_name) LIKE '_%.doc'                      -- CHECK: ... or .doc ...
             OR lower(file_name) LIKE '_%.docx')),                  -- CHECK: ... or .docx, any letter case, with at least one character before the dot

    jobseeker_note TEXT
        CHECK (jobseeker_note IS NULL                               -- CHECK: optional, but if given:
            OR length(jobseeker_note) <= 200),                      -- CHECK: at most 200 characters

    uploaded_on TEXT
        CHECK (uploaded_on IS NULL                                  -- CHECK: optional, but if given:
            OR (date(uploaded_on) IS NOT NULL                       -- CHECK: refuse impossible dates (date gives NULL)
                AND date(uploaded_on) = uploaded_on)),              -- CHECK: exact YYYY-MM-DD form

    review_status TEXT
        NOT NULL                                                    -- NOT NULL: every CV has a status
        DEFAULT 'waiting_for_review'                                -- DEFAULT: a new CV waits for review
        CHECK (review_status IN ('waiting_for_review', 'in_review', -- CHECK: one of the five allowed statuses
                                 'approved', 'rejected', 'needs_changes')),

    reviewer_id INTEGER
        REFERENCES user (id) ON DELETE SET NULL,                    -- REFERENCES: reviewer is a user; deleting them empties this link

    picked_up_at TEXT
        CHECK (picked_up_at IS NULL                                 -- CHECK: optional, but if given:
            OR (datetime(picked_up_at) IS NOT NULL                  -- CHECK: refuse impossible date-times (datetime gives NULL)
                AND datetime(picked_up_at) = picked_up_at           -- CHECK: exact YYYY-MM-DD HH:MM:SS form
                AND substr(picked_up_at, 12, 2) <> '24')),          -- CHECK: refuse hour 24 (SQLite lets it through)

    reviewed_on TEXT
        CHECK (reviewed_on IS NULL                                  -- CHECK: optional, but if given:
            OR (date(reviewed_on) IS NOT NULL                       -- CHECK: refuse impossible dates (date gives NULL)
                AND date(reviewed_on) = reviewed_on)),              -- CHECK: exact YYYY-MM-DD form

    review_comment TEXT
        CHECK (review_comment IS NULL                               -- CHECK: optional, but if given:
            OR length(review_comment) <= 200),                      -- CHECK: at most 200 characters

    file_data BLOB
        NOT NULL                                                    -- NOT NULL: the file itself is required
        CHECK (typeof(file_data) = 'blob'                           -- CHECK: stored as a real BLOB, not as text
           AND length(file_data) > 0                                -- CHECK: the file is not empty
           AND length(file_data) <= 5242880),                       -- CHECK: at most 5,242,880 bytes (5 MB)

    -- The matching rule for reviews: status decides which review fields are filled.
    CHECK (
        (review_status = 'waiting_for_review'                       -- CHECK: waiting -> nothing filled in
            AND reviewer_id IS NULL
            AND picked_up_at IS NULL
            AND reviewed_on IS NULL
            AND review_comment IS NULL)
        OR (review_status = 'in_review'                             -- CHECK: in review -> reviewer and pick-up time only
            AND reviewer_id IS NOT NULL
            AND picked_up_at IS NOT NULL
            AND reviewed_on IS NULL
            AND review_comment IS NULL)
        OR (review_status = 'approved'                              -- CHECK: approved -> reviewer and date; comment optional
            AND reviewer_id IS NOT NULL
            AND picked_up_at IS NULL
            AND reviewed_on IS NOT NULL)
        OR (review_status IN ('rejected', 'needs_changes')          -- CHECK: rejected / needs changes -> reviewer, date and comment
            AND reviewer_id IS NOT NULL
            AND picked_up_at IS NULL
            AND reviewed_on IS NOT NULL
            AND review_comment IS NOT NULL                          -- CHECK: the comment is required ...
            AND length(trim(review_comment, ' ' || char(9) || char(10) || char(13))) > 0) -- CHECK: ... and not blank
    )
);

-- Indexes: SQLite does not index a foreign key by itself. These make lists and cascades fast.
CREATE INDEX cv_jobseeker_id_idx ON cv (jobseeker_id);              -- INDEX: a jobseeker's CVs, and the cascade on account delete
CREATE INDEX cv_reviewer_id_idx ON cv (reviewer_id);                -- INDEX: an adviser's CVs, and the reset on adviser delete
CREATE INDEX cv_review_status_idx ON cv (review_status);            -- INDEX: the "waiting for review" list and the 7-day check

CREATE TRIGGER cv_owner_is_jobseeker
BEFORE INSERT ON cv
WHEN (SELECT role FROM user WHERE id = NEW.jobseeker_id) IS NOT 'jobseeker' -- RULE: the owner must be a jobseeker
BEGIN
    SELECT RAISE(ABORT, 'A CV must belong to a jobseeker');
END;

CREATE TRIGGER cv_reviewer_is_approved_adviser_on_insert
BEFORE INSERT ON cv
WHEN NEW.reviewer_id IS NOT NULL                                    -- RULE: only checked when there is a reviewer
 AND NOT EXISTS (SELECT 1 FROM user
                 WHERE id = NEW.reviewer_id
                   AND role = 'career_adviser'                      -- RULE: the reviewer is an adviser ...
                   AND approval_status = 'approved')                -- RULE: ... who has been approved
BEGIN
    SELECT RAISE(ABORT, 'The reviewer must be an approved career adviser');
END;

CREATE TRIGGER cv_reviewer_is_approved_adviser_on_update
BEFORE UPDATE OF reviewer_id ON cv
WHEN NEW.reviewer_id IS NOT NULL                                    -- RULE: same rule when the reviewer is set later
 AND NOT EXISTS (SELECT 1 FROM user
                 WHERE id = NEW.reviewer_id
                   AND role = 'career_adviser'
                   AND approval_status = 'approved')
BEGIN
    SELECT RAISE(ABORT, 'The reviewer must be an approved career adviser');
END;

CREATE TRIGGER cv_content_is_read_only
BEFORE UPDATE OF jobseeker_id, title, file_name, file_data, jobseeker_note, uploaded_on ON cv
WHEN NEW.jobseeker_id IS NOT OLD.jobseeker_id                       -- RULE: only fires if one of these would really change
  OR NEW.title IS NOT OLD.title
  OR NEW.file_name IS NOT OLD.file_name
  OR NEW.file_data IS NOT OLD.file_data
  OR NEW.jobseeker_note IS NOT OLD.jobseeker_note
  OR NEW.uploaded_on IS NOT OLD.uploaded_on
BEGIN
    SELECT RAISE(ABORT, 'A CV cannot be edited after upload');      -- RULE: only the review columns may change
END;

-- This trigger belongs to the user table, but it works on cv, so it sits here after cv is created.
CREATE TRIGGER user_adviser_delete_resets_cvs
BEFORE DELETE ON user
WHEN OLD.role = 'career_adviser'                                    -- RULE: only fires when an adviser is deleted
BEGIN
    UPDATE cv                                                       -- RULE: every CV of this adviser, in any status,
    SET review_status = 'waiting_for_review',                       -- RULE: goes back to waiting
        reviewer_id = NULL,                                         -- RULE: with no reviewer,
        picked_up_at = NULL,                                        -- RULE: no pick-up time,
        reviewed_on = NULL,                                         -- RULE: no review date,
        review_comment = NULL                                       -- RULE: and no comment
    WHERE reviewer_id = OLD.id;
END;

-- ---------------------------------------------------------------------------
-- application: one job application recorded by one jobseeker
-- ---------------------------------------------------------------------------
CREATE TABLE application (
    id INTEGER PRIMARY KEY AUTOINCREMENT,                           -- PRIMARY KEY: unique id, never reused

    jobseeker_id INTEGER
        NOT NULL                                                    -- NOT NULL: every application has an owner
        REFERENCES user (id) ON DELETE CASCADE,                     -- REFERENCES: owner is a user; deleting the owner deletes the application

    job_title TEXT
        NOT NULL                                                    -- NOT NULL: a job title is required
        CHECK (length(trim(job_title, ' ' || char(9) || char(10) || char(13))) > 0 -- CHECK: not blank
           AND length(job_title) <= 40),                            -- CHECK: at most 40 characters

    company TEXT
        NOT NULL                                                    -- NOT NULL: a company is required
        CHECK (length(trim(company, ' ' || char(9) || char(10) || char(13))) > 0 -- CHECK: not blank
           AND length(company) <= 30),                              -- CHECK: at most 30 characters

    applied_on TEXT
        NOT NULL                                                    -- NOT NULL: the application date is required
        CHECK (date(applied_on) IS NOT NULL                         -- CHECK: refuse impossible dates (date gives NULL)
           AND date(applied_on) = applied_on),                      -- CHECK: exact YYYY-MM-DD form

    progress TEXT
        NOT NULL                                                    -- NOT NULL: every application has a progress value
        DEFAULT 'applied'                                           -- DEFAULT: starts as 'applied'
        CHECK (progress IN ('applied', 'interview', 'accepted',     -- CHECK: one of the five allowed values
                            'rejected', 'withdrawn')),

    location TEXT
        CHECK (location IS NULL                                     -- CHECK: optional, but if given:
            OR length(location) <= 20),                             -- CHECK: at most 20 characters

    advert_url TEXT
        CHECK (advert_url IS NULL                                   -- CHECK: optional, but if given:
            OR ((advert_url GLOB 'http://*'                         -- CHECK: starts with http://
                 OR advert_url GLOB 'https://*')                    -- CHECK: or with https://
                AND advert_url NOT GLOB '* *')),                    -- CHECK: no spaces

    note TEXT
        CHECK (note IS NULL                                         -- CHECK: optional, but if given:
            OR length(note) <= 200)                                 -- CHECK: at most 200 characters
);

CREATE INDEX application_jobseeker_id_idx ON application (jobseeker_id); -- INDEX: a jobseeker's applications, and the cascade on account delete

CREATE TRIGGER application_owner_is_jobseeker_on_insert
BEFORE INSERT ON application
WHEN (SELECT role FROM user WHERE id = NEW.jobseeker_id) IS NOT 'jobseeker' -- RULE: the owner must be a jobseeker
BEGIN
    SELECT RAISE(ABORT, 'An application must belong to a jobseeker');
END;

CREATE TRIGGER application_owner_is_jobseeker_on_update
BEFORE UPDATE OF jobseeker_id ON application
WHEN (SELECT role FROM user WHERE id = NEW.jobseeker_id) IS NOT 'jobseeker' -- RULE: same rule if the owner is changed later
BEGIN
    SELECT RAISE(ABORT, 'An application must belong to a jobseeker');
END;
