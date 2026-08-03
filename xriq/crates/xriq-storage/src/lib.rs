//! Local chain storage for the XRIQ private devnet.

use std::{
    collections::BTreeMap,
    fs::{self, OpenOptions},
    io::{Cursor, Read, Write},
    path::{Path, PathBuf},
};

use xriq_core::{
    Address, Block, BlockHeader, Hash32, SignatureBytes, Transaction, TxAction, XriqAmount,
};
use xriq_crypto::block_hash as canonical_block_hash;

const BLOCK_RECORD_TAG: &[u8; 4] = b"BLK1";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StoredBlock {
    pub block_hash: Hash32,
    pub block: Block,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum StorageError {
    DuplicateBlockHash,
    DuplicateBlockHeight,
    Io,
    CorruptData,
    ValueTooLarge,
}

pub trait ChainStore {
    fn append_block(&mut self, block_hash: Hash32, block: Block) -> Result<(), StorageError>;

    fn append_block_with_canonical_hash(&mut self, block: Block) -> Result<Hash32, StorageError> {
        let block_hash = canonical_block_hash(&block);
        self.append_block(block_hash, block)?;
        Ok(block_hash)
    }

    fn block_by_hash(&self, block_hash: &Hash32) -> Option<&StoredBlock>;
    fn block_by_height(&self, height: u64) -> Option<&StoredBlock>;
    fn latest_block(&self) -> Option<&StoredBlock>;
    fn blocks_by_height_desc(&self, limit: usize) -> Vec<&StoredBlock>;
    fn len(&self) -> usize;

    fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct InMemoryChainStore {
    blocks_by_hash: BTreeMap<Hash32, StoredBlock>,
    hashes_by_height: BTreeMap<u64, Hash32>,
    latest_height: Option<u64>,
}

impl InMemoryChainStore {
    pub fn new() -> Self {
        Self::default()
    }

    fn validate_append(&self, block_hash: &Hash32, block: &Block) -> Result<(), StorageError> {
        if self.blocks_by_hash.contains_key(block_hash) {
            return Err(StorageError::DuplicateBlockHash);
        }
        if self.hashes_by_height.contains_key(&block.header.height) {
            return Err(StorageError::DuplicateBlockHeight);
        }
        Ok(())
    }
}

impl ChainStore for InMemoryChainStore {
    fn append_block(&mut self, block_hash: Hash32, block: Block) -> Result<(), StorageError> {
        self.validate_append(&block_hash, &block)?;

        let height = block.header.height;
        self.hashes_by_height.insert(height, block_hash);
        self.blocks_by_hash
            .insert(block_hash, StoredBlock { block_hash, block });
        self.latest_height = Some(
            self.latest_height
                .map_or(height, |latest| latest.max(height)),
        );
        Ok(())
    }

    fn block_by_hash(&self, block_hash: &Hash32) -> Option<&StoredBlock> {
        self.blocks_by_hash.get(block_hash)
    }

    fn block_by_height(&self, height: u64) -> Option<&StoredBlock> {
        self.hashes_by_height
            .get(&height)
            .and_then(|block_hash| self.blocks_by_hash.get(block_hash))
    }

    fn latest_block(&self) -> Option<&StoredBlock> {
        self.latest_height
            .and_then(|height| self.block_by_height(height))
    }

    fn blocks_by_height_desc(&self, limit: usize) -> Vec<&StoredBlock> {
        self.hashes_by_height
            .iter()
            .rev()
            .take(limit)
            .filter_map(|(_, block_hash)| self.blocks_by_hash.get(block_hash))
            .collect()
    }

    fn len(&self) -> usize {
        self.blocks_by_hash.len()
    }
}

#[derive(Debug)]
pub struct FileChainStore {
    path: PathBuf,
    inner: InMemoryChainStore,
}

impl FileChainStore {
    pub fn open(path: impl AsRef<Path>) -> Result<Self, StorageError> {
        let path = path.as_ref().to_path_buf();
        if let Some(parent) = path
            .parent()
            .filter(|parent| !parent.as_os_str().is_empty())
        {
            fs::create_dir_all(parent).map_err(|_| StorageError::Io)?;
        }

        let mut inner = InMemoryChainStore::new();
        if path.exists() {
            let bytes = fs::read(&path).map_err(|_| StorageError::Io)?;
            decode_store(&bytes, &mut inner)?;
        }

        OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)
            .map_err(|_| StorageError::Io)?;

        Ok(Self { path, inner })
    }

    pub fn path(&self) -> &Path {
        &self.path
    }
}

impl ChainStore for FileChainStore {
    fn append_block(&mut self, block_hash: Hash32, block: Block) -> Result<(), StorageError> {
        self.inner.validate_append(&block_hash, &block)?;

        let record = StoredBlock {
            block_hash,
            block: block.clone(),
        };
        let mut bytes = Vec::new();
        encode_block_record(&record, &mut bytes)?;
        let mut file = OpenOptions::new()
            .append(true)
            .open(&self.path)
            .map_err(|_| StorageError::Io)?;
        file.write_all(&bytes).map_err(|_| StorageError::Io)?;
        file.flush().map_err(|_| StorageError::Io)?;

        self.inner.append_block(block_hash, block)
    }

    fn block_by_hash(&self, block_hash: &Hash32) -> Option<&StoredBlock> {
        self.inner.block_by_hash(block_hash)
    }

    fn block_by_height(&self, height: u64) -> Option<&StoredBlock> {
        self.inner.block_by_height(height)
    }

    fn latest_block(&self) -> Option<&StoredBlock> {
        self.inner.latest_block()
    }

    fn blocks_by_height_desc(&self, limit: usize) -> Vec<&StoredBlock> {
        self.inner.blocks_by_height_desc(limit)
    }

    fn len(&self) -> usize {
        self.inner.len()
    }
}

fn encode_block_record(record: &StoredBlock, output: &mut Vec<u8>) -> Result<(), StorageError> {
    output.extend_from_slice(BLOCK_RECORD_TAG);
    write_hash(output, record.block_hash);
    write_header(output, &record.block.header)?;
    write_u32(output, checked_len(record.block.transactions.len())?);
    for transaction in &record.block.transactions {
        write_transaction(output, transaction)?;
    }
    Ok(())
}

fn decode_store(bytes: &[u8], store: &mut InMemoryChainStore) -> Result<(), StorageError> {
    let mut cursor = Cursor::new(bytes);
    while usize::try_from(cursor.position()).map_err(|_| StorageError::CorruptData)? < bytes.len() {
        let record = read_block_record(&mut cursor)?;
        store.append_block(record.block_hash, record.block)?;
    }
    Ok(())
}

fn read_block_record(cursor: &mut Cursor<&[u8]>) -> Result<StoredBlock, StorageError> {
    let mut tag = [0; 4];
    read_exact(cursor, &mut tag)?;
    if &tag != BLOCK_RECORD_TAG {
        return Err(StorageError::CorruptData);
    }
    let block_hash = read_hash(cursor)?;
    let header = read_header(cursor)?;
    let transaction_count = read_u32(cursor)?;
    // Clamp the pre-allocation to the remaining input (each transaction is >= 1 byte),
    // so a forged count can't allocate gigabytes; a lie is caught by the reads below.
    let mut transactions =
        Vec::with_capacity((transaction_count as usize).min(cursor_remaining(cursor)));
    for _ in 0..transaction_count {
        transactions.push(read_transaction(cursor)?);
    }
    Ok(StoredBlock {
        block_hash,
        block: Block {
            header,
            transactions,
        },
    })
}

const PEER_BLOCKS_TAG: &[u8; 4] = b"XPB1";

/// Encode a sequence of blocks for peer transfer (headers + bodies). The block
/// hash is not sent; a receiving node recomputes and fully validates each block
/// on import, so a peer cannot inject a block with a forged hash. Uses the same
/// canonical field encoding as the on-disk chain store.
pub fn encode_peer_blocks(blocks: &[Block]) -> Result<Vec<u8>, StorageError> {
    let mut output = Vec::new();
    output.extend_from_slice(PEER_BLOCKS_TAG);
    write_u32(&mut output, checked_len(blocks.len())?);
    for block in blocks {
        write_header(&mut output, &block.header)?;
        write_u32(&mut output, checked_len(block.transactions.len())?);
        for transaction in &block.transactions {
            write_transaction(&mut output, transaction)?;
        }
    }
    Ok(output)
}

/// Decode blocks produced by `encode_peer_blocks`. Rejects a wrong tag or any
/// trailing bytes as corrupt data.
pub fn decode_peer_blocks(bytes: &[u8]) -> Result<Vec<Block>, StorageError> {
    let mut cursor = Cursor::new(bytes);
    let mut tag = [0; 4];
    read_exact(&mut cursor, &mut tag)?;
    if &tag != PEER_BLOCKS_TAG {
        return Err(StorageError::CorruptData);
    }
    let count = read_u32(&mut cursor)?;
    let mut blocks = Vec::with_capacity((count as usize).min(cursor_remaining(&cursor)));
    for _ in 0..count {
        let header = read_header(&mut cursor)?;
        let transaction_count = read_u32(&mut cursor)?;
        let mut transactions =
            Vec::with_capacity((transaction_count as usize).min(cursor_remaining(&cursor)));
        for _ in 0..transaction_count {
            transactions.push(read_transaction(&mut cursor)?);
        }
        blocks.push(Block {
            header,
            transactions,
        });
    }
    if usize::try_from(cursor.position()).map_err(|_| StorageError::CorruptData)? != bytes.len() {
        return Err(StorageError::CorruptData);
    }
    Ok(blocks)
}

fn write_header(output: &mut Vec<u8>, header: &BlockHeader) -> Result<(), StorageError> {
    write_u16(output, header.version);
    write_string(output, &header.chain_id)?;
    write_u64(output, header.height);
    write_hash(output, header.previous_block_hash);
    write_hash(output, header.state_root);
    write_hash(output, header.transactions_root);
    write_u64(output, header.timestamp_ms);
    write_address(output, &header.producer)?;
    write_u64(output, header.consensus_round);
    write_signature(output, &header.signature)?;
    write_byte_vec(output, &header.public_key)?;
    Ok(())
}

fn read_header(cursor: &mut Cursor<&[u8]>) -> Result<BlockHeader, StorageError> {
    Ok(BlockHeader {
        version: read_u16(cursor)?,
        chain_id: read_string(cursor)?,
        height: read_u64(cursor)?,
        previous_block_hash: read_hash(cursor)?,
        state_root: read_hash(cursor)?,
        transactions_root: read_hash(cursor)?,
        timestamp_ms: read_u64(cursor)?,
        producer: read_address(cursor)?,
        consensus_round: read_u64(cursor)?,
        signature: read_signature(cursor)?,
        public_key: read_vec(cursor)?,
    })
}

fn write_transaction(output: &mut Vec<u8>, tx: &Transaction) -> Result<(), StorageError> {
    write_u16(output, tx.version);
    write_string(output, &tx.chain_id)?;
    write_address(output, &tx.from)?;
    write_address(output, &tx.to)?;
    write_amount(output, tx.amount);
    write_amount(output, tx.fee);
    write_u64(output, tx.nonce);
    write_option_hash(output, tx.memo_hash);
    write_option_u64(output, tx.expires_at_height);
    write_signature(output, &tx.signature)?;
    write_byte_vec(output, &tx.public_key)?;
    write_action(output, &tx.action)?;
    Ok(())
}

// The transaction action is a trailing tagged field: `0` for a plain transfer (the
// overwhelming common case), `1`/`2` for the governance variants followed by the
// target address. Unlike the consensus hash preimage — where `Transfer` contributes
// zero bytes so transfer hashes are unchanged — the on-disk codec is a parser and
// always writes the one-byte tag so decoding is unambiguous. Storage bytes are not a
// consensus golden; round-trip tests cover this.
const ACTION_TAG_TRANSFER: u8 = 0;
const ACTION_TAG_AUTHORIZE: u8 = 1;
const ACTION_TAG_REVOKE: u8 = 2;
const ACTION_TAG_SWAP: u8 = 3;

fn write_action(output: &mut Vec<u8>, action: &TxAction) -> Result<(), StorageError> {
    match action {
        TxAction::Transfer => write_u8(output, ACTION_TAG_TRANSFER),
        TxAction::AuthorizeWallet { target } => {
            write_u8(output, ACTION_TAG_AUTHORIZE);
            write_address(output, target)?;
        }
        TxAction::RevokeWallet { target } => {
            write_u8(output, ACTION_TAG_REVOKE);
            write_address(output, target)?;
        }
        TxAction::Swap {
            counter_amount,
            counterparty_public_key,
            counterparty_signature,
        } => {
            write_u8(output, ACTION_TAG_SWAP);
            write_u128(output, *counter_amount);
            write_byte_vec(output, counterparty_public_key)?;
            write_signature(output, counterparty_signature)?;
        }
    }
    Ok(())
}

fn read_action(cursor: &mut Cursor<&[u8]>) -> Result<TxAction, StorageError> {
    match read_u8(cursor)? {
        ACTION_TAG_TRANSFER => Ok(TxAction::Transfer),
        ACTION_TAG_AUTHORIZE => Ok(TxAction::AuthorizeWallet {
            target: read_address(cursor)?,
        }),
        ACTION_TAG_REVOKE => Ok(TxAction::RevokeWallet {
            target: read_address(cursor)?,
        }),
        ACTION_TAG_SWAP => Ok(TxAction::Swap {
            counter_amount: read_u128(cursor)?,
            counterparty_public_key: read_vec(cursor)?,
            counterparty_signature: read_signature(cursor)?,
        }),
        _ => Err(StorageError::CorruptData),
    }
}

fn read_transaction(cursor: &mut Cursor<&[u8]>) -> Result<Transaction, StorageError> {
    Ok(Transaction {
        version: read_u16(cursor)?,
        chain_id: read_string(cursor)?,
        from: read_address(cursor)?,
        to: read_address(cursor)?,
        amount: read_amount(cursor)?,
        fee: read_amount(cursor)?,
        nonce: read_u64(cursor)?,
        memo_hash: read_option_hash(cursor)?,
        expires_at_height: read_option_u64(cursor)?,
        signature: read_signature(cursor)?,
        public_key: read_vec(cursor)?,
        action: read_action(cursor)?,
    })
}

fn checked_len(len: usize) -> Result<u32, StorageError> {
    u32::try_from(len).map_err(|_| StorageError::ValueTooLarge)
}

fn write_u8(output: &mut Vec<u8>, value: u8) {
    output.push(value);
}

fn read_u8(cursor: &mut Cursor<&[u8]>) -> Result<u8, StorageError> {
    let mut bytes = [0; 1];
    read_exact(cursor, &mut bytes)?;
    Ok(bytes[0])
}

fn write_u16(output: &mut Vec<u8>, value: u16) {
    output.extend_from_slice(&value.to_le_bytes());
}

fn read_u16(cursor: &mut Cursor<&[u8]>) -> Result<u16, StorageError> {
    let mut bytes = [0; 2];
    read_exact(cursor, &mut bytes)?;
    Ok(u16::from_le_bytes(bytes))
}

fn write_u32(output: &mut Vec<u8>, value: u32) {
    output.extend_from_slice(&value.to_le_bytes());
}

fn read_u32(cursor: &mut Cursor<&[u8]>) -> Result<u32, StorageError> {
    let mut bytes = [0; 4];
    read_exact(cursor, &mut bytes)?;
    Ok(u32::from_le_bytes(bytes))
}

fn write_u64(output: &mut Vec<u8>, value: u64) {
    output.extend_from_slice(&value.to_le_bytes());
}

fn read_u64(cursor: &mut Cursor<&[u8]>) -> Result<u64, StorageError> {
    let mut bytes = [0; 8];
    read_exact(cursor, &mut bytes)?;
    Ok(u64::from_le_bytes(bytes))
}

fn write_u128(output: &mut Vec<u8>, value: u128) {
    output.extend_from_slice(&value.to_le_bytes());
}

fn read_u128(cursor: &mut Cursor<&[u8]>) -> Result<u128, StorageError> {
    let mut bytes = [0; 16];
    read_exact(cursor, &mut bytes)?;
    Ok(u128::from_le_bytes(bytes))
}

fn write_hash(output: &mut Vec<u8>, hash: Hash32) {
    output.extend_from_slice(hash.as_bytes());
}

fn read_hash(cursor: &mut Cursor<&[u8]>) -> Result<Hash32, StorageError> {
    let mut bytes = [0; 32];
    read_exact(cursor, &mut bytes)?;
    Ok(Hash32::from_bytes(bytes))
}

fn write_amount(output: &mut Vec<u8>, amount: XriqAmount) {
    write_u128(output, amount.base_units());
}

fn read_amount(cursor: &mut Cursor<&[u8]>) -> Result<XriqAmount, StorageError> {
    Ok(XriqAmount::from_base_units(read_u128(cursor)?))
}

fn write_string(output: &mut Vec<u8>, value: &str) -> Result<(), StorageError> {
    let bytes = value.as_bytes();
    write_u32(output, checked_len(bytes.len())?);
    output.extend_from_slice(bytes);
    Ok(())
}

fn read_string(cursor: &mut Cursor<&[u8]>) -> Result<String, StorageError> {
    let bytes = read_vec(cursor)?;
    String::from_utf8(bytes).map_err(|_| StorageError::CorruptData)
}

fn write_address(output: &mut Vec<u8>, address: &Address) -> Result<(), StorageError> {
    write_string(output, address.as_str())
}

fn read_address(cursor: &mut Cursor<&[u8]>) -> Result<Address, StorageError> {
    Address::parse(&read_string(cursor)?).map_err(|_| StorageError::CorruptData)
}

fn write_signature(output: &mut Vec<u8>, signature: &SignatureBytes) -> Result<(), StorageError> {
    write_u32(output, checked_len(signature.as_slice().len())?);
    output.extend_from_slice(signature.as_slice());
    Ok(())
}

fn write_byte_vec(output: &mut Vec<u8>, value: &[u8]) -> Result<(), StorageError> {
    write_u32(output, checked_len(value.len())?);
    output.extend_from_slice(value);
    Ok(())
}

fn read_signature(cursor: &mut Cursor<&[u8]>) -> Result<SignatureBytes, StorageError> {
    Ok(SignatureBytes::new(read_vec(cursor)?))
}

fn write_option_hash(output: &mut Vec<u8>, value: Option<Hash32>) {
    match value {
        Some(hash) => {
            write_u8(output, 1);
            write_hash(output, hash);
        }
        None => write_u8(output, 0),
    }
}

fn read_option_hash(cursor: &mut Cursor<&[u8]>) -> Result<Option<Hash32>, StorageError> {
    match read_u8(cursor)? {
        0 => Ok(None),
        1 => Ok(Some(read_hash(cursor)?)),
        _ => Err(StorageError::CorruptData),
    }
}

fn write_option_u64(output: &mut Vec<u8>, value: Option<u64>) {
    match value {
        Some(number) => {
            write_u8(output, 1);
            write_u64(output, number);
        }
        None => write_u8(output, 0),
    }
}

fn read_option_u64(cursor: &mut Cursor<&[u8]>) -> Result<Option<u64>, StorageError> {
    match read_u8(cursor)? {
        0 => Ok(None),
        1 => Ok(Some(read_u64(cursor)?)),
        _ => Err(StorageError::CorruptData),
    }
}

// Bytes left in the cursor. Used to bound length/count prefixes before allocating,
// so a hostile message with a huge prefix cannot trigger a multi-GB allocation or a
// capacity-overflow abort before the (short) actual data is read.
fn cursor_remaining(cursor: &Cursor<&[u8]>) -> usize {
    (cursor.get_ref().len() as u64).saturating_sub(cursor.position()) as usize
}

fn read_vec(cursor: &mut Cursor<&[u8]>) -> Result<Vec<u8>, StorageError> {
    let len = read_u32(cursor)? as usize;
    // A length longer than the remaining input is corrupt; reject before allocating.
    if len > cursor_remaining(cursor) {
        return Err(StorageError::CorruptData);
    }
    let mut bytes = vec![0; len];
    read_exact(cursor, &mut bytes)?;
    Ok(bytes)
}

fn read_exact(cursor: &mut Cursor<&[u8]>, buffer: &mut [u8]) -> Result<(), StorageError> {
    cursor
        .read_exact(buffer)
        .map_err(|_| StorageError::CorruptData)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn address(label: &str) -> Address {
        Address::parse(&format!("xriqdev1{label}00000000000")).unwrap()
    }

    fn hash(byte: u8) -> Hash32 {
        Hash32::from_bytes([byte; 32])
    }

    fn transaction() -> Transaction {
        Transaction {
            version: Transaction::SUPPORTED_VERSION,
            chain_id: "xriq-devnet".to_string(),
            from: address("alice"),
            to: address("bobbb"),
            amount: XriqAmount::from_base_units(10),
            fee: XriqAmount::from_base_units(2),
            nonce: 0,
            memo_hash: Some(hash(3)),
            expires_at_height: Some(100),
            signature: SignatureBytes::new(vec![1, 2, 3]),
            public_key: Vec::new(),
            action: Default::default(),
        }
    }

    fn block(height: u64, previous_block_hash: Hash32) -> Block {
        Block {
            header: BlockHeader {
                version: BlockHeader::SUPPORTED_VERSION,
                chain_id: "xriq-devnet".to_string(),
                height,
                previous_block_hash,
                state_root: hash(4),
                transactions_root: hash(5),
                timestamp_ms: 1_000 + height,
                producer: address("author"),
                consensus_round: 0,
                signature: SignatureBytes::new(vec![9]),
                public_key: Vec::new(),
            },
            transactions: vec![transaction()],
        }
    }

    fn temp_store_path() -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("xriq-store-{nanos}.bin"))
    }

    #[test]
    fn peer_blocks_encode_decode_roundtrip() {
        let blocks = vec![block(1, hash(0)), block(2, hash(1))];
        let encoded = encode_peer_blocks(&blocks).unwrap();
        assert_eq!(decode_peer_blocks(&encoded).unwrap(), blocks);

        // Empty range roundtrips.
        assert_eq!(
            decode_peer_blocks(&encode_peer_blocks(&[]).unwrap()).unwrap(),
            vec![]
        );

        // A wrong tag or trailing garbage is rejected.
        assert_eq!(
            decode_peer_blocks(b"NOPE").err(),
            Some(StorageError::CorruptData)
        );
        let mut trailing = encode_peer_blocks(&blocks).unwrap();
        trailing.push(0xff);
        assert_eq!(
            decode_peer_blocks(&trailing).err(),
            Some(StorageError::CorruptData)
        );
    }

    #[test]
    fn governance_actions_survive_encode_decode_roundtrip() {
        // The action is a trailing tagged codec field; every variant must round-trip so
        // a stored block carrying a registry mutation replays identically. A plain
        // transfer (the default) is covered by the roundtrip above; here we exercise
        // both governance tags and their target address.
        let mut authorize = transaction();
        authorize.action = TxAction::AuthorizeWallet {
            target: address("carol"),
        };
        let mut revoke = transaction();
        revoke.action = TxAction::RevokeWallet {
            target: address("davey"),
        };
        let mut swap = transaction();
        swap.action = TxAction::Swap {
            counter_amount: 123_456_789,
            counterparty_public_key: vec![7, 8, 9, 10],
            counterparty_signature: SignatureBytes::new(vec![11, 12, 13]),
        };

        let mut header = block(1, hash(0)).header;
        header.height = 7;
        let governance_block = Block {
            header,
            transactions: vec![transaction(), authorize, revoke, swap],
        };
        let blocks = vec![governance_block];

        let encoded = encode_peer_blocks(&blocks).unwrap();
        assert_eq!(decode_peer_blocks(&encoded).unwrap(), blocks);
    }

    #[test]
    fn memory_store_indexes_blocks_by_hash_height_and_latest() {
        let mut store = InMemoryChainStore::new();
        let block_hash = hash(8);
        let block = block(1, hash(0));

        assert_eq!(store.append_block(block_hash, block.clone()), Ok(()));

        assert_eq!(store.len(), 1);
        assert_eq!(
            store.block_by_hash(&block_hash).map(|record| &record.block),
            Some(&block)
        );
        assert_eq!(
            store.block_by_height(1).map(|record| record.block_hash),
            Some(block_hash)
        );
        assert_eq!(
            store.latest_block().map(|record| record.block_hash),
            Some(block_hash)
        );
    }

    #[test]
    fn memory_store_appends_block_with_canonical_hash() {
        let mut store = InMemoryChainStore::new();
        let block = block(1, hash(0));
        let block_hash = canonical_block_hash(&block);

        assert_eq!(
            store.append_block_with_canonical_hash(block.clone()),
            Ok(block_hash)
        );
        assert_eq!(
            store.block_by_hash(&block_hash).map(|record| &record.block),
            Some(&block)
        );
    }

    #[test]
    fn memory_store_lists_recent_blocks_by_descending_height() {
        let mut store = InMemoryChainStore::new();
        store.append_block(hash(1), block(1, hash(0))).unwrap();
        store.append_block(hash(2), block(2, hash(1))).unwrap();
        store.append_block(hash(3), block(3, hash(2))).unwrap();

        let heights: Vec<u64> = store
            .blocks_by_height_desc(2)
            .into_iter()
            .map(|record| record.block.header.height)
            .collect();

        assert_eq!(heights, vec![3, 2]);
        assert!(store.blocks_by_height_desc(0).is_empty());
    }

    #[test]
    fn memory_store_rejects_duplicates() {
        let mut store = InMemoryChainStore::new();
        let first_block = block(1, hash(0));
        store.append_block(hash(8), first_block.clone()).unwrap();

        assert_eq!(
            store.append_block(hash(8), block(2, hash(8))),
            Err(StorageError::DuplicateBlockHash)
        );
        assert_eq!(
            store.append_block(hash(9), first_block),
            Err(StorageError::DuplicateBlockHeight)
        );
    }

    #[test]
    fn file_store_reloads_persisted_blocks() {
        let path = temp_store_path();
        let block_hash = hash(8);
        let block = block(1, hash(0));

        {
            let mut store = FileChainStore::open(&path).unwrap();
            store.append_block(block_hash, block.clone()).unwrap();
        }

        let reloaded = FileChainStore::open(&path).unwrap();
        assert_eq!(
            reloaded
                .block_by_hash(&block_hash)
                .map(|record| &record.block),
            Some(&block)
        );
        assert_eq!(
            reloaded.latest_block().map(|record| record.block_hash),
            Some(block_hash)
        );

        let _ = fs::remove_file(path);
    }

    #[test]
    fn decode_peer_blocks_rejects_oversized_prefixes_without_allocating() {
        // A hostile ~10-byte message with count = u32::MAX must be rejected as
        // corrupt, NOT trigger a multi-GB / capacity-overflow allocation abort.
        let mut oversized_count = b"XPB1".to_vec();
        oversized_count.extend_from_slice(&u32::MAX.to_le_bytes());
        assert_eq!(
            decode_peer_blocks(&oversized_count),
            Err(StorageError::CorruptData)
        );

        // Same for a per-block transaction_count: a real header followed by a giant
        // transaction_count and no transactions.
        let block = block(1, hash(0));
        let mut oversized_txs = b"XPB1".to_vec();
        oversized_txs.extend_from_slice(&1u32.to_le_bytes());
        write_header(&mut oversized_txs, &block.header).unwrap();
        oversized_txs.extend_from_slice(&u32::MAX.to_le_bytes());
        assert_eq!(
            decode_peer_blocks(&oversized_txs),
            Err(StorageError::CorruptData)
        );
    }

    // ---- Deterministic fuzzing of the peer-block wire decoder ----
    //
    // `decode_peer_blocks` parses attacker-controlled bytes (a peer's HTTP response).
    // These tests hammer it with pseudo-random and mutated input to prove three
    // invariants an adversarial peer must never be able to break:
    //   1. it never panics / aborts (no unwrap, index-OOB, overflow, or OOM), always
    //      returning Ok/Err on ANY input;
    //   2. every structurally valid block round-trips (encode → decode → equal);
    //   3. the accepted encoding is CANONICAL — if a byte string decodes, re-encoding
    //      the result reproduces those exact bytes (no ambiguous/slack acceptance).
    // The RNG is seeded per iteration so any failure is deterministically reproducible.

    // xorshift64* — a tiny, dependency-free deterministic PRNG for fuzzing.
    struct FuzzRng(u64);

    impl FuzzRng {
        fn new(seed: u64) -> Self {
            // Any non-zero state; xorshift is degenerate at zero.
            FuzzRng(seed | 1)
        }

        fn next_u64(&mut self) -> u64 {
            let mut x = self.0;
            x ^= x >> 12;
            x ^= x << 25;
            x ^= x >> 27;
            self.0 = x;
            x.wrapping_mul(0x2545_F491_4F6C_DD1D)
        }

        fn below(&mut self, n: usize) -> usize {
            if n == 0 {
                0
            } else {
                (self.next_u64() % n as u64) as usize
            }
        }

        fn byte(&mut self) -> u8 {
            self.next_u64() as u8
        }

        fn bool(&mut self) -> bool {
            self.next_u64() & 1 == 1
        }

        fn bytes(&mut self, max_len: usize) -> Vec<u8> {
            let len = self.below(max_len + 1);
            (0..len).map(|_| self.byte()).collect()
        }
    }

    // A structurally valid address: the `xriqdev1` prefix + 16..=40 lowercase
    // alphanumeric payload chars, so `Address::parse` always succeeds.
    fn fuzz_address(rng: &mut FuzzRng) -> Address {
        const CHARS: &[u8] = b"abcdefghijklmnopqrstuvwxyz0123456789";
        let len = 16 + rng.below(25);
        let mut label = String::from("xriqdev1");
        for _ in 0..len {
            label.push(CHARS[rng.below(CHARS.len())] as char);
        }
        Address::parse(&label).expect("fuzz address is well-formed")
    }

    // A short valid-UTF-8 (ASCII) string; the decoder accepts any UTF-8, and ASCII
    // is a valid subset that round-trips exactly.
    fn fuzz_string(rng: &mut FuzzRng) -> String {
        let len = rng.below(20);
        (0..len)
            .map(|_| (0x20 + rng.below(0x5f) as u8) as char)
            .collect()
    }

    fn fuzz_bytes_vec(rng: &mut FuzzRng) -> Vec<u8> {
        rng.bytes(24)
    }

    fn fuzz_transaction(rng: &mut FuzzRng) -> Transaction {
        Transaction {
            version: rng.next_u64() as u16,
            chain_id: fuzz_string(rng),
            from: fuzz_address(rng),
            to: fuzz_address(rng),
            amount: XriqAmount::from_base_units(rng.next_u64() as u128),
            fee: XriqAmount::from_base_units(rng.next_u64() as u128),
            nonce: rng.next_u64(),
            memo_hash: rng.bool().then(|| hash(rng.byte())),
            expires_at_height: rng.bool().then(|| rng.next_u64()),
            signature: SignatureBytes::new(fuzz_bytes_vec(rng)),
            public_key: fuzz_bytes_vec(rng),
            action: Default::default(),
        }
    }

    fn fuzz_block(rng: &mut FuzzRng) -> Block {
        let header = BlockHeader {
            version: rng.next_u64() as u16,
            chain_id: fuzz_string(rng),
            height: rng.next_u64(),
            previous_block_hash: hash(rng.byte()),
            state_root: hash(rng.byte()),
            transactions_root: hash(rng.byte()),
            timestamp_ms: rng.next_u64(),
            producer: fuzz_address(rng),
            consensus_round: rng.next_u64(),
            signature: SignatureBytes::new(fuzz_bytes_vec(rng)),
            public_key: fuzz_bytes_vec(rng),
        };
        let tx_count = rng.below(4);
        let transactions = (0..tx_count).map(|_| fuzz_transaction(rng)).collect();
        Block {
            header,
            transactions,
        }
    }

    fn fuzz_blocks(rng: &mut FuzzRng) -> Vec<Block> {
        let count = rng.below(4);
        (0..count).map(|_| fuzz_block(rng)).collect()
    }

    #[test]
    fn fuzz_decode_never_panics_on_arbitrary_bytes() {
        for i in 0..50_000u64 {
            let mut rng = FuzzRng::new(0x9E37_79B9_7F4A_7C15 ^ i);
            // Half raw random bytes, half prefixed with the real tag so the header/
            // transaction readers are exercised deeply past the tag gate.
            let mut input = rng.bytes(256);
            if rng.bool() {
                let mut tagged = PEER_BLOCKS_TAG.to_vec();
                tagged.append(&mut input);
                input = tagged;
            }
            // Must return without panicking; either outcome is acceptable.
            if let Ok(blocks) = decode_peer_blocks(&input) {
                // Any accepted byte string is canonical: re-encoding reproduces it.
                assert_eq!(
                    encode_peer_blocks(&blocks).unwrap(),
                    input,
                    "non-canonical acceptance at seed {i}"
                );
            }
        }
    }

    #[test]
    fn fuzz_encode_decode_roundtrips_random_blocks() {
        for i in 0..5_000u64 {
            let mut rng = FuzzRng::new(0x1234_5678_9ABC_DEF0 ^ i.wrapping_mul(0x9E37_79B9));
            let blocks = fuzz_blocks(&mut rng);
            let encoded = encode_peer_blocks(&blocks).expect("valid blocks encode");
            let decoded = decode_peer_blocks(&encoded).expect("own encoding decodes");
            assert_eq!(decoded, blocks, "roundtrip mismatch at seed {i}");
        }
    }

    #[test]
    fn fuzz_mutating_a_valid_encoding_never_panics() {
        for i in 0..20_000u64 {
            let mut rng = FuzzRng::new(0xDEAD_BEEF_CAFE_F00D ^ i);
            let blocks = fuzz_blocks(&mut rng);
            let mut bytes = encode_peer_blocks(&blocks).expect("valid blocks encode");
            if bytes.is_empty() {
                continue;
            }
            // Apply one random mutation class to the valid encoding.
            match rng.below(5) {
                // Flip 1..=4 random bytes.
                0 => {
                    for _ in 0..=rng.below(4) {
                        let idx = rng.below(bytes.len());
                        bytes[idx] ^= rng.byte();
                    }
                }
                // Truncate to a random shorter length.
                1 => {
                    let keep = rng.below(bytes.len());
                    bytes.truncate(keep);
                }
                // Append random trailing bytes (must be rejected, never panic).
                2 => {
                    let mut extra = rng.bytes(16);
                    bytes.append(&mut extra);
                }
                // Tamper the top-level block-count prefix (bytes 4..8).
                3 => {
                    if bytes.len() >= 8 {
                        let patch = rng.next_u64() as u32;
                        bytes[4..8].copy_from_slice(&patch.to_le_bytes());
                    }
                }
                // Splice in a random byte at a random position.
                _ => {
                    let idx = rng.below(bytes.len() + 1);
                    bytes.insert(idx, rng.byte());
                }
            }

            // Must not panic; if it still decodes, the encoding stays canonical.
            if let Ok(decoded) = decode_peer_blocks(&bytes) {
                assert_eq!(
                    encode_peer_blocks(&decoded).unwrap(),
                    bytes,
                    "mutated input accepted non-canonically at seed {i}"
                );
            }
        }
    }

    // ---- Deterministic fuzzing of the on-disk chain-store reload path ----
    //
    // `FileChainStore::open` reads the append-only log file and feeds its raw bytes to
    // `decode_store`, which loops `read_block_record` (BLK1 tag + hash + header + txs)
    // and re-appends each record (rejecting duplicate hash/height). That decode runs on
    // whatever bytes are on disk — a truncated write, a corrupted file, or hostile
    // content. These tests reuse the module's `FuzzRng` / `fuzz_block` to prove:
    //   1. it never panics / OOMs on arbitrary bytes,
    //   2. a buffer of validly encoded records round-trips (same blocks, same count),
    //   3. mutating a valid buffer never panics,
    //   4. the real file-backed `open` reload round-trips persisted blocks.

    // Build `count` records with DISTINCT heights and hashes (the store rejects
    // duplicate height/hash), each carrying a randomly generated block body.
    fn fuzz_store_records(rng: &mut FuzzRng, count: usize) -> Vec<(Hash32, Block)> {
        (0..count)
            .map(|k| {
                let mut block = fuzz_block(rng);
                block.header.height = k as u64;
                (hash((k as u8) ^ 0xC3), block)
            })
            .collect()
    }

    fn encode_store_records(records: &[(Hash32, Block)]) -> Vec<u8> {
        let mut buffer = Vec::new();
        for (block_hash, block) in records {
            encode_block_record(
                &StoredBlock {
                    block_hash: *block_hash,
                    block: block.clone(),
                },
                &mut buffer,
            )
            .expect("valid record encodes");
        }
        buffer
    }

    #[test]
    fn fuzz_decode_store_never_panics_on_arbitrary_bytes() {
        for i in 0..50_000u64 {
            let mut rng = FuzzRng::new(0x5709_ABCD_1234_5678 ^ i);
            // Half raw random bytes, half prefixed with the real record tag so the
            // header/transaction readers are exercised past the tag gate.
            let mut input = rng.bytes(256);
            if rng.bool() {
                let mut tagged = BLOCK_RECORD_TAG.to_vec();
                tagged.append(&mut input);
                input = tagged;
            }
            // Must return without panicking; either outcome is acceptable.
            let mut store = InMemoryChainStore::new();
            let _ = decode_store(&input, &mut store);
        }
    }

    #[test]
    fn fuzz_decode_store_roundtrips_encoded_records() {
        for i in 0..5_000u64 {
            let mut rng = FuzzRng::new(0x0DD5_7075_2345_6789 ^ i);
            let count = rng.below(6);
            let records = fuzz_store_records(&mut rng, count);
            let buffer = encode_store_records(&records);

            let mut store = InMemoryChainStore::new();
            decode_store(&buffer, &mut store).expect("encoded records decode");
            assert_eq!(
                store.len(),
                records.len(),
                "record count mismatch at seed {i}"
            );
            for (block_hash, block) in &records {
                assert_eq!(
                    store.block_by_hash(block_hash).map(|stored| &stored.block),
                    Some(block),
                    "record body mismatch at seed {i}"
                );
            }
        }
    }

    #[test]
    fn fuzz_mutating_a_valid_store_buffer_never_panics() {
        for i in 0..20_000u64 {
            let mut rng = FuzzRng::new(0xF11E_57DA_3456_789A ^ i);
            let count = 1 + rng.below(5);
            let records = fuzz_store_records(&mut rng, count);
            let mut bytes = encode_store_records(&records);
            if bytes.is_empty() {
                continue;
            }
            match rng.below(5) {
                0 => {
                    for _ in 0..=rng.below(4) {
                        let idx = rng.below(bytes.len());
                        bytes[idx] ^= rng.byte();
                    }
                }
                1 => {
                    let keep = rng.below(bytes.len());
                    bytes.truncate(keep);
                }
                2 => {
                    let mut extra = rng.bytes(16);
                    bytes.append(&mut extra);
                }
                3 => {
                    // Tamper the first record's transaction-count prefix, which sits
                    // right after the tag (4) + hash (32) + header.
                    let idx = rng.below(bytes.len());
                    let patch = rng.next_u64() as u32;
                    let end = (idx + 4).min(bytes.len());
                    bytes[idx..end].copy_from_slice(&patch.to_le_bytes()[..end - idx]);
                }
                _ => {
                    let idx = rng.below(bytes.len() + 1);
                    bytes.insert(idx, rng.byte());
                }
            }

            // Must not panic; Ok or Err are both acceptable outcomes.
            let mut store = InMemoryChainStore::new();
            let _ = decode_store(&bytes, &mut store);
        }
    }

    #[test]
    fn file_chain_store_reload_roundtrips_random_blocks() {
        // Exercise the real file-backed reload (fs::read + decode_store) end to end.
        for i in 0..200u64 {
            let mut rng = FuzzRng::new(0xF11E_C0DE_4567_89AB ^ i);
            let path = temp_store_path();
            let count = 1 + rng.below(5);
            let records = fuzz_store_records(&mut rng, count);
            {
                let mut store = FileChainStore::open(&path).expect("open new store");
                for (block_hash, block) in &records {
                    store
                        .append_block(*block_hash, block.clone())
                        .expect("append persists");
                }
            }
            let reloaded = FileChainStore::open(&path).expect("reopen store");
            assert_eq!(
                reloaded.len(),
                records.len(),
                "reload count mismatch at seed {i}"
            );
            for (block_hash, block) in &records {
                assert_eq!(
                    reloaded
                        .block_by_hash(block_hash)
                        .map(|stored| &stored.block),
                    Some(block),
                    "reloaded body mismatch at seed {i}"
                );
            }
            let _ = fs::remove_file(&path);
        }
    }
}
