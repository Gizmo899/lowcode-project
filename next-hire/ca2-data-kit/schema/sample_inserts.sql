-- sample_inserts.sql
-- Sample INSERT statements for schema/001_initial.sql (Job Application Tracker).
-- Run them in this order, on an empty database that was created from 001_initial.sql.
-- Passwords below are placeholders, not real hashes.

-- Same setting that get_connection() turns on. Keep this line if you run the file
-- in the sqlite3 shell, where foreign-key checking starts switched off.
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- 0. One good row in the parent table.
--    user is the only parent table: cv and application both point at user(id).
--    On an empty table this row gets id 1.
-- ---------------------------------------------------------------------------
INSERT INTO user (full_name, email, password_hash, phone, role, approval_status,
                  must_change_password, temp_password_expires_at, linkedin_url, city)
VALUES ('Aoife Murphy',
        'aoife.murphy@example.ie',
        'placeholder-hash-1',
        '+353871234567',
        'jobseeker',
        NULL,
        0,
        NULL,
        'https://www.linkedin.com/in/aoife-murphy',
        'Dublin');

-- ---------------------------------------------------------------------------
-- A. A row that repeats a UNIQUE value.
--    The email is the same as the row above. The phone number is different.
-- ---------------------------------------------------------------------------
INSERT INTO user (full_name, email, password_hash, phone, role, approval_status,
                  must_change_password, temp_password_expires_at, linkedin_url, city)
VALUES ('Ciaran Doyle',
        'aoife.murphy@example.ie',
        'placeholder-hash-2',
        '+353861112223',
        'jobseeker',
        NULL,
        0,
        NULL,
        NULL,
        'Cork');

-- ---------------------------------------------------------------------------
-- B. A row that breaks a CHECK rule.
--    The role is 'manager', which is not one of 'jobseeker', 'career_adviser', 'admin'.
--    The email and phone number are not used by any other row.
-- ---------------------------------------------------------------------------
INSERT INTO user (full_name, email, password_hash, phone, role, approval_status,
                  must_change_password, temp_password_expires_at, linkedin_url, city)
VALUES ('Liam Byrne',
        'liam.byrne@example.ie',
        'placeholder-hash-3',
        '+353851234500',
        'manager',
        NULL,
        0,
        NULL,
        NULL,
        'Galway');

-- ---------------------------------------------------------------------------
-- C. A child row whose foreign key points at id 999.
--    application.jobseeker_id references user(id), and no row above has id 999.
--    Every other column holds an ordinary value.
-- ---------------------------------------------------------------------------
INSERT INTO application (jobseeker_id, job_title, company, applied_on, progress,
                         location, advert_url, note)
VALUES (999,
        'Junior Data Analyst',
        'Example Ltd',
        '2026-11-10',
        'applied',
        'Dublin',
        'https://example.ie/jobs/123',
        'Applied through the company website.');
