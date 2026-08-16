//! Telling apart the two things a customer can hold.
//!
//! A **licence** is a signed payload. It carries its own proof, so this machine
//! can check it alone, forever, with no network. A **key** is a short string
//! that identifies a purchase and proves nothing — the only way to turn one into
//! a licence is to ask the party holding the signing key.
//!
//! Keeping these distinct in the type system is what makes "never contact the
//! server unless asked" enforceable rather than aspirational: the offline path
//! has no branch that *could* reach the network, because a [`Credential::Licence`]
//! is already everything the app needs.

use crate::{LicenceError, LicenceKey};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Credential {
    /// A signed licence. Verifiable here, on its own.
    Licence(String),

    /// A purchase key. Needs exchanging before it means anything.
    Key(LicenceKey),
}

impl Credential {
    /// Work out what the user pasted.
    ///
    /// The two forms cannot be confused: a licence is base64url with a `.`
    /// separating payload from signature, and `.` is not in the key alphabet.
    pub fn classify(raw: &str) -> Result<Self, LicenceError> {
        // Licences are long enough that mail clients wrap them, and people
        // select the trailing newline. Neither should be the user's problem.
        let squeezed: String = raw.chars().filter(|c| !c.is_whitespace()).collect();

        if squeezed.is_empty() {
            return Err(LicenceError::MalformedKey(
                "nothing was entered".to_string(),
            ));
        }

        if squeezed.contains('.') {
            return Ok(Credential::Licence(squeezed));
        }

        LicenceKey::parse(&squeezed).map(Credential::Key)
    }

    /// Whether reading this can be finished without asking anyone anything.
    pub fn is_self_contained(&self) -> bool {
        matches!(self, Credential::Licence(_))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_signed_licence_is_recognised_as_self_contained() {
        let c = Credential::classify("cGF5bG9hZA.c2ln").unwrap();
        assert_eq!(c, Credential::Licence("cGF5bG9hZA.c2ln".into()));
        assert!(c.is_self_contained());
    }

    #[test]
    fn a_licence_wrapped_by_an_email_client_still_reads() {
        let wrapped = "cGF5bG9h\r\n  ZA.c2\n ln\n";
        assert_eq!(
            Credential::classify(wrapped).unwrap(),
            Credential::Licence("cGF5bG9hZA.c2ln".into())
        );
    }

    #[test]
    fn a_key_is_recognised_and_is_not_self_contained() {
        // Built the way the issuer builds one, so the checksum is right.
        let key = LicenceKey::from_payload("DEV0000000000000").unwrap();

        let c = Credential::classify(&key.formatted()).unwrap();
        assert_eq!(c, Credential::Key(key));
        assert!(
            !c.is_self_contained(),
            "a key proves nothing on its own and must not be treated as a licence"
        );
    }

    #[test]
    fn nothing_entered_says_so_rather_than_failing_obscurely() {
        let e = Credential::classify("   \n ").unwrap_err();
        assert!(e.to_string().contains("nothing was entered"), "{e}");
    }

    #[test]
    fn a_mistyped_key_is_caught_here_with_no_network() {
        let good = LicenceKey::from_payload("DEV0000000000000").unwrap();
        let mangled = good.formatted().replace('D', "F");

        let e = Credential::classify(&mangled).unwrap_err();
        assert!(e.to_string().contains("typo"), "{e}");
    }
}
