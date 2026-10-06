-- Fixed schema from the hackathon guide, Annex C. Columns may be added, never renamed/removed.
-- Synthetic data only. Student IDs S9000-S9999 and course codes JDG* are reserved for judges.

CREATE TABLE IF NOT EXISTS students (
    student_id        TEXT PRIMARY KEY,          -- S + 4 digits
    full_name         TEXT NOT NULL,             -- synthetic names only
    programme         TEXT NOT NULL,             -- e.g. "B.Tech CSE"
    batch_year        INTEGER NOT NULL,          -- year of admission
    current_semester  INTEGER NOT NULL CHECK (current_semester BETWEEN 1 AND 10),
    cgpa              REAL NOT NULL CHECK (cgpa BETWEEN 0 AND 10),
    active_backlogs   INTEGER NOT NULL CHECK (active_backlogs >= 0)
);

CREATE TABLE IF NOT EXISTS courses (
    course_code  TEXT PRIMARY KEY,
    course_name  TEXT NOT NULL,
    programme    TEXT NOT NULL,                  -- must match students.programme
    semester     INTEGER NOT NULL,
    credits      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS attendance (
    student_id        TEXT NOT NULL REFERENCES students(student_id),
    course_code       TEXT NOT NULL REFERENCES courses(course_code),
    classes_held      INTEGER NOT NULL CHECK (classes_held > 0),
    classes_attended  INTEGER NOT NULL CHECK (classes_attended >= 0),
    PRIMARY KEY (student_id, course_code)
    -- attendance % is computed by tools, never stored
);

CREATE TABLE IF NOT EXISTS results (
    student_id      TEXT NOT NULL REFERENCES students(student_id),
    course_code     TEXT NOT NULL REFERENCES courses(course_code),
    exam_session    TEXT NOT NULL,               -- e.g. 2026-MAY
    exam_type       TEXT NOT NULL,               -- REGULAR | SUPPLEMENTARY
    internal_marks  INTEGER NOT NULL,
    external_marks  INTEGER NOT NULL,
    total_marks     INTEGER NOT NULL,            -- = internal + external
    max_marks       INTEGER NOT NULL,
    result          TEXT NOT NULL,               -- PASS | FAIL | ABSENT | DETAINED
    PRIMARY KEY (student_id, course_code, exam_session, exam_type)
);

CREATE TABLE IF NOT EXISTS rule_registry (
    rule_id           TEXT PRIMARY KEY,          -- e.g. ATT-MIN-01
    description       TEXT NOT NULL,
    parameter         TEXT NOT NULL,             -- e.g. min_attendance_pct
    operator          TEXT NOT NULL,             -- >=, <=, ==, !=, >, <, between, in
    value             TEXT NOT NULL,             -- threshold value(s); "65,75" for between, "FAIL;ABSENT" for in
    scope_programmes  TEXT,                      -- ALL or list
    scope_batches     TEXT,                      -- ALL, 2023+, or list
    effective_from    TEXT,
    effective_to      TEXT,
    source_doc_id     TEXT NOT NULL,             -- must exist in the Source Register
    source_section    TEXT
);
