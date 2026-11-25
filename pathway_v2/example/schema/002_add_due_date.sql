-- 002_add_due_date.sql
-- Added after testing: the committee wants to see overdue items.
-- This runs on a database that already has loans in it, so:
--   * the new column must allow NULL (existing rows have no value yet)
--   * we fill in a sensible value for existing rows straight away.

ALTER TABLE loan ADD COLUMN due_on TEXT
    CHECK (due_on IS NULL OR due_on >= borrowed_on);

-- Existing loans: assume the club's standard 14-day loan period.
UPDATE loan SET due_on = date(borrowed_on, '+14 days') WHERE due_on IS NULL;
