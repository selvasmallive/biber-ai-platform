use core::fmt;

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Default)]
pub struct Hash32([u8; 32]);

impl Hash32 {
    pub const ZERO: Self = Self([0; 32]);

    pub const fn from_bytes(bytes: [u8; 32]) -> Self {
        Self(bytes)
    }

    pub const fn as_bytes(&self) -> &[u8; 32] {
        &self.0
    }
}

impl fmt::Debug for Hash32 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("Hash32(")?;
        for byte in self.0 {
            write!(formatter, "{byte:02x}")?;
        }
        formatter.write_str(")")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stores_exactly_32_bytes() {
        let hash = Hash32::from_bytes([7; 32]);
        assert_eq!(hash.as_bytes(), &[7; 32]);
    }

    #[test]
    fn debug_uses_hex_shape() {
        let rendered = format!("{:?}", Hash32::ZERO);
        assert!(rendered.starts_with("Hash32(0000"));
        assert!(rendered.ends_with(')'));
    }
}
