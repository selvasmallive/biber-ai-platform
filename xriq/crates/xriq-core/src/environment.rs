//! Deployment environment profiles for XRIQ.
//!
//! XRIQ only runs in non-production profiles today. Parsing is fail-closed:
//! `production`, `mainnet`, `public-testnet`, and any unknown value are
//! rejected, so a local/private build can never be configured to run as, or be
//! confused with, production. Accepted local mutation flags are only meaningful
//! within one of these non-production profiles.

use std::fmt;
use std::str::FromStr;

/// Canonical network identity for the current private-devnet line.
pub const CANONICAL_NETWORK: &str = "xriq-devnet";

/// Supported deployment environment profiles.
///
/// There is intentionally no `Production` or `Mainnet` variant: those are not
/// runnable from this build and parsing them fails closed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Environment {
    /// Developer machine. The default profile.
    Local,
    /// Hardened private/staging devnet: production-like topology, but no public
    /// network exposure and no public financial claims.
    StagingDevnet,
}

impl Environment {
    /// The default profile used when none is specified.
    pub const DEFAULT: Environment = Environment::Local;

    /// All supported profiles, in declaration order.
    pub const ALL: [Environment; 2] = [Environment::Local, Environment::StagingDevnet];

    /// Stable string identifier for the profile.
    pub fn as_str(self) -> &'static str {
        match self {
            Environment::Local => "local",
            Environment::StagingDevnet => "staging-devnet",
        }
    }

    /// True for every supported profile. All current profiles are
    /// non-production; this exists to make the invariant explicit at call sites
    /// that gate accepted local mutations.
    pub fn is_non_production(self) -> bool {
        matches!(self, Environment::Local | Environment::StagingDevnet)
    }
}

impl fmt::Display for Environment {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// Error returned when an environment string is not an allowed profile.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EnvironmentError {
    /// The rejected value (trimmed).
    pub value: String,
}

impl fmt::Display for EnvironmentError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "unsupported environment {:?}: only \"local\" and \"staging-devnet\" are allowed; \
             production, mainnet, and public-testnet are not runnable from this build",
            self.value
        )
    }
}

impl std::error::Error for EnvironmentError {}

impl FromStr for Environment {
    type Err = EnvironmentError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value.trim() {
            "local" => Ok(Environment::Local),
            "staging-devnet" => Ok(Environment::StagingDevnet),
            other => Err(EnvironmentError {
                value: other.to_string(),
            }),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_supported_profiles() {
        assert_eq!("local".parse::<Environment>().unwrap(), Environment::Local);
        assert_eq!(
            "staging-devnet".parse::<Environment>().unwrap(),
            Environment::StagingDevnet
        );
        // Surrounding whitespace is tolerated.
        assert_eq!(
            "  staging-devnet  ".parse::<Environment>().unwrap(),
            Environment::StagingDevnet
        );
    }

    #[test]
    fn rejects_production_and_unknown_profiles_fail_closed() {
        for value in [
            "production",
            "mainnet",
            "public-testnet",
            "production-candidate",
            "prod",
            "Local",
            "STAGING-DEVNET",
            "xriq-devnet",
            "",
        ] {
            let error = value.parse::<Environment>().unwrap_err();
            assert_eq!(error.value, value.trim());
        }
    }

    #[test]
    fn as_str_round_trips() {
        for environment in Environment::ALL {
            assert_eq!(
                environment.as_str().parse::<Environment>().unwrap(),
                environment
            );
            assert!(environment.is_non_production());
        }
    }

    #[test]
    fn default_is_local() {
        assert_eq!(Environment::DEFAULT, Environment::Local);
    }
}
