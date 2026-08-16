-- Licence records.
--
-- Note what is absent: no name, no address, no card details, no telemetry.
-- Those live with the payment processor, which is already obliged to hold them.
-- Everything kept here is subject to PIPEDA, so the schema is the first place
-- to say no.

CREATE TABLE IF NOT EXISTS licences (
    key          TEXT PRIMARY KEY,
    email        TEXT NOT NULL,
    token        TEXT NOT NULL,
    product      TEXT NOT NULL,
    issued_unix  BIGINT NOT NULL,
    expires_unix BIGINT,
    revoked_unix BIGINT,
    order_ref    TEXT
);

CREATE INDEX IF NOT EXISTS licences_email_idx ON licences (email);

-- One row per device that has ever activated a licence. The composite primary
-- key is what makes a reinstall idempotent instead of a second device.
CREATE TABLE IF NOT EXISTS activations (
    key     TEXT NOT NULL REFERENCES licences (key) ON DELETE CASCADE,
    device  TEXT NOT NULL,
    at_unix BIGINT NOT NULL,
    PRIMARY KEY (key, device)
);

-- Payment events already handled. The primary key is the idempotency
-- mechanism: a retried webhook cannot issue a second licence, because the
-- insert that claims it will fail.
CREATE TABLE IF NOT EXISTS handled_events (
    event_id TEXT PRIMARY KEY,
    at_unix  BIGINT NOT NULL
);

-- Rate limiting for "send me my licence again", kept in the database rather
-- than in process memory because many instances run at once and a per-instance
-- counter is not a limit.
CREATE TABLE IF NOT EXISTS recovery_attempts (
    id      BIGSERIAL PRIMARY KEY,
    email   TEXT NOT NULL,
    at_unix BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS recovery_attempts_email_idx
    ON recovery_attempts (email, at_unix);

-- Support staff can see customer email addresses, so the looking is itself
-- worth a record.
CREATE TABLE IF NOT EXISTS admin_audit (
    id      BIGSERIAL PRIMARY KEY,
    who     TEXT NOT NULL,
    action  TEXT NOT NULL,
    subject TEXT NOT NULL,
    at_unix BIGINT NOT NULL
);
