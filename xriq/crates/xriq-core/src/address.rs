use core::{fmt, str::FromStr};

pub const DEVNET_ADDRESS_PREFIX: &str = "xriqdev1";
const MIN_PAYLOAD_LEN: usize = 16;
const MAX_PAYLOAD_LEN: usize = 96;

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Address(String);

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AddressError {
    Empty,
    WrongPrefix,
    PayloadTooShort,
    PayloadTooLong,
    InvalidCharacter(char),
}

impl Address {
    pub fn parse(input: &str) -> Result<Self, AddressError> {
        let value = input.trim();
        if value.is_empty() {
            return Err(AddressError::Empty);
        }
        if !value.starts_with(DEVNET_ADDRESS_PREFIX) {
            return Err(AddressError::WrongPrefix);
        }

        let payload = &value[DEVNET_ADDRESS_PREFIX.len()..];
        if payload.len() < MIN_PAYLOAD_LEN {
            return Err(AddressError::PayloadTooShort);
        }
        if payload.len() > MAX_PAYLOAD_LEN {
            return Err(AddressError::PayloadTooLong);
        }
        if let Some(invalid) = payload
            .chars()
            .find(|character| !character.is_ascii_lowercase() && !character.is_ascii_digit())
        {
            return Err(AddressError::InvalidCharacter(invalid));
        }

        Ok(Self(value.to_string()))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl fmt::Display for Address {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(&self.0)
    }
}

impl FromStr for Address {
    type Err = AddressError;

    fn from_str(input: &str) -> Result<Self, Self::Err> {
        Self::parse(input)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_devnet_address() {
        let address = Address::parse("xriqdev1alice00000000000").unwrap();
        assert_eq!(address.as_str(), "xriqdev1alice00000000000");
    }

    #[test]
    fn rejects_wrong_network_prefix() {
        assert_eq!(
            Address::parse("xriqmain1alice00000000000"),
            Err(AddressError::WrongPrefix)
        );
    }

    #[test]
    fn rejects_invalid_payload_character() {
        assert_eq!(
            Address::parse("xriqdev1ALICE00000000000"),
            Err(AddressError::InvalidCharacter('A'))
        );
    }
}
