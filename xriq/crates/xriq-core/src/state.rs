use crate::{Address, XriqAmount};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AccountStateEntry {
    pub address: Address,
    pub balance: XriqAmount,
    pub nonce: u64,
}

impl AccountStateEntry {
    pub fn new(address: Address, balance: XriqAmount, nonce: u64) -> Self {
        Self {
            address,
            balance,
            nonce,
        }
    }
}
