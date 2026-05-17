use core::fmt;

pub const BASE_UNITS_PER_XRIQ: u128 = 1_000_000_000;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Default)]
pub struct XriqAmount(u128);

impl XriqAmount {
    pub const ZERO: Self = Self(0);

    pub const fn from_base_units(base_units: u128) -> Self {
        Self(base_units)
    }

    pub const fn base_units(self) -> u128 {
        self.0
    }

    pub const fn is_zero(self) -> bool {
        self.0 == 0
    }

    pub fn checked_add(self, other: Self) -> Option<Self> {
        self.0.checked_add(other.0).map(Self)
    }

    pub fn checked_sub(self, other: Self) -> Option<Self> {
        self.0.checked_sub(other.0).map(Self)
    }

    pub fn checked_mul_u64(self, multiplier: u64) -> Option<Self> {
        self.0.checked_mul(u128::from(multiplier)).map(Self)
    }
}

impl fmt::Display for XriqAmount {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{}", self.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn uses_integer_base_units() {
        let one = XriqAmount::from_base_units(BASE_UNITS_PER_XRIQ);
        assert_eq!(one.base_units(), 1_000_000_000);
    }

    #[test]
    fn checked_arithmetic_detects_overflow_and_underflow() {
        let max = XriqAmount::from_base_units(u128::MAX);
        assert!(max.checked_add(XriqAmount::from_base_units(1)).is_none());

        let zero = XriqAmount::ZERO;
        assert!(zero.checked_sub(XriqAmount::from_base_units(1)).is_none());
    }

    #[test]
    fn checked_mul_detects_overflow() {
        let amount = XriqAmount::from_base_units(u128::MAX);
        assert!(amount.checked_mul_u64(2).is_none());
    }
}
