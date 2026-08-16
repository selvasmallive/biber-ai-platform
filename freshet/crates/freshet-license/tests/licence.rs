//! Tests for licensing.
//!
//! The forgery cases matter most. A licence system that accepts an edited
//! licence is worse than none, because it looks like protection while being
//! none.

use freshet_license::key::LicenceKey;
use freshet_license::{
    dev, sign, verify, verify_with, Activation, Allowance, Coverage, Entitlement, Filing, Licence,
    LicenceError, LicenceKind, WebActivation,
};

const NOW: i64 = 1_770_000_000;

/// The development licence's allowance, read from the licence rather than
/// restated, so it cannot drift from what `dev.rs` actually builds.
fn max_dev_returns() -> u32 {
    match dev_licence().1.allowance {
        Allowance::Returns(n) => n,
        Allowance::Unlimited => panic!("the development licence became unlimited"),
    }
}

fn dev_key() -> LicenceKey {
    LicenceKey::from_payload("DEV0000000000001").unwrap()
}

fn dev_licence() -> (String, Licence) {
    let built = dev::find(&dev_key()).expect("the development licence is built in");
    (built.token, built.licence)
}

// -- the key format -------------------------------------------------------

#[test]
fn a_key_round_trips_through_the_form_people_see() {
    let key = LicenceKey::from_payload("DEV0000000000001").unwrap();

    assert!(key.formatted().starts_with("FRSH-"));
    assert_eq!(LicenceKey::parse(&key.formatted()).unwrap(), key);
    assert_eq!(LicenceKey::parse(&key.compact()).unwrap(), key);
}

#[test]
fn keys_are_read_the_way_people_actually_type_them() {
    let key = LicenceKey::from_payload("DEV0000000000001").unwrap();
    let canonical = key.formatted();

    for typed in [
        canonical.to_lowercase(),
        canonical.replace('-', ""),
        canonical.replace('-', " "),
        format!("  {canonical}  "),
    ] {
        assert_eq!(LicenceKey::parse(&typed).unwrap(), key, "rejected {typed:?}");
    }
}

#[test]
fn characters_that_look_alike_are_folded_rather_than_rejected() {
    // The alphabet has no O, I, L or U precisely so these can be mapped to what
    // the person meant instead of becoming a support ticket.
    let key = LicenceKey::from_payload("DEV0000000000001").unwrap();
    let with_letter_o = key.formatted().replace('0', "O");

    assert_eq!(LicenceKey::parse(&with_letter_o).unwrap(), key);
}

#[test]
fn a_mistyped_key_is_caught_offline_before_anything_is_contacted() {
    let key = LicenceKey::from_payload("DEV0000000000001").unwrap();
    let mut chars: Vec<char> = key.compact().chars().collect();
    chars[6] = if chars[6] == '7' { '8' } else { '7' };
    let typo: String = chars.into_iter().collect();

    match LicenceKey::parse(&typo) {
        Err(LicenceError::MalformedKey(msg)) => assert!(msg.contains("typo"), "{msg}"),
        other => panic!("a typo was accepted: {other:?}"),
    }
}

#[test]
fn a_key_of_the_wrong_length_says_so() {
    assert!(matches!(
        LicenceKey::parse("FRSH-ABC"),
        Err(LicenceError::MalformedKey(_))
    ));
}

// -- signatures -----------------------------------------------------------

#[test]
fn a_built_in_development_licence_verifies() {
    let (token, expected) = dev_licence();
    let got = verify(&token).expect("the development licence verifies in a dev build");

    assert_eq!(got, expected);
    assert_eq!(got.kind, LicenceKind::Development);
}

/// The whole point. A licence edited to grant more must stop verifying.
#[test]
fn an_edited_licence_is_rejected() {
    let (token, licence) = dev_licence();

    let mut greedy = licence.clone();
    greedy.allowance = Allowance::Returns(100_000);
    greedy.kind = LicenceKind::Retail;

    // Re-encode the tampered body against the original signature.
    let sig = token.split_once('.').unwrap().1;
    let body = base64_url(&serde_json::to_vec(&greedy).unwrap());
    let forged = format!("{body}.{sig}");

    assert_eq!(verify(&forged), Err(LicenceError::BadSignature));
}

#[test]
fn a_licence_signed_by_the_wrong_key_is_rejected() {
    let (_, licence) = dev_licence();
    let attacker = ed25519_dalek::SigningKey::from_bytes(&[9u8; 32]);
    let token = sign(&licence, &attacker).unwrap();

    assert_eq!(verify(&token), Err(LicenceError::BadSignature));
}

/// A release build trusts only the production key, so a development licence
/// must be worthless against it — this is the second of the two locks that
/// stop the built-in licences becoming a shipped backdoor.
#[test]
fn the_production_key_does_not_accept_development_licences() {
    let (token, _) = dev_licence();

    assert_eq!(
        verify_with(&token, &freshet_license::sign::PRODUCTION_PUBLIC_KEY),
        Err(LicenceError::BadSignature)
    );
}

/// The placeholder was all zeroes and refused everything by design. A real key
/// is now set; this pins that it stays set, because silently reverting would
/// reject every licence ever sold.
#[test]
fn a_real_production_key_is_configured() {
    assert_ne!(
        freshet_license::sign::PRODUCTION_PUBLIC_KEY,
        [0u8; 32],
        "the production key is back to the placeholder — no licence can verify"
    );
}

#[test]
fn a_licence_that_is_not_a_licence_is_rejected_cleanly() {
    for junk in ["", "not-a-licence", "a.b", "onlyonepart"] {
        assert!(verify(junk).is_err(), "accepted {junk:?}");
    }
}

// -- entitlements ---------------------------------------------------------

#[test]
fn a_development_licence_covers_the_supported_years() {
    let (_, licence) = dev_licence();

    assert_eq!(licence.check("freshet-t1", &Filing::TaxYear(2026), 0, NOW), Entitlement::Granted);
    assert_eq!(licence.check("freshet-t1", &Filing::TaxYear(2025), 0, NOW), Entitlement::Granted);
}

#[test]
fn a_year_outside_the_licence_is_refused_with_the_years_it_does_cover() {
    let (_, licence) = dev_licence();

    match licence.check("freshet-t1", &Filing::TaxYear(2031), 0, NOW) {
        Entitlement::NotCovered { covered } => {
            assert_eq!(covered, Coverage::TaxYears(vec![2025, 2026]))
        }
        other => panic!("expected a year refusal, got {other:?}"),
    }
}

/// A T1 licence must not silently unlock a future T2 product.
#[test]
fn a_licence_for_one_product_does_not_unlock_another() {
    let (_, licence) = dev_licence();

    match licence.check("freshet-t2", &Filing::TaxYear(2026), 0, NOW) {
        Entitlement::WrongProduct { licensed_for } => assert_eq!(licensed_for, "freshet-t1"),
        other => panic!("a T1 licence unlocked T2: {other:?}"),
    }
}

#[test]
fn the_return_limit_is_enforced_and_explained() {
    let (_, licence) = dev_licence();
    let at_limit = licence.check("freshet-t1", &Filing::TaxYear(2026), max_dev_returns(), NOW);

    assert!(matches!(at_limit, Entitlement::ReturnLimitReached { .. }));
    assert!(at_limit.explain().contains("all been filed"));
    // One below the limit is still fine.
    assert!(licence
        .check("freshet-t1", &Filing::TaxYear(2026), max_dev_returns() - 1, NOW)
        .granted());
}

/// Filing does not stop dead on the expiry date.
///
/// A licence that lapsed yesterday must not be what stands between someone and
/// their filing deadline, so a grace period runs on past the end date. The
/// anti-sharing property is unaffected — the licence still dies, a month later.
#[test]
fn a_licence_that_has_just_lapsed_can_still_file() {
    let (_, mut licence) = dev_licence();
    licence.expires_unix = Some(NOW);

    assert!(licence.check("freshet-t1", &Filing::TaxYear(2026), 0, NOW - 1).granted());
    assert!(licence.check("freshet-t1", &Filing::TaxYear(2026), 0, NOW).granted());
    assert!(licence
        .check("freshet-t1", &Filing::TaxYear(2026), 0, NOW + freshet_license::standing::GRACE_SECS - 1)
        .granted());
}

#[test]
fn a_licence_stops_working_once_the_grace_period_is_spent() {
    let (_, mut licence) = dev_licence();
    licence.expires_unix = Some(NOW);

    let after = NOW + freshet_license::standing::GRACE_SECS;

    assert!(matches!(
        licence.check("freshet-t1", &Filing::TaxYear(2026), 0, after),
        Entitlement::Expired { .. }
    ));
}

/// The refusal has to say what still works before it says anything else.
/// Someone whose licence lapsed still owns their return.
#[test]
fn an_ended_licence_does_not_imply_the_return_is_lost() {
    let (_, mut licence) = dev_licence();
    licence.expires_unix = Some(NOW);

    let said = licence
        .check("freshet-t1", &Filing::TaxYear(2026), 0, NOW + freshet_license::standing::GRACE_SECS)
        .explain();

    assert!(said.contains("print and export"), "{said}");
}

#[test]
fn every_refusal_explains_itself_in_words_a_person_can_act_on() {
    let (_, licence) = dev_licence();

    for outcome in [
        licence.check("freshet-t2", &Filing::TaxYear(2026), 0, NOW),
        licence.check("freshet-t1", &Filing::TaxYear(2031), 0, NOW),
        licence.check("freshet-t1", &Filing::TaxYear(2026), 9_999_999, NOW),
    ] {
        let said = outcome.explain();
        assert!(!outcome.granted());
        assert!(said.len() > 20, "unhelpfully terse: {said}");
    }
}

// -- the certification licence -------------------------------------------

/// CRA certification means transmitting test returns for three months. Making
/// that wait on a purchase flow would be absurd, so it has its own licence.
#[test]
fn a_certification_licence_exists_and_is_marked_as_such() {
    let built = dev::licences()
        .into_iter()
        .find(|b| b.licence.kind == LicenceKind::Certification)
        .expect("a certification licence is built in");

    assert!(verify(&built.token).is_ok());
    assert!(built.licence.check("freshet-t1", &Filing::TaxYear(2026), 0, NOW).granted());

    // Distinguishable afterwards, which is the point of the separate kind.
    assert!(!built.licence.kind.is_production());
    assert!(dev::licences().iter().all(|b| !b.licence.kind.is_production()));
}

// -- the activation boundary ---------------------------------------------

#[test]
fn web_activation_reports_that_it_does_not_exist_yet() {
    let err = WebActivation {
        base_url: "https://freshettax.ca".into(),
    }
    .activate(&LicenceKey::from_payload("DEV0000000000001").unwrap())
    .unwrap_err();

    assert_eq!(err, LicenceError::ActivationUnavailable);
    assert!(err.to_string().contains("development licence"));
}

#[test]
fn a_pasted_licence_needs_no_server_at_all() {
    let (token, _) = dev_licence();
    let source = freshet_license::activation::PastedLicence {
        token: token.clone(),
    };

    let got = source
        .activate(&LicenceKey::from_payload("DEV0000000000001").unwrap())
        .unwrap();
    assert_eq!(got, token);
    assert!(verify(&got).is_ok());
}

fn base64_url(bytes: &[u8]) -> String {
    use base64::engine::general_purpose::URL_SAFE_NO_PAD;
    use base64::Engine as _;
    URL_SAFE_NO_PAD.encode(bytes)
}

// -- payload versioning ---------------------------------------------------

/// A licence from a newer Freshet is a *this app is old* problem, not a
/// *your licence is fake* problem, and the difference decides whether the
/// customer clicks update or emails support.
#[test]
fn a_licence_from_a_newer_build_says_to_update_rather_than_calling_it_invalid() {
    let (_, mut licence) = dev_licence();
    licence.version = freshet_license::PAYLOAD_VERSION + 1;

    let outcome = licence.check("freshet-t1", &Filing::TaxYear(2026), 0, NOW);

    assert!(matches!(outcome, Entitlement::NewerThanThisBuild { .. }));

    let said = outcome.explain();
    assert!(said.contains("Update Freshet"), "{said}");
    assert!(
        said.contains("nothing wrong with the licence"),
        "the customer must not be told their paid licence is bad: {said}"
    );
}

#[test]
fn todays_licences_carry_todays_version() {
    let (_, licence) = dev_licence();
    assert_eq!(licence.version, freshet_license::PAYLOAD_VERSION);
}

// -- the T2 shape ---------------------------------------------------------

/// The case a calendar year cannot express: a corporation with a June
/// year-end, which is the reason `Coverage` exists at all.
#[test]
fn a_corporate_licence_covers_a_fiscal_period_a_tax_year_could_not_name() {
    let (_, mut licence) = dev_licence();
    licence.product = "freshet-t2".into();
    licence.coverage = Coverage::PeriodsEnding {
        from_unix: 1_767_225_600, // 2026-01-01
        to_unix: 1_798_761_600,   // 2027-01-01
    };
    licence.allowance = Allowance::Returns(1);

    let june_year_end = Filing::PeriodEnding(1_782_000_000);
    assert!(licence.check("freshet-t2", &june_year_end, 0, NOW).granted());

    // A single-return licence is spent after one.
    assert!(!licence.check("freshet-t2", &june_year_end, 1, NOW).granted());

    // And a period outside the range is refused with the range named.
    let outside = Filing::PeriodEnding(1_900_000_000);
    let said = licence.check("freshet-t2", &outside, 0, NOW).explain();
    assert!(said.contains("fiscal periods ending between"), "{said}");
}

#[test]
fn a_professional_licence_never_runs_out() {
    let (_, mut licence) = dev_licence();
    licence.allowance = Allowance::Unlimited;

    assert!(licence
        .check("freshet-t1", &Filing::TaxYear(2026), 10_000, NOW)
        .granted());
    assert!(!licence.needs_authoritative_count());
}

/// The rule that decides whether transmission has to confirm the count.
#[test]
fn only_a_counted_licence_needs_the_server_to_agree() {
    let (_, mut licence) = dev_licence();

    licence.allowance = Allowance::Returns(5);
    assert!(licence.needs_authoritative_count());

    licence.allowance = Allowance::Unlimited;
    assert!(!licence.needs_authoritative_count());
}
