CREATE DATABASE IF NOT EXISTS biber;
USE biber;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin_users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    force_password_change BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_keys (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    key_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    rate_limit_per_minute INT DEFAULT 60,
    expires_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS passcodes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    passcode_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    priority_level INT NOT NULL,
    gpu_allocation_percent INT NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    expires_at TIMESTAMP NULL,
    created_by BIGINT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS models (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL UNIQUE,
    model_type VARCHAR(50) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_versions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    model_id BIGINT NOT NULL,
    version VARCHAR(50) NOT NULL,
    model_path VARCHAR(500) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'staged',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES models(id)
);

CREATE TABLE IF NOT EXISTS jobs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    job_uuid VARCHAR(100) NOT NULL UNIQUE,
    user_id BIGINT NULL,
    model_name VARCHAR(100) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    priority_level INT NOT NULL DEFAULT 3,
    status VARCHAR(30) NOT NULL DEFAULT 'queued',
    input_type VARCHAR(50),
    gpu_required BOOLEAN NOT NULL DEFAULT TRUE,
    gpu_allocated_percent INT DEFAULT 0,
    payload_json JSON,
    result_json JSON,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gpu_nodes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    node_name VARCHAR(100) NOT NULL,
    gpu_name VARCHAR(255),
    total_memory_mb INT,
    status VARCHAR(30) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gpu_allocations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    job_id BIGINT NOT NULL,
    gpu_node_id BIGINT NULL,
    allocation_percent INT NOT NULL,
    status VARCHAR(30) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    released_at TIMESTAMP NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (gpu_node_id) REFERENCES gpu_nodes(id)
);

CREATE TABLE IF NOT EXISTS media_files (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    storage_path VARCHAR(500) NOT NULL,
    media_type VARCHAR(50) NOT NULL,
    checksum_sha256 VARCHAR(128),
    encrypted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proctor_sessions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    exam_id VARCHAR(100) NOT NULL,
    candidate_id VARCHAR(100) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'created',
    start_time TIMESTAMP NULL,
    end_time TIMESTAMP NULL,
    risk_score INT DEFAULT 0,
    risk_level VARCHAR(50) DEFAULT 'clear',
    review_status VARCHAR(50) DEFAULT 'not_reviewed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proctor_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id BIGINT NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    start_time VARCHAR(50),
    end_time VARCHAR(50),
    confidence DECIMAL(5,4),
    severity VARCHAR(30),
    evidence_clip_id BIGINT NULL,
    requires_human_review BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES proctor_sessions(id),
    FOREIGN KEY (evidence_clip_id) REFERENCES media_files(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    actor_type VARCHAR(50),
    actor_id VARCHAR(100),
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(100),
    target_id VARCHAR(100),
    result VARCHAR(50),
    ip_address VARCHAR(100),
    request_id VARCHAR(100),
    details_json JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usage_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NULL,
    api_key_id BIGINT NULL,
    passcode_id BIGINT NULL,
    model_name VARCHAR(100),
    job_uuid VARCHAR(100),
    tokens_input INT DEFAULT 0,
    tokens_output INT DEFAULT 0,
    gpu_seconds DECIMAL(12,3) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT IGNORE INTO users (username, email) VALUES ('demo_user', 'demo@example.com');

INSERT IGNORE INTO models (model_name, model_type) VALUES
('biber-dev-core', 'code'),
('biber-code-python', 'code'),
('biber-code-react', 'code'),
('biber-code-dotnet', 'code'),
('biber-code-java', 'code'),
('biber-code-rust', 'code'),
('biber-video-core', 'video'),
('biber-audio-core', 'audio'),
('biber-proctor-core', 'proctor');
