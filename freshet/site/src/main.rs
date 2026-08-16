use std::sync::Arc;

use freshet_site::config::Config;
use freshet_site::mail::{LoggingMailer, Mailer, SmtpMailer};
use freshet_site::store::postgres::PostgresStore;
use freshet_site::{router, AppState, SystemClock};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info,tower_http=info".into()),
        )
        .init();

    let config = Config::from_env()?;

    // Refuse to run against a placeholder. A service that issues licences no
    // shipped build can verify is worse than one that will not start: the
    // failure would surface as customers who paid and cannot file.
    if freshet_license::sign::PRODUCTION_PUBLIC_KEY == [0u8; 32] {
        return Err(
            "PRODUCTION_PUBLIC_KEY in freshet-license is still the placeholder. \
             Run `cargo run --bin keygen`, paste the public half into sign.rs, \
             and rebuild before issuing anything."
                .into(),
        );
    }

    // And refuse if the key we hold is not the key the app trusts. Getting
    // these out of step is the single most expensive mistake available here,
    // and it is one comparison to rule out.
    let ours = config.signing_key.verifying_key().to_bytes();
    if ours != freshet_license::sign::PRODUCTION_PUBLIC_KEY {
        return Err(format!(
            "FRESHET_SIGNING_KEY does not match PRODUCTION_PUBLIC_KEY. Licences \
             signed with it would be rejected by every installed copy of Freshet. \
             This build expects the key whose public half begins {:02x}{:02x}…",
            freshet_license::sign::PRODUCTION_PUBLIC_KEY[0],
            freshet_license::sign::PRODUCTION_PUBLIC_KEY[1],
        )
        .into());
    }

    let mailer: Arc<dyn Mailer> = match &config.smtp {
        Some(smtp) => Arc::new(SmtpMailer::new(smtp)?),
        None => {
            tracing::warn!("no SMTP configured — licences will be logged, not delivered");
            Arc::new(LoggingMailer)
        }
    };

    if config.admin_emails.is_empty() {
        tracing::warn!("ADMIN_EMAILS is unset — the admin pages are switched off");
    }

    let state = AppState {
        store: Arc::new(PostgresStore::connect(&config.database_url).await?),
        mailer,
        clock: Arc::new(SystemClock),
        signing_key: Arc::new(config.signing_key),
        stripe_secret: config.stripe_webhook_secret,
        admin_emails: config.admin_emails,
        sale_year: 2026,
    };

    let listener = tokio::net::TcpListener::bind(("0.0.0.0", config.port)).await?;
    tracing::info!("listening on {}", listener.local_addr()?);

    axum::serve(listener, router(state))
        .with_graceful_shutdown(shutdown())
        .await?;

    Ok(())
}

/// Cloud Run sends SIGTERM before it stops an instance. Draining rather than
/// dropping means an in-flight webhook finishes instead of being retried.
async fn shutdown() {
    let _ = tokio::signal::ctrl_c().await;
}
