//! Local chain storage for the XRIQ private devnet.

use std::{
    collections::BTreeMap,
    fs::{self, OpenOptions},
    io::{Cursor, Read, Write},
    path::{Path, PathBuf},
};

use xriq_core::{Address, Block, BlockHeader, Hash32, SignatureBytes, Transaction, XriqAmount};
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
    let mut transactions = Vec::with_capacity(transaction_count as usize);
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
    let mut blocks = Vec::with_capacity(count as usize);
    for _ in 0..count {
        let header = read_header(&mut cursor)?;
        let transaction_count = read_u32(&mut cursor)?;
        let mut transactions = Vec::with_capacity(transaction_count as usize);
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
    Ok(())
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

fn read_vec(cursor: &mut Cursor<&[u8]>) -> Result<Vec<u8>, StorageError> {
    let len = read_u32(cursor)? as usize;
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
}
