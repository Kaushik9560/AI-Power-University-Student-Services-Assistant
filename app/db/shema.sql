PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    programme TEXT NOT NULL,
    batch_year INTEGER NOT NULL CHECK (batch_year > 0),
    current_semester INTEGER NOT NULL CHECK (current_semester > 0),
    cgpa REAL NOT NULL CHECK (cgpa >= 0.0),
    active_backlogs INTEGER NOT NULL CHECK (active_backlogs >= 0)
);

CREATE TABLE IF NOT EXISTS courses (
    course_code TEXT PRIMARY KEY,
    course_name TEXT NOT NULL,
    programme TEXT NOT NULL,
    semester INTEGER NOT NULL CHECK (semester > 0),
    credits INTEGER NOT NULL CHECK (credits > 0)
);

CREATE TABLE IF NOT EXISTS attendance (
    student_id TEXT NOT NULL,
    course_code TEXT NOT NULL,
    classes_held INTEGER NOT NULL CHECK (classes_held > 0),
    classes_attended INTEGER NOT NULL CHECK (classes_attended >= 0),
    PRIMARY KEY (student_id, course_code),
    CHECK (classes_attended <= classes_held),
    FOREIGN KEY (student_id) REFERENCES students (student_id),
    FOREIGN KEY (course_code) REFERENCES courses (course_code)
);

CREATE TABLE IF NOT EXISTS results (
    student_id TEXT NOT NULL,
    course_code TEXT NOT NULL,
    exam_session TEXT NOT NULL,
    exam_type TEXT NOT NULL,
    internal_marks INTEGER NOT NULL CHECK (internal_marks >= 0),
    external_marks INTEGER NOT NULL CHECK (external_marks >= 0),
    total_marks INTEGER NOT NULL CHECK (total_marks >= 0),
    max_marks INTEGER NOT NULL CHECK (max_marks > 0),
    result TEXT NOT NULL CHECK (result IN ('PASS', 'FAIL', 'ABSENT')),
    PRIMARY KEY (student_id, course_code, exam_session),
    FOREIGN KEY (student_id) REFERENCES students (student_id),
    FOREIGN KEY (course_code) REFERENCES courses (course_code),
    CHECK (total_marks <= max_marks)
);

CREATE TABLE IF NOT EXISTS rule_registry (
    rule_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    parameter TEXT NOT NULL,
    operator TEXT NOT NULL CHECK (operator IN ('>=', '<=', '>', '<', '=', '!=')),
    value TEXT NOT NULL CHECK (length(value) > 0),
    scope_programmes TEXT NOT NULL,
    scope_batches TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    source_doc_id TEXT NOT NULL,
    source_section TEXT NOT NULL
);
