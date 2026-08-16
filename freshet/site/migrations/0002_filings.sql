-- Filings counted against a licence.
--
-- This is the authoritative count for a counted (non-unlimited) licence. The
-- desktop app keeps its own tally, but that lives on the customer's machine and
-- a reinstall resets it — so the number that binds is this one, claimed at
-- transmission, where the network is already required to reach CRA.
--
-- The composite primary key makes a retry idempotent. Someone whose connection
-- dropped mid-transmission must not lose a return off their allowance for it.
CREATE TABLE IF NOT EXISTS filings (
    key        TEXT NOT NULL REFERENCES licences (key) ON DELETE CASCADE,
    filing_ref TEXT NOT NULL,
    at_unix    BIGINT NOT NULL,
    PRIMARY KEY (key, filing_ref)
);
