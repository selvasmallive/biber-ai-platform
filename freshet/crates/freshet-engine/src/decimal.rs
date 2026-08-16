//! Decimal helpers.
//!
//! Every monetary value in the engine is a `rust_decimal::Decimal`. Binary
//! floating point is never used: a return that is off by a cent fails CRA
//! certification, and `f64` cannot represent `0.145` exactly.

use rust_decimal::prelude::*;
use rust_decimal::{Decimal, RoundingStrategy};
use serde::{Deserialize, Deserializer};

/// CRA rounds monetary amounts to the nearest cent, with halves away from zero.
///
/// The result is rescaled to exactly two places. `round_dp` alone only ever
/// *reduces* scale, so a whole-dollar input would stay scale 0 and serialize as
/// `85000` while its neighbours serialized as `4034.10`. Amounts that reach a
/// CRA payload must not vary in shape with how the taxpayer happened to type
/// them.
pub fn round_cents(v: Decimal) -> Decimal {
    let mut v = v.round_dp_with_strategy(2, RoundingStrategy::MidpointAwayFromZero);
    v.rescale(2);
    v
}

/// Many return lines are reported in whole dollars.
pub fn round_dollars(v: Decimal) -> Decimal {
    let mut v = v.round_dp_with_strategy(0, RoundingStrategy::MidpointAwayFromZero);
    v.rescale(0);
    v
}

/// Tax forms say "if negative, enter 0" on nearly every subtotal.
pub fn floor_zero(v: Decimal) -> Decimal {
    if v.is_sign_negative() {
        Decimal::ZERO
    } else {
        v
    }
}

/// Parse an amount the way a person actually types it: `$85,000.00`, `85 000`,
/// `85000`. Returns `None` for anything with no digits at all, which is how a
/// blank field stays blank rather than becoming zero.
pub fn parse_entered(raw: &str) -> Option<Decimal> {
    let cleaned: String = raw
        .chars()
        .filter(|c| c.is_ascii_digit() || *c == '.' || *c == '-')
        .collect();

    if cleaned.is_empty() || cleaned == "-" || cleaned == "." {
        return None;
    }
    Decimal::from_str_exact(&cleaned).ok()
}

/// Accept a decimal written in JSON as either a string (`"16129.00"`) or a bare
/// number. Parameter packs are authored as strings so the source document can be
/// transcribed character-for-character with no parsing ambiguity.
pub fn de_decimal<'de, D>(d: D) -> Result<Decimal, D::Error>
where
    D: Deserializer<'de>,
{
    struct V;

    impl<'de> serde::de::Visitor<'de> for V {
        type Value = Decimal;

        fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
            f.write_str("a decimal, as a JSON string or number")
        }

        fn visit_str<E: serde::de::Error>(self, v: &str) -> Result<Decimal, E> {
            Decimal::from_str_exact(v.trim()).map_err(E::custom)
        }

        fn visit_u64<E: serde::de::Error>(self, v: u64) -> Result<Decimal, E> {
            Ok(Decimal::from(v))
        }

        fn visit_i64<E: serde::de::Error>(self, v: i64) -> Result<Decimal, E> {
            Ok(Decimal::from(v))
        }

        fn visit_f64<E: serde::de::Error>(self, v: f64) -> Result<Decimal, E> {
            Decimal::from_f64(v).ok_or_else(|| E::custom("f64 not representable as Decimal"))
        }
    }

    d.deserialize_any(V)
}

/// `Option<Decimal>` variant of [`de_decimal`], for open-ended bracket bands.
pub fn de_decimal_opt<'de, D>(d: D) -> Result<Option<Decimal>, D::Error>
where
    D: Deserializer<'de>,
{
    #[derive(Deserialize)]
    struct Wrap(#[serde(deserialize_with = "de_decimal")] Decimal);

    Ok(Option::<Wrap>::deserialize(d)?.map(|w| w.0))
}
