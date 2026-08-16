//! The Postgres store.
//!
//! Queries are runtime-checked rather than `query!`-macro checked, so the
//! service builds in CI and in a container without a live database to introspect.
//! The schema lives in `migrations/` and is applied at boot.

use async_trait::async_trait;
use sqlx::postgres::{PgPool, PgPoolOptions};
use sqlx::Row;

use super::{normalise_email, IssuedLicence, Result, Store, StoreError};

impl From<sqlx::Error> for StoreError {
    fn from(e: sqlx::Error) -> Self {
        // A unique violation on the key is a collision, not an outage, and the
        // caller's correct response is to generate another key and retry.
        if let sqlx::Error::Database(ref db) = e {
            if db.code().as_deref() == Some("23505") {
                return StoreError::DuplicateKey;
            }
        }
        StoreError::Backend(e.to_string())
    }
}

pub struct PostgresStore {
    pool: PgPool,
}

impl PostgresStore {
    pub async fn connect(url: &str) -> Result<Self> {
        let pool = PgPoolOptions::new()
            // Cloud Run scales to many instances and Cloud SQL has a hard
            // connection ceiling. A small per-instance pool is what keeps a
            // traffic spike from exhausting it.
            .max_connections(5)
            .connect(url)
            .await?;

        sqlx::migrate!("./migrations")
            .run(&pool)
            .await
            .map_err(|e| StoreError::Backend(e.to_string()))?;

        Ok(Self { pool })
    }
}

fn row_to_licence(row: &sqlx::postgres::PgRow) -> IssuedLicence {
    IssuedLicence {
        key: row.get("key"),
        email: row.get("email"),
        token: row.get("token"),
        product: row.get("product"),
        issued_unix: row.get("issued_unix"),
        expires_unix: row.get("expires_unix"),
        revoked_unix: row.get("revoked_unix"),
        order_ref: row.get("order_ref"),
    }
}

#[async_trait]
impl Store for PostgresStore {
    async fn insert(&self, licence: &IssuedLicence) -> Result<()> {
        sqlx::query(
            "INSERT INTO licences
               (key, email, token, product, issued_unix, expires_unix, revoked_unix, order_ref)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
        )
        .bind(&licence.key)
        .bind(normalise_email(&licence.email))
        .bind(&licence.token)
        .bind(&licence.product)
        .bind(licence.issued_unix)
        .bind(licence.expires_unix)
        .bind(licence.revoked_unix)
        .bind(&licence.order_ref)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    async fn by_key(&self, key: &str) -> Result<Option<IssuedLicence>> {
        let row = sqlx::query("SELECT * FROM licences WHERE key = $1")
            .bind(key)
            .fetch_optional(&self.pool)
            .await?;

        Ok(row.as_ref().map(row_to_licence))
    }

    async fn for_email(&self, email: &str) -> Result<Vec<IssuedLicence>> {
        let rows = sqlx::query("SELECT * FROM licences WHERE email = $1 ORDER BY issued_unix DESC")
            .bind(normalise_email(email))
            .fetch_all(&self.pool)
            .await?;

        Ok(rows.iter().map(row_to_licence).collect())
    }

    async fn revoke(&self, key: &str, at_unix: i64) -> Result<bool> {
        let done = sqlx::query(
            "UPDATE licences SET revoked_unix = $2 WHERE key = $1 AND revoked_unix IS NULL",
        )
        .bind(key)
        .bind(at_unix)
        .execute(&self.pool)
        .await?;

        Ok(done.rows_affected() > 0)
    }

    async fn record_activation(&self, key: &str, device: &str, at_unix: i64) -> Result<u32> {
        // ON CONFLICT DO NOTHING makes a reinstall idempotent rather than a
        // second device, without a read-then-write race between instances.
        sqlx::query(
            "INSERT INTO activations (key, device, at_unix) VALUES ($1, $2, $3)
             ON CONFLICT (key, device) DO NOTHING",
        )
        .bind(key)
        .bind(device)
        .bind(at_unix)
        .execute(&self.pool)
        .await?;

        let row = sqlx::query("SELECT COUNT(*) AS n FROM activations WHERE key = $1")
            .bind(key)
            .fetch_one(&self.pool)
            .await?;

        let n: i64 = row.get("n");
        Ok(n as u32)
    }

    async fn claim_event(&self, event_id: &str, at_unix: i64) -> Result<bool> {
        // The insert *is* the claim. Two concurrent deliveries of the same
        // webhook cannot both win, because the primary key will not allow it.
        let done = sqlx::query(
            "INSERT INTO handled_events (event_id, at_unix) VALUES ($1, $2)
             ON CONFLICT (event_id) DO NOTHING",
        )
        .bind(event_id)
        .bind(at_unix)
        .execute(&self.pool)
        .await?;

        Ok(done.rows_affected() > 0)
    }

    async fn recovery_permitted(
        &self,
        email: &str,
        now_unix: i64,
        window_secs: i64,
        max_in_window: i64,
    ) -> Result<bool> {
        let email = normalise_email(email);

        let row = sqlx::query(
            "SELECT COUNT(*) AS n FROM recovery_attempts WHERE email = $1 AND at_unix > $2",
        )
        .bind(&email)
        .bind(now_unix - window_secs)
        .fetch_one(&self.pool)
        .await?;

        let recent: i64 = row.get("n");
        if recent >= max_in_window {
            return Ok(false);
        }

        sqlx::query("INSERT INTO recovery_attempts (email, at_unix) VALUES ($1, $2)")
            .bind(&email)
            .bind(now_unix)
            .execute(&self.pool)
            .await?;

        Ok(true)
    }

    async fn claim_filing(
        &self,
        key: &str,
        filing_ref: &str,
        at_unix: i64,
    ) -> Result<Option<u32>> {
        // The insert is the claim, so two concurrent transmissions of the same
        // return cannot both consume a slot.
        let done = sqlx::query(
            "INSERT INTO filings (key, filing_ref, at_unix) VALUES ($1, $2, $3)
             ON CONFLICT (key, filing_ref) DO NOTHING",
        )
        .bind(key)
        .bind(filing_ref)
        .bind(at_unix)
        .execute(&self.pool)
        .await?;

        if done.rows_affected() == 0 {
            return Ok(None);
        }

        Ok(Some(self.filings_used(key).await?))
    }

    async fn filings_used(&self, key: &str) -> Result<u32> {
        let row = sqlx::query("SELECT COUNT(*) AS n FROM filings WHERE key = $1")
            .bind(key)
            .fetch_one(&self.pool)
            .await?;

        let n: i64 = row.get("n");
        Ok(n as u32)
    }

    async fn search(&self, needle: &str, limit: i64) -> Result<Vec<IssuedLicence>> {
        let pattern = format!("%{}%", needle.trim().to_ascii_lowercase());

        let rows = sqlx::query(
            "SELECT * FROM licences
             WHERE email LIKE $1 OR LOWER(key) LIKE $1 OR LOWER(order_ref) LIKE $1
             ORDER BY issued_unix DESC LIMIT $2",
        )
        .bind(&pattern)
        .bind(limit)
        .fetch_all(&self.pool)
        .await?;

        Ok(rows.iter().map(row_to_licence).collect())
    }

    async fn audit(&self, who: &str, action: &str, subject: &str, at_unix: i64) -> Result<()> {
        sqlx::query(
            "INSERT INTO admin_audit (who, action, subject, at_unix) VALUES ($1, $2, $3, $4)",
        )
        .bind(who)
        .bind(action)
        .bind(subject)
        .bind(at_unix)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    async fn forget_email(&self, email: &str) -> Result<u64> {
        let email = normalise_email(email);

        // Activations cascade from licences; recovery attempts are keyed by
        // address and have to go explicitly or a deletion request leaves a
        // record of when that person asked for help.
        let done = sqlx::query("DELETE FROM licences WHERE email = $1")
            .bind(&email)
            .execute(&self.pool)
            .await?;

        sqlx::query("DELETE FROM recovery_attempts WHERE email = $1")
            .bind(&email)
            .execute(&self.pool)
            .await?;

        Ok(done.rows_affected())
    }
}
