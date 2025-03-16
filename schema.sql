CREATE TABLE users
(
    id                 SERIAL PRIMARY KEY,
    github_id          VARCHAR(255) UNIQUE NOT NULL,
    github_api_token   TEXT,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE github_commits
(
    id             SERIAL PRIMARY KEY,
    github_id      VARCHAR(255) NOT NULL,
    commit_id      VARCHAR(255) NOT NULL UNIQUE,
    repository     VARCHAR(255) NOT NULL,
    message        TEXT NOT NULL,
    commit_url     TEXT NOT NULL,
    commit_date    TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE attendance (
    id SERIAL PRIMARY KEY,
    github_id      VARCHAR(255) NOT NULL,
    attendance_date DATE NOT NULL,
    is_attended BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (github_id, attendance_date)
);