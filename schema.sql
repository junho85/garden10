CREATE TABLE github_commits
(
    id             SERIAL PRIMARY KEY,
    username       VARCHAR(255),
    commit_hash    VARCHAR(40),
    commit_message TEXT,
    commit_date    TIMESTAMP,
    repo_name      VARCHAR(255),
    commit_url     TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (commit_hash, repo_name) -- 동일한 commit_hash와 repo에서 중복 방지
);

CREATE TABLE users
(
    id                 SERIAL PRIMARY KEY,
    github_id          VARCHAR(255) UNIQUE NOT NULL,
    github_api_token   TEXT,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
