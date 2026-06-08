use std::{
    collections::BTreeMap,
    env,
    fmt::Write as _,
    fs,
    io::{Read, Write},
    net::{TcpListener, TcpStream},
    path::Path,
    process::{self, Command, Stdio},
};

use xriq_api::{
    local_refusal_audit_events, pending_mempool_entries_from_tsv, product_api_http_response,
    verify_signed_submit_envelope_preview, ApiHttpResponse, LocalRefusalAuditEventResponse,
    SignedSubmitEnvelopeInput, SignedSubmitHashesInput, SignedSubmitSignatureEnvelopeInput,
    SignedSubmitStateContext, SignedSubmitTransactionInput, SignedSubmitVerificationOk,
    SignedSubmitVerificationRefusal, XriqApiService, LOCAL_REFUSAL_AUDIT_ACTOR,
    MEMPOOL_READONLY_WARNING, SIGNED_SUBMIT_ENDPOINT, SIGNED_SUBMIT_TEST_SIGNATURE_ALGORITHM,
    SIGNED_SUBMIT_TEST_VERIFIER, SNAPSHOT_READONLY_WARNING, WALLET_AUDIT_RESOURCE_TYPE,
    WALLET_PREVIEW_WARNING, WALLET_SEND_AUDIT_ACTION, WALLET_SEND_AUDIT_RESOURCE_ID,
    WALLET_SIGNED_SUBMIT_AUDIT_ACTION, WALLET_SUBMIT_AUDIT_ACTION, WALLET_SUBMIT_AUDIT_RESOURCE_ID,
};
use xriq_core::{
    Address, Hash32, XriqAmount, PRIVATE_DEVNET_MAX_TRANSACTIONS_PER_BLOCK,
    PRIVATE_DEVNET_MIN_FEE_BASE_UNITS,
};
use xriq_crypto::transaction_hash;
use xriq_indexer::index_private_devnet_store;
use xriq_iso20022::{
    account_statement_preview, payment_initiation_preview, payment_status_preview,
    XriqIsoAccountHistory, XriqIsoAccountTransaction, XriqIsoTransaction,
};
use xriq_node::{
    private_devnet_file_produce_pending_block, private_devnet_file_submit_pending_transfer_body,
    PrivateDevnetPendingTransactionDetail, ProducedPendingBlockStatus,
};
use xriq_storage::{ChainStore, FileChainStore};

const DEFAULT_BIND: &str = "127.0.0.1:8090";
const BLOCK_PRODUCTION_ROUTE: &str = "/api/v1/blocks/produce";
const WALLET_SUBMIT_ROUTE: &str = "/api/v1/wallet/transfers/submit";
const WALLET_SUBMIT_ENDPOINT: &str = "POST /api/v1/wallet/transfers/submit";
const WALLET_SEND_ROUTE: &str = "/api/v1/wallet/transfers/send";
const WALLET_SEND_ENDPOINT: &str = "POST /api/v1/wallet/transfers/send";
const WALLET_SIGNED_SUBMIT_ROUTE: &str = "/api/v1/wallet/transfers/submit-signed";
const ENABLE_LOCAL_BLOCK_PRODUCTION_FLAG: &str = "--enable-local-block-production";
const ENABLE_LOCAL_WALLET_SUBMIT_FLAG: &str = "--enable-local-wallet-submit";
const ENABLE_LOCAL_WALLET_SEND_FLAG: &str = "--enable-local-wallet-send";
const ENABLE_LOCAL_WALLET_SIGNED_SUBMIT_FLAG: &str = "--enable-local-wallet-submit-signed";
const LOCAL_BLOCK_PRODUCTION_ACCEPTED_CODE: &str = "block_production_accepted_local_only";
const LOCAL_WALLET_SUBMIT_ACCEPTED_CODE: &str = "wallet_submit_accepted_local_only";
const LOCAL_WALLET_SEND_ACCEPTED_CODE: &str = "wallet_send_accepted_local_only";
const LOCAL_WALLET_SIGNED_SUBMIT_ACCEPTED_CODE: &str = "signed_submit_accepted_local_only";
const LOCAL_BLOCK_PRODUCTION_AUDIT_SCOPE: &str = "api-local-accepted";
const LOCAL_SIGNED_SUBMIT_TEST_WARNING: &str = "local-private-devnet-test-signature-only";
const PRIVATE_DEVNET_TEST_SENDER: &str = "xriqdev1alice00000000000";
const PRIVATE_DEVNET_PRODUCER: &str = "xriqdev1author00000000000";
const POSTGRES_READ_MODEL_STATUS_ROUTE: &str = "/api/v1/admin/postgres/read-model-status";
const POSTGRES_NODE_STATUS_ROUTE: &str = "/api/v1/admin/node/status";
const POSTGRES_INDEXER_STATUS_ROUTE: &str = "/api/v1/admin/indexer/status";
const POSTGRES_AUDIT_EVENTS_ROUTE: &str = "/api/v1/admin/audit-events";
const POSTGRES_EXPLORER_OVERVIEW_ROUTE: &str = "/api/v1/explorer/overview";
const POSTGRES_BLOCKS_ROUTE: &str = "/api/v1/blocks";
const POSTGRES_BLOCK_DETAIL_PREFIX: &str = "/api/v1/blocks/";
const POSTGRES_TRANSACTIONS_ROUTE: &str = "/api/v1/transactions";
const POSTGRES_MEMPOOL_ROUTE: &str = "/api/v1/mempool";
const POSTGRES_WALLET_STATUS_ROUTE: &str = "/api/v1/wallet/status";
const POSTGRES_WALLET_DRAFT_PREVIEW_ROUTE: &str = "/api/v1/wallet/transfers/draft-preview";
const POSTGRES_TRANSACTION_DETAIL_PREFIX: &str = "/api/v1/transactions/";
const POSTGRES_WALLET_TRANSACTION_PREFIX: &str = "/api/v1/wallet/transactions/";
const POSTGRES_WALLET_TRANSACTION_STATUS_SUFFIX: &str = "/status";
const POSTGRES_ISO20022_TRANSACTION_PREFIX: &str = "/api/v1/iso20022/transactions/";
const POSTGRES_ISO20022_PAYMENT_INITIATION_PREVIEW_ROUTE: &str =
    "/api/v1/iso20022/payment-initiation/preview";
const POSTGRES_ISO20022_ACCOUNT_PREFIX: &str = "/api/v1/iso20022/accounts/";
const POSTGRES_ISO20022_ACCOUNT_STATEMENT_SUFFIX: &str = "/statement";
const POSTGRES_ACCOUNTS_ROUTE: &str = "/api/v1/accounts";
const POSTGRES_WALLET_ACCOUNTS_ROUTE: &str = "/api/v1/wallet/accounts";
const POSTGRES_SNAPSHOTS_ROUTE: &str = "/api/v1/snapshots";
const POSTGRES_SNAPSHOT_DETAIL_PREFIX: &str = "/api/v1/snapshots/";
const POSTGRES_ACCOUNT_DETAIL_PREFIX: &str = "/api/v1/accounts/";
const POSTGRES_ACCOUNT_HISTORY_SUFFIX: &str = "/transactions";
const POSTGRES_WALLET_ACCOUNT_PREFIX: &str = "/api/v1/wallet/accounts/";
const POSTGRES_WALLET_ACCOUNT_BALANCE_SUFFIX: &str = "/balance";
const POSTGRES_WALLET_ACCOUNT_HISTORY_SUFFIX: &str = "/history";
const POSTGRES_PRIVATE_DEVNET_NETWORK: &str = "xriq-devnet";
const POSTGRES_READ_MODEL_WARNING: &str =
    "local-private-devnet-postgres-read-only-preview-no-mutation";

type PostgresReadModelRenderer =
    for<'a> fn(&PostgresReadModelConfig<'a>, &BTreeMap<String, String>) -> Result<String, String>;

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    match run(args.iter().map(String::as_str)) {
        Ok(output) if output.is_empty() => {}
        Ok(output) => println!("{output}"),
        Err(error) => {
            eprintln!("error={error}");
            eprintln!("{}", help_text());
            process::exit(1);
        }
    }
}

fn run<'a, I>(args: I) -> Result<String, String>
where
    I: IntoIterator<Item = &'a str>,
{
    let args: Vec<&str> = args.into_iter().collect();
    match args.first().copied() {
        Some("help" | "--help" | "-h") => Ok(help_text()),
        Some("request") => run_request(&args[1..]),
        Some("request-postgres") => run_request_postgres(&args[1..]),
        Some("serve-readonly") => run_serve_readonly(&args[1..]),
        Some(command) => Err(format!("unknown command: {command}")),
        None => Err("missing command".to_string()),
    }
}

fn run_request(args: &[&str]) -> Result<String, String> {
    let config = RequestConfig::parse(args)?;
    let service = build_service(config.chain_file, config.pending_file, config.alice_balance)?;
    let mut response = None;
    if config.enable_local_wallet_submit {
        response = maybe_local_wallet_submit_http_response(
            &service,
            config.method,
            config.target,
            config.chain_file,
            config.pending_file,
            config.alice_balance,
        );
    }
    if response.is_none() && config.enable_local_wallet_send {
        response = maybe_local_wallet_send_http_response(
            &service,
            config.method,
            config.target,
            config.chain_file,
            config.pending_file,
            config.alice_balance,
        );
    }
    if response.is_none() && config.enable_local_wallet_signed_submit {
        response = maybe_local_wallet_signed_submit_http_response(
            &service,
            config.method,
            config.target,
            config.chain_file,
            config.pending_file,
            config.alice_balance,
        );
    }
    if response.is_none() && config.enable_local_block_production {
        response = maybe_local_block_production_http_response(
            &service,
            config.method,
            config.target,
            config.chain_file,
            config.pending_file,
            config.alice_balance,
        );
    }
    let response = response
        .unwrap_or_else(|| product_api_http_response(&service, config.method, config.target));

    Ok(cli_response(response))
}

fn run_request_postgres(args: &[&str]) -> Result<String, String> {
    let config = PostgresRequestConfig::parse(args)?;
    let response =
        postgres_read_model_http_response(&config.read_model, config.method, config.target)?;

    Ok(cli_response(response))
}

fn run_serve_readonly(args: &[&str]) -> Result<String, String> {
    let config = ServeConfig::parse(args)?;
    let service = build_service(config.chain_file, config.pending_file, config.alice_balance)?;
    let runtime = LocalApiRuntime {
        service,
        postgres_read_model: config.postgres_read_model,
        chain_file: config.chain_file.to_string(),
        pending_file: config.pending_file.map(ToString::to_string),
        alice_balance: config.alice_balance,
        enable_local_wallet_submit: config.enable_local_wallet_submit,
        enable_local_wallet_send: config.enable_local_wallet_send,
        enable_local_wallet_signed_submit: config.enable_local_wallet_signed_submit,
        enable_local_block_production: config.enable_local_block_production,
    };
    let mut runtime = runtime;
    let listener = TcpListener::bind(config.bind)
        .map_err(|error| format!("could not bind xriq-api to {}: {error}", config.bind))?;
    eprintln!(
        "xriq-api private-devnet read-only server listening on {}",
        listener
            .local_addr()
            .map(|address| address.to_string())
            .unwrap_or_else(|_| config.bind.to_string())
    );

    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                if let Err(error) = handle_connection(&mut runtime, stream) {
                    eprintln!("xriq-api connection error: {error}");
                }
            }
            Err(error) => eprintln!("xriq-api accept error: {error}"),
        }
    }

    Ok(String::new())
}

fn build_service(
    chain_file: &str,
    pending_file: Option<&str>,
    alice_balance: Option<XriqAmount>,
) -> Result<XriqApiService, String> {
    if !Path::new(chain_file).exists() {
        return Err(format!(
            "chain file does not exist: {chain_file}; run xriq-node first or pass an existing chain file"
        ));
    }
    let store = FileChainStore::open(chain_file)
        .map_err(|error| format!("could not open chain file {chain_file}: {error:?}"))?;
    let snapshot = index_private_devnet_store(&store, alice_balance)
        .map_err(|error| format!("index replay failed: {error}"))?;
    let expected_chain_id = snapshot.chain_id.clone();
    let mut service = XriqApiService::new(snapshot);
    if let Some(pending_file) = pending_file {
        let pending_path = Path::new(pending_file);
        if pending_path.exists() {
            let pending_text = fs::read_to_string(pending_path)
                .map_err(|error| format!("could not read pending file {pending_file}: {error}"))?;
            let pending_entries =
                pending_mempool_entries_from_tsv(&pending_text, &expected_chain_id).map_err(
                    |error| format!("could not parse pending file {pending_file}: {error}"),
                )?;
            service = service.with_pending_mempool_entries(pending_entries);
        }
    }
    Ok(service)
}

struct LocalApiRuntime<'a> {
    service: XriqApiService,
    postgres_read_model: Option<PostgresReadModelConfig<'a>>,
    chain_file: String,
    pending_file: Option<String>,
    alice_balance: Option<XriqAmount>,
    enable_local_wallet_submit: bool,
    enable_local_wallet_send: bool,
    enable_local_wallet_signed_submit: bool,
    enable_local_block_production: bool,
}

fn handle_connection(
    runtime: &mut LocalApiRuntime<'_>,
    mut stream: TcpStream,
) -> Result<(), String> {
    let mut buffer = [0_u8; 8192];
    let bytes_read = stream
        .read(&mut buffer)
        .map_err(|error| format!("could not read request: {error}"))?;
    if bytes_read == 0 {
        return Ok(());
    }

    let request = std::str::from_utf8(&buffer[..bytes_read])
        .map_err(|error| format!("request was not valid UTF-8: {error}"))?;
    let first_line = request
        .lines()
        .next()
        .ok_or_else(|| "request was empty".to_string())?;
    let response = match parse_http_request_line(first_line) {
        Ok((method, target)) => local_api_http_response(runtime, method, target),
        Err(message) => bad_request_response(&message),
    };

    stream
        .write_all(response.to_http_response().as_bytes())
        .map_err(|error| format!("could not write response: {error}"))?;
    stream
        .flush()
        .map_err(|error| format!("could not flush response: {error}"))
}

fn local_api_http_response(
    runtime: &mut LocalApiRuntime<'_>,
    method: &str,
    target: &str,
) -> ApiHttpResponse {
    if let Some(response) = maybe_postgres_read_model_http_response(
        runtime.postgres_read_model.as_ref(),
        method,
        target,
    ) {
        return response.unwrap_or_else(|error| {
            local_api_error_response(503, "postgres_read_model_unavailable", &error)
        });
    }

    if runtime.enable_local_wallet_submit {
        if let Some(response) = maybe_local_wallet_submit_http_response(
            &runtime.service,
            method,
            target,
            &runtime.chain_file,
            runtime.pending_file.as_deref(),
            runtime.alice_balance,
        ) {
            if let Some(error) = refresh_runtime_after_local_mutation(runtime, &response) {
                return error;
            }
            return response;
        }
    }

    if runtime.enable_local_wallet_send {
        if let Some(response) = maybe_local_wallet_send_http_response(
            &runtime.service,
            method,
            target,
            &runtime.chain_file,
            runtime.pending_file.as_deref(),
            runtime.alice_balance,
        ) {
            if let Some(error) = refresh_runtime_after_local_mutation(runtime, &response) {
                return error;
            }
            return response;
        }
    }

    if runtime.enable_local_wallet_signed_submit {
        if let Some(response) = maybe_local_wallet_signed_submit_http_response(
            &runtime.service,
            method,
            target,
            &runtime.chain_file,
            runtime.pending_file.as_deref(),
            runtime.alice_balance,
        ) {
            if let Some(error) = refresh_runtime_after_local_mutation(runtime, &response) {
                return error;
            }
            return response;
        }
    }

    if runtime.enable_local_block_production {
        if let Some(response) = maybe_local_block_production_http_response(
            &runtime.service,
            method,
            target,
            &runtime.chain_file,
            runtime.pending_file.as_deref(),
            runtime.alice_balance,
        ) {
            if let Some(error) = refresh_runtime_after_local_mutation(runtime, &response) {
                return error;
            }
            return response;
        }
    }

    product_api_http_response(&runtime.service, method, target)
}

fn refresh_runtime_after_local_mutation(
    runtime: &mut LocalApiRuntime<'_>,
    response: &ApiHttpResponse,
) -> Option<ApiHttpResponse> {
    if response.status_code != 201 {
        return None;
    }
    match build_service(
        &runtime.chain_file,
        runtime.pending_file.as_deref(),
        runtime.alice_balance,
    ) {
        Ok(service) => {
            runtime.service = service;
            None
        }
        Err(error) => Some(local_api_error_response(
            503,
            "local_state_refresh_failed",
            &error,
        )),
    }
}

fn maybe_local_wallet_submit_http_response(
    service: &XriqApiService,
    method: &str,
    target: &str,
    chain_file: &str,
    pending_file: Option<&str>,
    alice_balance: Option<XriqAmount>,
) -> Option<ApiHttpResponse> {
    let (path, query) = split_http_target(target);
    if method != "POST" || path != WALLET_SUBMIT_ROUTE {
        return None;
    }
    Some(local_wallet_submit_http_response(
        service,
        query,
        chain_file,
        pending_file,
        alice_balance,
    ))
}

fn local_wallet_submit_http_response(
    service: &XriqApiService,
    query: Option<&str>,
    chain_file: &str,
    pending_file: Option<&str>,
    alice_balance: Option<XriqAmount>,
) -> ApiHttpResponse {
    let Some(pending_file) = pending_file else {
        return local_api_error_response(
            400,
            "missing_pending_file",
            "accepted local wallet submit requires --pending-file",
        );
    };
    let request = match LocalWalletSubmitRequest::from_query(service, query) {
        Ok(request) => request,
        Err(response) => return response,
    };
    if query_param(query, "dry_run") == Some("true") {
        return local_api_error_response(
            400,
            "dry_run_not_enabled",
            "dry_run is contract-only in this checkpoint and does not mutate state",
        );
    }

    let before_count = service.mempool(usize::MAX).pending_count;
    let body = render_local_wallet_submit_transfer_body(service, &request);
    let detail = match private_devnet_file_submit_pending_transfer_body(
        chain_file,
        pending_file,
        alice_balance,
        &body,
    ) {
        Ok(detail) => detail,
        Err(error) => {
            return local_api_error_response(
                400,
                error.code(),
                &format!("local wallet submit failed: {error}"),
            );
        }
    };

    render_local_wallet_submit_accepted_response(
        service,
        &detail,
        LocalWalletSubmitRenderInput {
            local_request_id: request.local_request_id,
            draft_id: request.draft_id,
            chain_file,
            pending_file,
            before_count,
            after_count: before_count + 1,
        },
    )
}

#[derive(Debug, Clone, Copy)]
struct LocalWalletSubmitRequest<'a> {
    local_request_id: &'a str,
    draft_id: &'a str,
    from_address: &'a str,
    to_address: &'a str,
    amount: XriqAmount,
    fee: XriqAmount,
    nonce: u64,
    expires_at_height: u64,
}

impl<'a> LocalWalletSubmitRequest<'a> {
    fn from_query(
        service: &XriqApiService,
        query: Option<&'a str>,
    ) -> Result<Self, ApiHttpResponse> {
        let local_request_id = required_query_param_any(query, &["local_request_id"])
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        if !valid_local_request_id(local_request_id) {
            return Err(local_api_error_response(
                400,
                "invalid_local_request_id",
                "local_request_id must use letters, digits, dash, or underscore and be 1-64 characters",
            ));
        }
        let draft_id = required_query_param_any(query, &["draft_id"])
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        if !valid_local_request_id(draft_id) {
            return Err(local_api_error_response(
                400,
                "invalid_draft_id",
                "draft_id must use letters, digits, dash, or underscore and be 1-64 characters",
            ));
        }
        let from_address = required_query_param_any(query, &["from_address", "from"])
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        if let Err(error) = validate_xriq_address(from_address, "from_address") {
            return Err(local_api_error_response(400, "bad_request", &error));
        }
        if from_address != PRIVATE_DEVNET_TEST_SENDER {
            return Err(local_api_error_response(
                400,
                "invalid_sender",
                "wallet submit is limited to the configured private-devnet Alice test sender",
            ));
        }
        let to_address = required_query_param_any(query, &["to_address", "to"])
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        if let Err(error) = validate_xriq_address(to_address, "to_address") {
            return Err(local_api_error_response(400, "bad_request", &error));
        }
        if from_address == to_address {
            return Err(local_api_error_response(
                400,
                "self_transfer",
                "from_address and to_address must differ",
            ));
        }
        let amount_units = required_query_param_any(query, &["amount_base_units", "amount"])
            .and_then(|value| parse_u128_query(value, "amount_base_units"))
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        if amount_units == 0 {
            return Err(local_api_error_response(
                400,
                "zero_amount",
                "amount_base_units must be greater than zero",
            ));
        }
        let fee_units = required_query_param_any(query, &["fee_base_units", "fee"])
            .and_then(|value| parse_u128_query(value, "fee_base_units"))
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        if fee_units < PRIVATE_DEVNET_MIN_FEE_BASE_UNITS {
            return Err(local_api_error_response(
                400,
                "fee_too_low",
                "fee_base_units must satisfy the private-devnet minimum fee",
            ));
        }
        let nonce = required_query_param_any(query, &["nonce"])
            .and_then(|value| parse_u64_query(value, "nonce"))
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        let expires_at_height = required_query_param_any(query, &["expires_at_height"])
            .and_then(|value| parse_u64_query(value, "expires_at_height"))
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        if expires_at_height <= service.snapshot().current_height {
            return Err(local_api_error_response(
                400,
                "expired",
                "expires_at_height must be greater than current local height",
            ));
        }

        Ok(Self {
            local_request_id,
            draft_id,
            from_address,
            to_address,
            amount: XriqAmount::from_base_units(amount_units),
            fee: XriqAmount::from_base_units(fee_units),
            nonce,
            expires_at_height,
        })
    }
}

#[derive(Debug, Clone)]
struct LocalWalletSignedSubmitPreviewRequest<'a> {
    local_request_id: &'a str,
    envelope: SignedSubmitEnvelopeInput<'a>,
}

impl<'a> LocalWalletSignedSubmitPreviewRequest<'a> {
    fn from_query(query: Option<&'a str>) -> Result<Self, ApiHttpResponse> {
        let local_request_id = required_query_param_any(query, &["local_request_id"])
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        if !valid_local_request_id(local_request_id) {
            return Err(local_api_error_response(
                400,
                "invalid_local_request_id",
                "local_request_id must use letters, digits, dash, or underscore and be 1-64 characters",
            ));
        }
        let version = optional_u16_query(query, "version")
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        let nonce = query_param(query, "nonce")
            .map(|value| parse_u64_query(value, "nonce"))
            .transpose()
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        let expires_at_height = query_param(query, "expires_at_height")
            .map(|value| parse_u64_query(value, "expires_at_height"))
            .transpose()
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;

        Ok(Self {
            local_request_id,
            envelope: SignedSubmitEnvelopeInput {
                format_version: query_param(query, "format_version")
                    .or_else(|| query_param(query, "signed_transfer_envelope")),
                transaction: Some(SignedSubmitTransactionInput {
                    version,
                    chain_id: query_param(query, "chain_id"),
                    from: query_param(query, "from_address").or_else(|| query_param(query, "from")),
                    to: query_param(query, "to_address").or_else(|| query_param(query, "to")),
                    amount_base_units: query_param(query, "amount_base_units")
                        .or_else(|| query_param(query, "amount")),
                    fee_base_units: query_param(query, "fee_base_units")
                        .or_else(|| query_param(query, "fee")),
                    nonce,
                    expires_at_height,
                }),
                hashes: Some(SignedSubmitHashesInput {
                    transaction_signing_hash: query_param(query, "transaction_signing_hash"),
                    transaction_hash: query_param(query, "transaction_hash"),
                }),
                signature_envelope: Some(SignedSubmitSignatureEnvelopeInput {
                    algorithm: query_param(query, "signature_algorithm")
                        .or_else(|| query_param(query, "algorithm")),
                    signature_encoding: query_param(query, "signature_encoding"),
                }),
            },
        })
    }

    fn verify_preview(
        &self,
        service: &XriqApiService,
    ) -> Result<SignedSubmitVerificationOk, SignedSubmitVerificationRefusal> {
        let mempool = service.mempool(usize::MAX);
        let pending_hashes = mempool
            .entries
            .iter()
            .map(|entry| entry.tx_hash.as_str())
            .collect::<Vec<_>>();
        let sender_chain_nonce = self
            .envelope
            .transaction
            .as_ref()
            .and_then(|transaction| transaction.from)
            .and_then(|from| service.account(from).ok().map(|account| account.nonce))
            .unwrap_or(0);
        verify_signed_submit_envelope_preview(
            self.envelope.clone(),
            SignedSubmitStateContext {
                expected_chain_id: &service.snapshot().chain_id,
                current_height: service.snapshot().current_height,
                sender_chain_nonce,
                pending_transaction_hashes: &pending_hashes,
            },
        )
    }
}

fn maybe_local_wallet_signed_submit_http_response(
    service: &XriqApiService,
    method: &str,
    target: &str,
    chain_file: &str,
    pending_file: Option<&str>,
    alice_balance: Option<XriqAmount>,
) -> Option<ApiHttpResponse> {
    let (path, query) = split_http_target(target);
    if method != "POST" || path != WALLET_SIGNED_SUBMIT_ROUTE {
        return None;
    }
    Some(local_wallet_signed_submit_http_response(
        service,
        query,
        chain_file,
        pending_file,
        alice_balance,
    ))
}

fn local_wallet_signed_submit_http_response(
    service: &XriqApiService,
    query: Option<&str>,
    chain_file: &str,
    pending_file: Option<&str>,
    alice_balance: Option<XriqAmount>,
) -> ApiHttpResponse {
    let Some(pending_file) = pending_file else {
        return local_api_error_response(
            400,
            "missing_pending_file",
            "accepted local signed wallet submit requires --pending-file",
        );
    };
    if query_param(query, "dry_run") == Some("true") {
        return local_api_error_response(
            400,
            "dry_run_not_enabled",
            "dry_run is contract-only in this checkpoint and does not mutate state",
        );
    }
    if let Some(field) = forbidden_signed_submit_query_field(query) {
        return local_api_error_response(
            400,
            "forbidden_signed_submit_field",
            &format!("{field} is not accepted by the local/private signed-submit endpoint"),
        );
    }
    let request = match LocalWalletSignedSubmitPreviewRequest::from_query(query) {
        Ok(request) => request,
        Err(response) => return response,
    };
    if let Some(transaction) = request.envelope.transaction {
        if let Some(from_address) = transaction.from {
            if from_address != PRIVATE_DEVNET_TEST_SENDER {
                return local_api_error_response(
                    400,
                    "invalid_sender",
                    "signed wallet submit is limited to the configured private-devnet Alice test sender",
                );
            }
        }
    }

    let verified = match request.verify_preview(service) {
        Ok(verified) => verified,
        Err(refusal) => {
            return render_local_wallet_signed_submit_verification_refusal_response(
                service, &request, refusal,
            );
        }
    };

    let before_count = service.mempool(usize::MAX).pending_count;
    let body = match render_local_wallet_signed_submit_transfer_body(service, &request) {
        Ok(body) => body,
        Err(response) => return response,
    };
    let detail = match private_devnet_file_submit_pending_transfer_body(
        chain_file,
        pending_file,
        alice_balance,
        &body,
    ) {
        Ok(detail) => detail,
        Err(error) => {
            return local_api_error_response(
                400,
                error.code(),
                &format!("local signed wallet submit failed: {error}"),
            );
        }
    };
    let detail_tx_hash = hash_hex(detail.tx_hash);
    if detail_tx_hash != verified.transaction_hash {
        return local_api_error_response(
            503,
            "signed_submit_hash_drift",
            "local signed wallet submit wrote a transaction hash different from the verified envelope",
        );
    }

    render_local_wallet_signed_submit_accepted_response(
        service,
        &detail,
        &verified,
        LocalWalletSignedSubmitRenderInput {
            local_request_id: request.local_request_id,
            chain_file,
            pending_file,
            before_count,
            after_count: before_count + 1,
        },
    )
}

fn forbidden_signed_submit_query_field(query: Option<&str>) -> Option<&'static str> {
    [
        "private_key",
        "seed_phrase",
        "mnemonic",
        "secret_key",
        "raw_signature",
        "custody_account",
        "public_network_endpoint",
        "dex_route",
    ]
    .into_iter()
    .find(|field| query_param(query, field).is_some())
}

fn render_local_wallet_signed_submit_verification_refusal_response(
    service: &XriqApiService,
    request: &LocalWalletSignedSubmitPreviewRequest<'_>,
    refusal: SignedSubmitVerificationRefusal,
) -> ApiHttpResponse {
    let reason = match refusal.http_status {
        400 => "Bad Request",
        409 => "Conflict",
        503 => "Service Unavailable",
        _ => "Error",
    };
    let event_id = refusal
        .audit_event_id
        .replace("local_request_id", request.local_request_id);
    let mut body = String::new();
    writeln!(&mut body, "{{").expect("write to String");
    writeln!(&mut body, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut body,
        "  \"network\": {},",
        json_string(&service.snapshot().chain_id)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "  \"endpoint\": {},",
        json_string(refusal.endpoint)
    )
    .expect("write to String");
    writeln!(&mut body, "  \"code\": {},", json_string(refusal.code)).expect("write to String");
    writeln!(&mut body, "  \"status\": {},", json_string(refusal.status)).expect("write to String");
    writeln!(
        &mut body,
        "  \"mutation\": {},",
        json_string(refusal.mutation)
    )
    .expect("write to String");
    writeln!(&mut body, "  \"verification\": {{").expect("write to String");
    writeln!(
        &mut body,
        "    \"verifier\": {},",
        json_string(refusal.verifier)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"verifier_error\": {},",
        json_string(refusal.verifier_error)
    )
    .expect("write to String");
    writeln!(&mut body, "    \"verified\": false,").expect("write to String");
    writeln!(
        &mut body,
        "    \"pending_write_allowed\": {},",
        refusal.pending_write_allowed
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"pending_state_unchanged\": {},",
        refusal.pending_state_unchanged
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"chain_state_unchanged\": {}",
        refusal.chain_state_unchanged
    )
    .expect("write to String");
    writeln!(&mut body, "  }},").expect("write to String");
    writeln!(&mut body, "  \"audit_event_recorded\": true,").expect("write to String");
    writeln!(&mut body, "  \"audit_event\": {{").expect("write to String");
    writeln!(&mut body, "    \"event_id\": {},", json_string(&event_id)).expect("write to String");
    writeln!(
        &mut body,
        "    \"actor\": {},",
        json_string(LOCAL_REFUSAL_AUDIT_ACTOR)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"action\": {},",
        json_string(WALLET_SIGNED_SUBMIT_AUDIT_ACTION)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"resource_type\": {},",
        json_string(WALLET_AUDIT_RESOURCE_TYPE)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"resource_id\": {},",
        json_string(request.local_request_id)
    )
    .expect("write to String");
    writeln!(&mut body, "    \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(&mut body, "    \"metadata\": {{").expect("write to String");
    writeln!(
        &mut body,
        "      \"endpoint\": {},",
        json_string(SIGNED_SUBMIT_ENDPOINT)
    )
    .expect("write to String");
    writeln!(&mut body, "      \"outcome\": \"refused\",").expect("write to String");
    writeln!(
        &mut body,
        "      \"refusal_code\": {},",
        json_string(refusal.code)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"explicit_flag\": {},",
        json_string(ENABLE_LOCAL_WALLET_SIGNED_SUBMIT_FLAG)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"local_request_id\": {},",
        json_string(request.local_request_id)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"metadata_policy\": \"request fields and verifier metadata only; no key material, raw signatures, or custody material\""
    )
    .expect("write to String");
    writeln!(&mut body, "    }}").expect("write to String");
    writeln!(&mut body, "  }}").expect("write to String");
    body.push('}');

    ApiHttpResponse {
        status_code: refusal.http_status,
        reason,
        body,
    }
}

fn render_local_wallet_signed_submit_transfer_body(
    service: &XriqApiService,
    request: &LocalWalletSignedSubmitPreviewRequest<'_>,
) -> Result<String, ApiHttpResponse> {
    let Some(transaction) = request.envelope.transaction else {
        return Err(local_api_error_response(
            400,
            "malformed_signed_envelope",
            "missing signed-submit transaction",
        ));
    };
    let version = transaction.version.ok_or_else(|| {
        local_api_error_response(
            400,
            "malformed_signed_envelope",
            "missing signed-submit transaction.version",
        )
    })?;
    let chain_id = transaction.chain_id.ok_or_else(|| {
        local_api_error_response(
            400,
            "malformed_signed_envelope",
            "missing signed-submit transaction.chain_id",
        )
    })?;
    let from = transaction.from.ok_or_else(|| {
        local_api_error_response(
            400,
            "malformed_signed_envelope",
            "missing signed-submit transaction.from",
        )
    })?;
    let to = transaction.to.ok_or_else(|| {
        local_api_error_response(
            400,
            "malformed_signed_envelope",
            "missing signed-submit transaction.to",
        )
    })?;
    let amount_base_units = transaction.amount_base_units.ok_or_else(|| {
        local_api_error_response(
            400,
            "malformed_signed_envelope",
            "missing signed-submit transaction.amount_base_units",
        )
    })?;
    let fee_base_units = transaction.fee_base_units.ok_or_else(|| {
        local_api_error_response(
            400,
            "malformed_signed_envelope",
            "missing signed-submit transaction.fee_base_units",
        )
    })?;
    let nonce = transaction.nonce.ok_or_else(|| {
        local_api_error_response(
            400,
            "malformed_signed_envelope",
            "missing signed-submit transaction.nonce",
        )
    })?;
    let expires_at_height = transaction.expires_at_height.ok_or_else(|| {
        local_api_error_response(
            400,
            "malformed_signed_envelope",
            "missing signed-submit transaction.expires_at_height",
        )
    })?;

    let mut body = String::new();
    writeln!(&mut body, "{{").expect("write to String");
    writeln!(
        &mut body,
        "  \"format_version\": \"xriq-node-transfer-submit-v1\","
    )
    .expect("write to String");
    writeln!(&mut body, "  \"version\": {version},").expect("write to String");
    writeln!(&mut body, "  \"chain_id\": {},", json_string(chain_id)).expect("write to String");
    writeln!(&mut body, "  \"from\": {},", json_string(from)).expect("write to String");
    writeln!(&mut body, "  \"to\": {},", json_string(to)).expect("write to String");
    writeln!(
        &mut body,
        "  \"amount_base_units\": {},",
        json_string(amount_base_units)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "  \"fee_base_units\": {},",
        json_string(fee_base_units)
    )
    .expect("write to String");
    writeln!(&mut body, "  \"nonce\": {nonce},").expect("write to String");
    writeln!(&mut body, "  \"expires_at_height\": {expires_at_height}").expect("write to String");
    body.push('}');

    if chain_id != service.snapshot().chain_id {
        return Err(local_api_error_response(
            400,
            "wrong_chain_id",
            "signed-submit chain_id does not match local private-devnet chain",
        ));
    }

    Ok(body)
}

#[derive(Debug, Clone, Copy)]
struct LocalWalletSignedSubmitRenderInput<'a> {
    local_request_id: &'a str,
    chain_file: &'a str,
    pending_file: &'a str,
    before_count: usize,
    after_count: usize,
}

fn render_local_wallet_signed_submit_accepted_response(
    service: &XriqApiService,
    detail: &PrivateDevnetPendingTransactionDetail,
    verified: &SignedSubmitVerificationOk,
    input: LocalWalletSignedSubmitRenderInput<'_>,
) -> ApiHttpResponse {
    let tx = &detail.transaction;
    let tx_hash = hash_hex(detail.tx_hash);
    let expires_at_height = tx
        .expires_at_height
        .unwrap_or(service.snapshot().current_height + 1);
    let mut body = String::new();
    writeln!(&mut body, "{{").expect("write to String");
    writeln!(&mut body, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut body,
        "  \"network\": {},",
        json_string(&service.snapshot().chain_id)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "  \"endpoint\": {},",
        json_string(SIGNED_SUBMIT_ENDPOINT)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "  \"code\": {},",
        json_string(LOCAL_WALLET_SIGNED_SUBMIT_ACCEPTED_CODE)
    )
    .expect("write to String");
    writeln!(&mut body, "  \"status\": \"pending\",").expect("write to String");
    writeln!(&mut body, "  \"mutation\": \"pending_state_only\",").expect("write to String");
    writeln!(
        &mut body,
        "  \"warning\": {},",
        json_string(LOCAL_SIGNED_SUBMIT_TEST_WARNING)
    )
    .expect("write to String");
    writeln!(&mut body, "  \"transaction\": {{").expect("write to String");
    writeln!(&mut body, "    \"tx_hash\": {},", json_string(&tx_hash)).expect("write to String");
    writeln!(&mut body, "    \"status\": \"pending\",").expect("write to String");
    writeln!(
        &mut body,
        "    \"from_address\": {},",
        json_string(tx.from.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"to_address\": {},",
        json_string(tx.to.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"amount_base_units\": {},",
        json_string(&tx.amount.base_units().to_string())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"fee_base_units\": {},",
        json_string(&tx.fee.base_units().to_string())
    )
    .expect("write to String");
    writeln!(&mut body, "    \"nonce\": {},", tx.nonce).expect("write to String");
    writeln!(
        &mut body,
        "    \"expires_at_height\": {},",
        expires_at_height
    )
    .expect("write to String");
    writeln!(&mut body, "    \"block_height\": null,").expect("write to String");
    writeln!(&mut body, "    \"transaction_index\": null").expect("write to String");
    writeln!(&mut body, "  }},").expect("write to String");
    writeln!(&mut body, "  \"verification\": {{").expect("write to String");
    writeln!(
        &mut body,
        "    \"signature_algorithm\": {},",
        json_string(verified.signature_algorithm)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"transaction_signing_hash\": {},",
        json_string(&verified.transaction_signing_hash)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"transaction_hash\": {},",
        json_string(&verified.transaction_hash)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"verifier\": {},",
        json_string(verified.verifier)
    )
    .expect("write to String");
    writeln!(&mut body, "    \"verified\": {}", verified.verified).expect("write to String");
    writeln!(&mut body, "  }},").expect("write to String");
    writeln!(&mut body, "  \"pending_state\": {{").expect("write to String");
    writeln!(&mut body, "    \"before_count\": {},", input.before_count).expect("write to String");
    writeln!(&mut body, "    \"after_count\": {},", input.after_count).expect("write to String");
    writeln!(
        &mut body,
        "    \"added_tx_hash\": {},",
        json_string(&tx_hash)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"pending_file\": {}",
        json_string(input.pending_file)
    )
    .expect("write to String");
    writeln!(&mut body, "  }},").expect("write to String");
    writeln!(&mut body, "  \"chain_state\": {{").expect("write to String");
    writeln!(
        &mut body,
        "    \"current_height\": {},",
        service.snapshot().current_height
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"latest_block_hash\": {},",
        json_string(&service.snapshot().latest_block_hash)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"chain_file\": {},",
        json_string(input.chain_file)
    )
    .expect("write to String");
    writeln!(&mut body, "    \"chain_unchanged\": true").expect("write to String");
    writeln!(&mut body, "  }},").expect("write to String");
    writeln!(&mut body, "  \"audit_event_recorded\": true,").expect("write to String");
    writeln!(&mut body, "  \"audit_event\": {{").expect("write to String");
    writeln!(
        &mut body,
        "    \"event_id\": {},",
        json_string(&format!(
            "signed-submit-accepted:{}",
            input.local_request_id
        ))
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"actor\": {},",
        json_string(LOCAL_REFUSAL_AUDIT_ACTOR)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"action\": {},",
        json_string(WALLET_SIGNED_SUBMIT_AUDIT_ACTION)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"resource_type\": {},",
        json_string(WALLET_AUDIT_RESOURCE_TYPE)
    )
    .expect("write to String");
    writeln!(&mut body, "    \"resource_id\": {},", json_string(&tx_hash))
        .expect("write to String");
    writeln!(&mut body, "    \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(&mut body, "    \"metadata\": {{").expect("write to String");
    writeln!(
        &mut body,
        "      \"endpoint\": {},",
        json_string(SIGNED_SUBMIT_ENDPOINT)
    )
    .expect("write to String");
    writeln!(&mut body, "      \"outcome\": \"accepted\",").expect("write to String");
    writeln!(&mut body, "      \"status\": \"pending\",").expect("write to String");
    writeln!(
        &mut body,
        "      \"explicit_flag\": {},",
        json_string(ENABLE_LOCAL_WALLET_SIGNED_SUBMIT_FLAG)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"local_request_id\": {},",
        json_string(input.local_request_id)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"from_address\": {},",
        json_string(tx.from.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"to_address\": {},",
        json_string(tx.to.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"amount_base_units\": {},",
        json_string(&tx.amount.base_units().to_string())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"fee_base_units\": {},",
        json_string(&tx.fee.base_units().to_string())
    )
    .expect("write to String");
    writeln!(&mut body, "      \"nonce\": {},", tx.nonce).expect("write to String");
    writeln!(
        &mut body,
        "      \"expires_at_height\": {},",
        expires_at_height
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"signature_algorithm\": {},",
        json_string(verified.signature_algorithm)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"verifier\": {},",
        json_string(verified.verifier)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"pending_before_count\": {},",
        input.before_count
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"pending_after_count\": {},",
        input.after_count
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"added_tx_hash\": {},",
        json_string(&tx_hash)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"chain_current_height\": {},",
        service.snapshot().current_height
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"metadata_policy\": \"request fields, hashes, verifier result, and local pending-state transition summary only; no key material or custody material\""
    )
    .expect("write to String");
    writeln!(&mut body, "    }}").expect("write to String");
    writeln!(&mut body, "  }}").expect("write to String");
    body.push('}');

    ApiHttpResponse {
        status_code: 201,
        reason: "Created",
        body,
    }
}

fn render_local_wallet_submit_transfer_body(
    service: &XriqApiService,
    request: &LocalWalletSubmitRequest<'_>,
) -> String {
    let mut body = String::new();
    writeln!(&mut body, "{{").expect("write to String");
    writeln!(
        &mut body,
        "  \"format_version\": \"xriq-node-transfer-submit-v1\","
    )
    .expect("write to String");
    writeln!(&mut body, "  \"version\": 1,").expect("write to String");
    writeln!(
        &mut body,
        "  \"chain_id\": {},",
        json_string(&service.snapshot().chain_id)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "  \"from\": {},",
        json_string(request.from_address)
    )
    .expect("write to String");
    writeln!(&mut body, "  \"to\": {},", json_string(request.to_address)).expect("write to String");
    writeln!(
        &mut body,
        "  \"amount_base_units\": {},",
        json_string(&request.amount.base_units().to_string())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "  \"fee_base_units\": {},",
        json_string(&request.fee.base_units().to_string())
    )
    .expect("write to String");
    writeln!(&mut body, "  \"nonce\": {},", request.nonce).expect("write to String");
    writeln!(
        &mut body,
        "  \"expires_at_height\": {}",
        request.expires_at_height
    )
    .expect("write to String");
    body.push('}');
    body
}

#[derive(Debug, Clone, Copy)]
struct LocalWalletSubmitRenderInput<'a> {
    local_request_id: &'a str,
    draft_id: &'a str,
    chain_file: &'a str,
    pending_file: &'a str,
    before_count: usize,
    after_count: usize,
}

fn render_local_wallet_submit_accepted_response(
    service: &XriqApiService,
    detail: &PrivateDevnetPendingTransactionDetail,
    input: LocalWalletSubmitRenderInput<'_>,
) -> ApiHttpResponse {
    let tx = &detail.transaction;
    let tx_hash = hash_hex(detail.tx_hash);
    let expires_at_height = tx
        .expires_at_height
        .unwrap_or(service.snapshot().current_height + 1);
    let mut body = String::new();
    writeln!(&mut body, "{{").expect("write to String");
    writeln!(&mut body, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut body,
        "  \"network\": {},",
        json_string(&service.snapshot().chain_id)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "  \"endpoint\": {},",
        json_string(WALLET_SUBMIT_ENDPOINT)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "  \"code\": {},",
        json_string(LOCAL_WALLET_SUBMIT_ACCEPTED_CODE)
    )
    .expect("write to String");
    writeln!(&mut body, "  \"status\": \"pending\",").expect("write to String");
    writeln!(&mut body, "  \"mutation\": \"pending_state_only\",").expect("write to String");
    writeln!(&mut body, "  \"warning\": \"local-private-devnet-only\",").expect("write to String");
    writeln!(&mut body, "  \"transaction\": {{").expect("write to String");
    writeln!(&mut body, "    \"tx_hash\": {},", json_string(&tx_hash)).expect("write to String");
    writeln!(&mut body, "    \"status\": \"pending\",").expect("write to String");
    writeln!(
        &mut body,
        "    \"from_address\": {},",
        json_string(tx.from.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"to_address\": {},",
        json_string(tx.to.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"amount_base_units\": {},",
        json_string(&tx.amount.base_units().to_string())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"fee_base_units\": {},",
        json_string(&tx.fee.base_units().to_string())
    )
    .expect("write to String");
    writeln!(&mut body, "    \"nonce\": {},", tx.nonce).expect("write to String");
    writeln!(
        &mut body,
        "    \"expires_at_height\": {},",
        expires_at_height
    )
    .expect("write to String");
    writeln!(&mut body, "    \"block_height\": null,").expect("write to String");
    writeln!(&mut body, "    \"transaction_index\": null").expect("write to String");
    writeln!(&mut body, "  }},").expect("write to String");
    writeln!(&mut body, "  \"pending_state\": {{").expect("write to String");
    writeln!(&mut body, "    \"before_count\": {},", input.before_count).expect("write to String");
    writeln!(&mut body, "    \"after_count\": {},", input.after_count).expect("write to String");
    writeln!(
        &mut body,
        "    \"added_tx_hash\": {},",
        json_string(&tx_hash)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"pending_file\": {}",
        json_string(input.pending_file)
    )
    .expect("write to String");
    writeln!(&mut body, "  }},").expect("write to String");
    writeln!(&mut body, "  \"chain_state\": {{").expect("write to String");
    writeln!(
        &mut body,
        "    \"current_height\": {},",
        service.snapshot().current_height
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"latest_block_hash\": {},",
        json_string(&service.snapshot().latest_block_hash)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"chain_file\": {},",
        json_string(input.chain_file)
    )
    .expect("write to String");
    writeln!(&mut body, "    \"chain_unchanged\": true").expect("write to String");
    writeln!(&mut body, "  }},").expect("write to String");
    writeln!(&mut body, "  \"audit_event_recorded\": true,").expect("write to String");
    writeln!(&mut body, "  \"audit_event\": {{").expect("write to String");
    writeln!(
        &mut body,
        "    \"event_id\": {},",
        json_string(&format!(
            "wallet-transfer-submit:{}",
            input.local_request_id
        ))
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"actor\": {},",
        json_string(LOCAL_REFUSAL_AUDIT_ACTOR)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"action\": {},",
        json_string(WALLET_SUBMIT_AUDIT_ACTION)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"resource_type\": {},",
        json_string(WALLET_AUDIT_RESOURCE_TYPE)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"resource_id\": {},",
        json_string(WALLET_SUBMIT_AUDIT_RESOURCE_ID)
    )
    .expect("write to String");
    writeln!(&mut body, "    \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(&mut body, "    \"metadata\": {{").expect("write to String");
    writeln!(
        &mut body,
        "      \"endpoint\": {},",
        json_string(WALLET_SUBMIT_ENDPOINT)
    )
    .expect("write to String");
    writeln!(&mut body, "      \"outcome\": \"accepted\",").expect("write to String");
    writeln!(&mut body, "      \"status\": \"pending\",").expect("write to String");
    writeln!(
        &mut body,
        "      \"explicit_flag\": {},",
        json_string(ENABLE_LOCAL_WALLET_SUBMIT_FLAG)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"local_request_id\": {},",
        json_string(input.local_request_id)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"draft_id\": {},",
        json_string(input.draft_id)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"from_address\": {},",
        json_string(tx.from.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"to_address\": {},",
        json_string(tx.to.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"amount_base_units\": {},",
        json_string(&tx.amount.base_units().to_string())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"fee_base_units\": {},",
        json_string(&tx.fee.base_units().to_string())
    )
    .expect("write to String");
    writeln!(&mut body, "      \"nonce\": {},", tx.nonce).expect("write to String");
    writeln!(
        &mut body,
        "      \"expires_at_height\": {},",
        expires_at_height
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"pending_before_count\": {},",
        input.before_count
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"pending_after_count\": {},",
        input.after_count
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"added_tx_hash\": {},",
        json_string(&tx_hash)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"chain_current_height\": {},",
        service.snapshot().current_height
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"metadata_policy\": \"request fields and local pending-state transition summary only; no signing material or custody material\""
    )
    .expect("write to String");
    writeln!(&mut body, "    }}").expect("write to String");
    writeln!(&mut body, "  }}").expect("write to String");
    body.push('}');

    ApiHttpResponse {
        status_code: 201,
        reason: "Created",
        body,
    }
}

fn maybe_local_wallet_send_http_response(
    service: &XriqApiService,
    method: &str,
    target: &str,
    chain_file: &str,
    pending_file: Option<&str>,
    alice_balance: Option<XriqAmount>,
) -> Option<ApiHttpResponse> {
    let (path, query) = split_http_target(target);
    if method != "POST" || path != WALLET_SEND_ROUTE {
        return None;
    }
    Some(local_wallet_send_http_response(
        service,
        query,
        chain_file,
        pending_file,
        alice_balance,
    ))
}

fn local_wallet_send_http_response(
    service: &XriqApiService,
    query: Option<&str>,
    chain_file: &str,
    pending_file: Option<&str>,
    alice_balance: Option<XriqAmount>,
) -> ApiHttpResponse {
    let Some(pending_file) = pending_file else {
        return local_api_error_response(
            400,
            "missing_pending_file",
            "accepted local wallet send requires --pending-file",
        );
    };
    let request = match LocalWalletSendRequest::from_query(service, query) {
        Ok(request) => request,
        Err(response) => return response,
    };
    if query_param(query, "dry_run") == Some("true") {
        return local_api_error_response(
            400,
            "dry_run_not_enabled",
            "dry_run is contract-only in this checkpoint and does not mutate state",
        );
    }

    let before_count = service.mempool(usize::MAX).pending_count;
    let body = render_local_wallet_send_transfer_body(service, &request);
    let detail = match private_devnet_file_submit_pending_transfer_body(
        chain_file,
        pending_file,
        alice_balance,
        &body,
    ) {
        Ok(detail) => detail,
        Err(error) => {
            return local_api_error_response(
                400,
                error.code(),
                &format!("local wallet send failed: {error}"),
            );
        }
    };

    render_local_wallet_send_accepted_response(
        service,
        &detail,
        LocalWalletSendRenderInput {
            local_request_id: request.local_request_id,
            chain_file,
            pending_file,
            before_count,
            after_count: before_count + 1,
        },
    )
}

#[derive(Debug, Clone, Copy)]
struct LocalWalletSendRequest<'a> {
    local_request_id: &'a str,
    from_address: &'a str,
    to_address: &'a str,
    amount: XriqAmount,
    fee: XriqAmount,
    nonce: u64,
    expires_at_height: u64,
}

impl<'a> LocalWalletSendRequest<'a> {
    fn from_query(
        service: &XriqApiService,
        query: Option<&'a str>,
    ) -> Result<Self, ApiHttpResponse> {
        let local_request_id = required_query_param_any(query, &["local_request_id"])
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        if !valid_local_request_id(local_request_id) {
            return Err(local_api_error_response(
                400,
                "invalid_local_request_id",
                "local_request_id must use letters, digits, dash, or underscore and be 1-64 characters",
            ));
        }
        let from_address = required_query_param_any(query, &["from_address", "from"])
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        if let Err(error) = validate_xriq_address(from_address, "from_address") {
            return Err(local_api_error_response(400, "bad_request", &error));
        }
        if from_address != PRIVATE_DEVNET_TEST_SENDER {
            return Err(local_api_error_response(
                400,
                "invalid_sender",
                "wallet send is limited to the configured private-devnet Alice test sender",
            ));
        }
        let to_address = required_query_param_any(query, &["to_address", "to"])
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        if let Err(error) = validate_xriq_address(to_address, "to_address") {
            return Err(local_api_error_response(400, "bad_request", &error));
        }
        if from_address == to_address {
            return Err(local_api_error_response(
                400,
                "self_transfer",
                "from_address and to_address must differ",
            ));
        }
        let amount_units = required_query_param_any(query, &["amount_base_units", "amount"])
            .and_then(|value| parse_u128_query(value, "amount_base_units"))
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        if amount_units == 0 {
            return Err(local_api_error_response(
                400,
                "zero_amount",
                "amount_base_units must be greater than zero",
            ));
        }
        let fee_units = required_query_param_any(query, &["fee_base_units", "fee"])
            .and_then(|value| parse_u128_query(value, "fee_base_units"))
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        if fee_units < PRIVATE_DEVNET_MIN_FEE_BASE_UNITS {
            return Err(local_api_error_response(
                400,
                "fee_too_low",
                "fee_base_units must satisfy the private-devnet minimum fee",
            ));
        }
        let nonce = required_query_param_any(query, &["nonce"])
            .and_then(|value| parse_u64_query(value, "nonce"))
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        let expires_at_height = required_query_param_any(query, &["expires_at_height"])
            .and_then(|value| parse_u64_query(value, "expires_at_height"))
            .map_err(|error| local_api_error_response(400, "bad_request", &error))?;
        if expires_at_height <= service.snapshot().current_height {
            return Err(local_api_error_response(
                400,
                "expired",
                "expires_at_height must be greater than current local height",
            ));
        }

        Ok(Self {
            local_request_id,
            from_address,
            to_address,
            amount: XriqAmount::from_base_units(amount_units),
            fee: XriqAmount::from_base_units(fee_units),
            nonce,
            expires_at_height,
        })
    }
}

fn render_local_wallet_send_transfer_body(
    service: &XriqApiService,
    request: &LocalWalletSendRequest<'_>,
) -> String {
    let mut body = String::new();
    writeln!(&mut body, "{{").expect("write to String");
    writeln!(
        &mut body,
        "  \"format_version\": \"xriq-node-transfer-submit-v1\","
    )
    .expect("write to String");
    writeln!(&mut body, "  \"version\": 1,").expect("write to String");
    writeln!(
        &mut body,
        "  \"chain_id\": {},",
        json_string(&service.snapshot().chain_id)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "  \"from\": {},",
        json_string(request.from_address)
    )
    .expect("write to String");
    writeln!(&mut body, "  \"to\": {},", json_string(request.to_address)).expect("write to String");
    writeln!(
        &mut body,
        "  \"amount_base_units\": {},",
        json_string(&request.amount.base_units().to_string())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "  \"fee_base_units\": {},",
        json_string(&request.fee.base_units().to_string())
    )
    .expect("write to String");
    writeln!(&mut body, "  \"nonce\": {},", request.nonce).expect("write to String");
    writeln!(
        &mut body,
        "  \"expires_at_height\": {}",
        request.expires_at_height
    )
    .expect("write to String");
    body.push('}');
    body
}

#[derive(Debug, Clone, Copy)]
struct LocalWalletSendRenderInput<'a> {
    local_request_id: &'a str,
    chain_file: &'a str,
    pending_file: &'a str,
    before_count: usize,
    after_count: usize,
}

fn render_local_wallet_send_accepted_response(
    service: &XriqApiService,
    detail: &PrivateDevnetPendingTransactionDetail,
    input: LocalWalletSendRenderInput<'_>,
) -> ApiHttpResponse {
    let tx = &detail.transaction;
    let tx_hash = hash_hex(detail.tx_hash);
    let expires_at_height = tx
        .expires_at_height
        .unwrap_or(service.snapshot().current_height + 1);
    let mut body = String::new();
    writeln!(&mut body, "{{").expect("write to String");
    writeln!(&mut body, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut body,
        "  \"network\": {},",
        json_string(&service.snapshot().chain_id)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "  \"endpoint\": {},",
        json_string(WALLET_SEND_ENDPOINT)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "  \"code\": {},",
        json_string(LOCAL_WALLET_SEND_ACCEPTED_CODE)
    )
    .expect("write to String");
    writeln!(&mut body, "  \"status\": \"pending\",").expect("write to String");
    writeln!(&mut body, "  \"mutation\": \"pending_state_only\",").expect("write to String");
    writeln!(&mut body, "  \"warning\": \"local-private-devnet-only\",").expect("write to String");
    writeln!(&mut body, "  \"transaction\": {{").expect("write to String");
    writeln!(&mut body, "    \"tx_hash\": {},", json_string(&tx_hash)).expect("write to String");
    writeln!(&mut body, "    \"status\": \"pending\",").expect("write to String");
    writeln!(
        &mut body,
        "    \"from_address\": {},",
        json_string(tx.from.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"to_address\": {},",
        json_string(tx.to.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"amount_base_units\": {},",
        json_string(&tx.amount.base_units().to_string())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"fee_base_units\": {},",
        json_string(&tx.fee.base_units().to_string())
    )
    .expect("write to String");
    writeln!(&mut body, "    \"nonce\": {},", tx.nonce).expect("write to String");
    writeln!(
        &mut body,
        "    \"expires_at_height\": {},",
        expires_at_height
    )
    .expect("write to String");
    writeln!(&mut body, "    \"block_height\": null,").expect("write to String");
    writeln!(&mut body, "    \"transaction_index\": null").expect("write to String");
    writeln!(&mut body, "  }},").expect("write to String");
    writeln!(&mut body, "  \"pending_state\": {{").expect("write to String");
    writeln!(&mut body, "    \"before_count\": {},", input.before_count).expect("write to String");
    writeln!(&mut body, "    \"after_count\": {},", input.after_count).expect("write to String");
    writeln!(
        &mut body,
        "    \"added_tx_hash\": {},",
        json_string(&tx_hash)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"pending_file\": {}",
        json_string(input.pending_file)
    )
    .expect("write to String");
    writeln!(&mut body, "  }},").expect("write to String");
    writeln!(&mut body, "  \"chain_state\": {{").expect("write to String");
    writeln!(
        &mut body,
        "    \"current_height\": {},",
        service.snapshot().current_height
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"latest_block_hash\": {},",
        json_string(&service.snapshot().latest_block_hash)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"chain_file\": {},",
        json_string(input.chain_file)
    )
    .expect("write to String");
    writeln!(&mut body, "    \"chain_unchanged\": true").expect("write to String");
    writeln!(&mut body, "  }},").expect("write to String");
    writeln!(&mut body, "  \"audit_event_recorded\": true,").expect("write to String");
    writeln!(&mut body, "  \"audit_event\": {{").expect("write to String");
    writeln!(
        &mut body,
        "    \"event_id\": {},",
        json_string(&format!("wallet-transfer-send:{}", input.local_request_id))
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"actor\": {},",
        json_string(LOCAL_REFUSAL_AUDIT_ACTOR)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"action\": {},",
        json_string(WALLET_SEND_AUDIT_ACTION)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"resource_type\": {},",
        json_string(WALLET_AUDIT_RESOURCE_TYPE)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"resource_id\": {},",
        json_string(WALLET_SEND_AUDIT_RESOURCE_ID)
    )
    .expect("write to String");
    writeln!(&mut body, "    \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(&mut body, "    \"metadata\": {{").expect("write to String");
    writeln!(
        &mut body,
        "      \"endpoint\": {},",
        json_string(WALLET_SEND_ENDPOINT)
    )
    .expect("write to String");
    writeln!(&mut body, "      \"outcome\": \"accepted\",").expect("write to String");
    writeln!(&mut body, "      \"status\": \"pending\",").expect("write to String");
    writeln!(
        &mut body,
        "      \"explicit_flag\": {},",
        json_string(ENABLE_LOCAL_WALLET_SEND_FLAG)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"local_request_id\": {},",
        json_string(input.local_request_id)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"from_address\": {},",
        json_string(tx.from.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"to_address\": {},",
        json_string(tx.to.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"amount_base_units\": {},",
        json_string(&tx.amount.base_units().to_string())
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"fee_base_units\": {},",
        json_string(&tx.fee.base_units().to_string())
    )
    .expect("write to String");
    writeln!(&mut body, "      \"nonce\": {},", tx.nonce).expect("write to String");
    writeln!(
        &mut body,
        "      \"expires_at_height\": {},",
        expires_at_height
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"pending_before_count\": {},",
        input.before_count
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"pending_after_count\": {},",
        input.after_count
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"added_tx_hash\": {},",
        json_string(&tx_hash)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"chain_current_height\": {},",
        service.snapshot().current_height
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"metadata_policy\": \"request fields and local pending-state transition summary only; no signing material or custody material\""
    )
    .expect("write to String");
    writeln!(&mut body, "    }}").expect("write to String");
    writeln!(&mut body, "  }}").expect("write to String");
    body.push('}');

    ApiHttpResponse {
        status_code: 201,
        reason: "Created",
        body,
    }
}

fn maybe_local_block_production_http_response(
    service: &XriqApiService,
    method: &str,
    target: &str,
    chain_file: &str,
    pending_file: Option<&str>,
    alice_balance: Option<XriqAmount>,
) -> Option<ApiHttpResponse> {
    let (path, query) = split_http_target(target);
    if method != "POST" || path != BLOCK_PRODUCTION_ROUTE {
        return None;
    }
    Some(local_block_production_http_response(
        service,
        query,
        chain_file,
        pending_file,
        alice_balance,
    ))
}

fn local_block_production_http_response(
    service: &XriqApiService,
    query: Option<&str>,
    chain_file: &str,
    pending_file: Option<&str>,
    alice_balance: Option<XriqAmount>,
) -> ApiHttpResponse {
    let Some(pending_file) = pending_file else {
        return local_api_error_response(
            400,
            "missing_pending_file",
            "accepted local block production requires --pending-file",
        );
    };
    let local_request_id = match required_query_param_any(query, &["local_request_id"]) {
        Ok(value) => value,
        Err(error) => return local_api_error_response(400, "bad_request", &error),
    };
    if !valid_local_request_id(local_request_id) {
        return local_api_error_response(
            400,
            "invalid_local_request_id",
            "local_request_id must use letters, digits, dash, or underscore and be 1-64 characters",
        );
    }
    let producer = match required_query_param_any(query, &["producer"]) {
        Ok(value) => value,
        Err(error) => return local_api_error_response(400, "bad_request", &error),
    };
    if let Err(error) = validate_xriq_address(producer, "producer") {
        return local_api_error_response(400, "bad_request", &error);
    }
    if producer != PRIVATE_DEVNET_PRODUCER {
        return local_api_error_response(
            400,
            "invalid_producer",
            "producer must be the configured private-devnet test authority",
        );
    }
    let max_transactions = match required_query_param_any(query, &["max_transactions"])
        .and_then(|value| parse_u64_query(value, "max_transactions"))
    {
        Ok(value) => value,
        Err(error) => return local_api_error_response(400, "bad_request", &error),
    };
    if max_transactions != PRIVATE_DEVNET_MAX_TRANSACTIONS_PER_BLOCK as u64 {
        return local_api_error_response(
            400,
            "invalid_max_transactions",
            "max_transactions must match the private-devnet block transaction limit",
        );
    }
    let timestamp_ms = match required_query_param_any(query, &["timestamp_ms"])
        .and_then(|value| parse_u64_query(value, "timestamp_ms"))
    {
        Ok(value) => value,
        Err(error) => return local_api_error_response(400, "bad_request", &error),
    };
    let consensus_round = match query_param(query, "consensus_round")
        .map(|value| parse_u64_query(value, "consensus_round"))
        .transpose()
    {
        Ok(value) => value.unwrap_or(0),
        Err(error) => return local_api_error_response(400, "bad_request", &error),
    };
    if query_param(query, "dry_run") == Some("true") {
        return local_api_error_response(
            400,
            "dry_run_not_enabled",
            "dry_run is contract-only in this checkpoint and does not mutate state",
        );
    }
    let before_count = service.mempool(usize::MAX).pending_count;
    if before_count == 0 {
        return local_api_error_response(
            400,
            "no_pending_transactions",
            "local block production requires at least one pending transaction",
        );
    }

    let produced = match private_devnet_file_produce_pending_block(
        chain_file,
        pending_file,
        alice_balance,
        timestamp_ms,
        consensus_round,
    ) {
        Ok(status) => status,
        Err(error) => {
            return local_api_error_response(
                400,
                error.code(),
                &format!("local block production failed: {error}"),
            );
        }
    };
    let store = match FileChainStore::open(chain_file) {
        Ok(store) => store,
        Err(error) => {
            return local_api_error_response(
                503,
                "chain_file_read_failed",
                &format!("could not reopen chain file after block production: {error:?}"),
            );
        }
    };
    let Some(latest_block) = store.latest_block() else {
        return local_api_error_response(
            503,
            "produced_block_missing",
            "chain file did not contain a latest block after block production",
        );
    };
    let after_count = produced.status.pending_transactions;
    render_local_block_production_accepted_response(
        service,
        &produced,
        latest_block,
        LocalBlockProductionRenderInput {
            local_request_id,
            producer,
            chain_file,
            pending_file,
            max_transactions,
            timestamp_ms,
            before_count,
            after_count,
        },
    )
}

#[derive(Debug, Clone, Copy)]
struct LocalBlockProductionRenderInput<'a> {
    local_request_id: &'a str,
    producer: &'a str,
    chain_file: &'a str,
    pending_file: &'a str,
    max_transactions: u64,
    timestamp_ms: u64,
    before_count: usize,
    after_count: usize,
}

fn render_local_block_production_accepted_response(
    service: &XriqApiService,
    produced: &ProducedPendingBlockStatus,
    latest_block: &xriq_storage::StoredBlock,
    input: LocalBlockProductionRenderInput<'_>,
) -> ApiHttpResponse {
    let block = &latest_block.block;
    let block_hash = hash_hex(latest_block.block_hash);
    let previous_height = service.snapshot().current_height;
    let mut body = String::new();
    writeln!(&mut body, "{{").expect("write to String");
    writeln!(&mut body, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut body,
        "  \"network\": {},",
        json_string(&service.snapshot().chain_id)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "  \"endpoint\": {},",
        json_string("POST /api/v1/blocks/produce")
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "  \"code\": {},",
        json_string(LOCAL_BLOCK_PRODUCTION_ACCEPTED_CODE)
    )
    .expect("write to String");
    writeln!(&mut body, "  \"status\": \"confirmed\",").expect("write to String");
    writeln!(
        &mut body,
        "  \"mutation\": \"chain_and_pending_state_local_only\","
    )
    .expect("write to String");
    writeln!(&mut body, "  \"warning\": \"local-private-devnet-only\",").expect("write to String");
    writeln!(&mut body, "  \"block\": {{").expect("write to String");
    writeln!(&mut body, "    \"height\": {},", block.header.height).expect("write to String");
    writeln!(
        &mut body,
        "    \"block_hash\": {},",
        json_string(&block_hash)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"previous_block_hash\": {},",
        json_string(&hash_hex(block.header.previous_block_hash))
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"state_root\": {},",
        json_string(&hash_hex(block.header.state_root))
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"transactions_root\": {},",
        json_string(&hash_hex(block.header.transactions_root))
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"transaction_count\": {},",
        block.transactions.len()
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"timestamp_utc\": {}",
        json_string(&timestamp_ms_to_utc(block.header.timestamp_ms))
    )
    .expect("write to String");
    writeln!(&mut body, "  }},").expect("write to String");
    writeln!(&mut body, "  \"confirmed_transactions\": [").expect("write to String");
    for (index, transaction) in block.transactions.iter().enumerate() {
        let tx_hash = hash_hex(transaction_hash(transaction));
        writeln!(&mut body, "    {{").expect("write to String");
        writeln!(&mut body, "      \"tx_hash\": {},", json_string(&tx_hash))
            .expect("write to String");
        writeln!(&mut body, "      \"status\": \"confirmed\",").expect("write to String");
        writeln!(
            &mut body,
            "      \"block_height\": {},",
            block.header.height
        )
        .expect("write to String");
        writeln!(
            &mut body,
            "      \"block_hash\": {},",
            json_string(&block_hash)
        )
        .expect("write to String");
        writeln!(&mut body, "      \"transaction_index\": {}", index).expect("write to String");
        let trailing = if index + 1 == block.transactions.len() {
            ""
        } else {
            ","
        };
        writeln!(&mut body, "    }}{trailing}").expect("write to String");
    }
    writeln!(&mut body, "  ],").expect("write to String");
    writeln!(&mut body, "  \"pending_state\": {{").expect("write to String");
    writeln!(&mut body, "    \"before_count\": {},", input.before_count).expect("write to String");
    writeln!(&mut body, "    \"after_count\": {},", input.after_count).expect("write to String");
    writeln!(&mut body, "    \"removed_tx_hashes\": [").expect("write to String");
    for (index, tx_hash) in produced.included_transaction_hashes.iter().enumerate() {
        let trailing = if index + 1 == produced.included_transaction_hashes.len() {
            ""
        } else {
            ","
        };
        writeln!(
            &mut body,
            "      {}{}",
            json_string(&hash_hex(*tx_hash)),
            trailing
        )
        .expect("write to String");
    }
    writeln!(&mut body, "    ],").expect("write to String");
    writeln!(
        &mut body,
        "    \"pending_file\": {}",
        json_string(input.pending_file)
    )
    .expect("write to String");
    writeln!(&mut body, "  }},").expect("write to String");
    writeln!(&mut body, "  \"chain_state\": {{").expect("write to String");
    writeln!(&mut body, "    \"previous_height\": {},", previous_height).expect("write to String");
    writeln!(
        &mut body,
        "    \"current_height\": {},",
        produced.status.current_height
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"chain_file\": {}",
        json_string(input.chain_file)
    )
    .expect("write to String");
    writeln!(&mut body, "  }},").expect("write to String");
    writeln!(
        &mut body,
        "  \"audit_scope\": {},",
        json_string(LOCAL_BLOCK_PRODUCTION_AUDIT_SCOPE)
    )
    .expect("write to String");
    writeln!(&mut body, "  \"audit_event_recorded\": true,").expect("write to String");
    writeln!(&mut body, "  \"audit_event\": {{").expect("write to String");
    writeln!(
        &mut body,
        "    \"event_id\": {},",
        json_string(&format!("block-production:{}", input.local_request_id))
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "    \"actor\": \"local-private-devnet-operator\","
    )
    .expect("write to String");
    writeln!(&mut body, "    \"action\": \"block_production_attempt\",").expect("write to String");
    writeln!(&mut body, "    \"resource_type\": \"block_production\",").expect("write to String");
    writeln!(
        &mut body,
        "    \"resource_id\": {},",
        json_string(input.local_request_id)
    )
    .expect("write to String");
    writeln!(&mut body, "    \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(&mut body, "    \"metadata\": {{").expect("write to String");
    writeln!(
        &mut body,
        "      \"endpoint\": {},",
        json_string("POST /api/v1/blocks/produce")
    )
    .expect("write to String");
    writeln!(&mut body, "      \"outcome\": \"accepted\",").expect("write to String");
    writeln!(&mut body, "      \"status\": \"confirmed\",").expect("write to String");
    writeln!(
        &mut body,
        "      \"explicit_flag\": {},",
        json_string(ENABLE_LOCAL_BLOCK_PRODUCTION_FLAG)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"local_request_id\": {},",
        json_string(input.local_request_id)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"producer\": {},",
        json_string(input.producer)
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"max_transactions\": {},",
        input.max_transactions
    )
    .expect("write to String");
    writeln!(&mut body, "      \"timestamp_ms\": {},", input.timestamp_ms)
        .expect("write to String");
    writeln!(
        &mut body,
        "      \"pending_before_count\": {},",
        input.before_count
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"pending_after_count\": {},",
        input.after_count
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"confirmed_transaction_count\": {},",
        produced.applied_transactions
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"chain_previous_height\": {},",
        previous_height
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"chain_current_height\": {},",
        produced.status.current_height
    )
    .expect("write to String");
    writeln!(
        &mut body,
        "      \"metadata_policy\": \"request fields and local state transition summary only; no signing material\""
    )
    .expect("write to String");
    writeln!(&mut body, "    }}").expect("write to String");
    writeln!(&mut body, "  }}").expect("write to String");
    body.push('}');

    ApiHttpResponse {
        status_code: 201,
        reason: "Created",
        body,
    }
}

fn valid_local_request_id(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 64
        && value
            .chars()
            .all(|character| character.is_ascii_alphanumeric() || matches!(character, '-' | '_'))
}

fn parse_http_request_line(line: &str) -> Result<(&str, &str), String> {
    let mut parts = line.split_whitespace();
    let method = parts
        .next()
        .ok_or_else(|| "missing HTTP method".to_string())?;
    let target = parts
        .next()
        .ok_or_else(|| "missing HTTP target".to_string())?;
    let version = parts
        .next()
        .ok_or_else(|| "missing HTTP version".to_string())?;
    if parts.next().is_some() {
        return Err("too many values in HTTP request line".to_string());
    }
    if !version.starts_with("HTTP/") {
        return Err(format!("unsupported HTTP version marker: {version}"));
    }
    Ok((method, target))
}

fn bad_request_response(message: &str) -> ApiHttpResponse {
    ApiHttpResponse {
        status_code: 400,
        reason: "Bad Request",
        body: format!(
            "{{\n  \"error\": {{\n    \"code\": \"bad_request\",\n    \"message\": {}\n  }}\n}}",
            json_string(message)
        ),
    }
}

fn cli_response(response: ApiHttpResponse) -> String {
    format!(
        "status_code={}\nreason={}\nbody={}",
        response.status_code, response.reason, response.body
    )
}

fn postgres_account_history_address_from_path(path: &str) -> Option<&str> {
    let account_path = path.strip_prefix(POSTGRES_ACCOUNT_DETAIL_PREFIX)?;
    let address = account_path.strip_suffix(POSTGRES_ACCOUNT_HISTORY_SUFFIX)?;
    (!address.is_empty() && !address.contains('/')).then_some(address)
}

fn postgres_wallet_account_history_address_from_path(path: &str) -> Option<&str> {
    let account_path = path.strip_prefix(POSTGRES_WALLET_ACCOUNT_PREFIX)?;
    let address = account_path.strip_suffix(POSTGRES_WALLET_ACCOUNT_HISTORY_SUFFIX)?;
    (!address.is_empty() && !address.contains('/')).then_some(address)
}

fn postgres_wallet_account_balance_address_from_path(path: &str) -> Option<&str> {
    let account_path = path.strip_prefix(POSTGRES_WALLET_ACCOUNT_PREFIX)?;
    let address = account_path.strip_suffix(POSTGRES_WALLET_ACCOUNT_BALANCE_SUFFIX)?;
    (!address.is_empty() && !address.contains('/')).then_some(address)
}

fn postgres_wallet_transaction_status_hash_from_path(path: &str) -> Option<&str> {
    let tx_path = path.strip_prefix(POSTGRES_WALLET_TRANSACTION_PREFIX)?;
    let tx_hash = tx_path.strip_suffix(POSTGRES_WALLET_TRANSACTION_STATUS_SUFFIX)?;
    (!tx_hash.is_empty() && !tx_hash.contains('/')).then_some(tx_hash)
}

fn postgres_iso20022_transaction_status_hash_from_path(path: &str) -> Option<&str> {
    let tx_path = path.strip_prefix(POSTGRES_ISO20022_TRANSACTION_PREFIX)?;
    let tx_hash = tx_path.strip_suffix(POSTGRES_WALLET_TRANSACTION_STATUS_SUFFIX)?;
    (!tx_hash.is_empty() && !tx_hash.contains('/')).then_some(tx_hash)
}

fn postgres_iso20022_account_statement_address_from_path(path: &str) -> Option<&str> {
    let account_path = path.strip_prefix(POSTGRES_ISO20022_ACCOUNT_PREFIX)?;
    let address = account_path.strip_suffix(POSTGRES_ISO20022_ACCOUNT_STATEMENT_SUFFIX)?;
    (!address.is_empty() && !address.contains('/')).then_some(address)
}

fn postgres_snapshot_name_from_path(path: &str) -> Option<&str> {
    let snapshot_name = path.strip_prefix(POSTGRES_SNAPSHOT_DETAIL_PREFIX)?;
    (!snapshot_name.is_empty() && !snapshot_name.contains('/')).then_some(snapshot_name)
}

fn postgres_block_identifier_from_path(path: &str) -> Option<&str> {
    let identifier = path.strip_prefix(POSTGRES_BLOCK_DETAIL_PREFIX)?;
    (!identifier.is_empty() && !identifier.contains('/')).then_some(identifier)
}

fn maybe_postgres_read_model_http_response(
    config: Option<&PostgresReadModelConfig<'_>>,
    method: &str,
    target: &str,
) -> Option<Result<ApiHttpResponse, String>> {
    let path = target.split('?').next().unwrap_or(target);
    let is_transaction_detail = path
        .strip_prefix(POSTGRES_TRANSACTION_DETAIL_PREFIX)
        .is_some_and(|tx_hash| !tx_hash.is_empty());
    let is_wallet_transaction_status =
        postgres_wallet_transaction_status_hash_from_path(path).is_some();
    let is_iso20022_transaction_status =
        postgres_iso20022_transaction_status_hash_from_path(path).is_some();
    let is_iso20022_account_statement =
        postgres_iso20022_account_statement_address_from_path(path).is_some();
    let is_account_detail = path
        .strip_prefix(POSTGRES_ACCOUNT_DETAIL_PREFIX)
        .is_some_and(|address| !address.is_empty() && !address.contains('/'));
    let is_account_history = postgres_account_history_address_from_path(path).is_some();
    let is_wallet_account_balance =
        postgres_wallet_account_balance_address_from_path(path).is_some();
    let is_wallet_account_history =
        postgres_wallet_account_history_address_from_path(path).is_some();
    let is_snapshot_detail = postgres_snapshot_name_from_path(path).is_some();
    let is_block_detail = postgres_block_identifier_from_path(path).is_some();
    match (path, config) {
        (POSTGRES_READ_MODEL_STATUS_ROUTE, None) => {
            return Some(Ok(postgres_read_model_disabled_response()));
        }
        (
            POSTGRES_EXPLORER_OVERVIEW_ROUTE
            | POSTGRES_NODE_STATUS_ROUTE
            | POSTGRES_INDEXER_STATUS_ROUTE
            | POSTGRES_AUDIT_EVENTS_ROUTE
            | POSTGRES_BLOCKS_ROUTE
            | POSTGRES_TRANSACTIONS_ROUTE
            | POSTGRES_MEMPOOL_ROUTE
            | POSTGRES_WALLET_STATUS_ROUTE
            | POSTGRES_WALLET_DRAFT_PREVIEW_ROUTE
            | POSTGRES_ISO20022_PAYMENT_INITIATION_PREVIEW_ROUTE
            | POSTGRES_ACCOUNTS_ROUTE
            | POSTGRES_WALLET_ACCOUNTS_ROUTE
            | POSTGRES_SNAPSHOTS_ROUTE,
            None,
        ) => return None,
        (_, None) if is_transaction_detail => return None,
        (_, None) if is_wallet_transaction_status => return None,
        (_, None) if is_iso20022_transaction_status => return None,
        (_, None) if is_iso20022_account_statement => return None,
        (_, None) if is_account_history => return None,
        (_, None) if is_wallet_account_balance => return None,
        (_, None) if is_wallet_account_history => return None,
        (_, None) if is_account_detail => return None,
        (_, None) if is_snapshot_detail => return None,
        (_, None) if is_block_detail => return None,
        (
            POSTGRES_READ_MODEL_STATUS_ROUTE
            | POSTGRES_NODE_STATUS_ROUTE
            | POSTGRES_INDEXER_STATUS_ROUTE
            | POSTGRES_AUDIT_EVENTS_ROUTE
            | POSTGRES_EXPLORER_OVERVIEW_ROUTE
            | POSTGRES_BLOCKS_ROUTE
            | POSTGRES_TRANSACTIONS_ROUTE
            | POSTGRES_MEMPOOL_ROUTE
            | POSTGRES_WALLET_STATUS_ROUTE
            | POSTGRES_WALLET_DRAFT_PREVIEW_ROUTE
            | POSTGRES_ISO20022_PAYMENT_INITIATION_PREVIEW_ROUTE
            | POSTGRES_ACCOUNTS_ROUTE
            | POSTGRES_WALLET_ACCOUNTS_ROUTE
            | POSTGRES_SNAPSHOTS_ROUTE,
            Some(config),
        ) => return Some(postgres_read_model_http_response(config, method, target)),
        _ => {}
    };
    if let (true, Some(config)) = (is_transaction_detail, config) {
        return Some(postgres_read_model_http_response(config, method, target));
    }
    if let (true, Some(config)) = (is_wallet_transaction_status, config) {
        return Some(postgres_read_model_http_response(config, method, target));
    }
    if let (true, Some(config)) = (is_iso20022_transaction_status, config) {
        return Some(postgres_read_model_http_response(config, method, target));
    }
    if let (true, Some(config)) = (is_iso20022_account_statement, config) {
        return Some(postgres_read_model_http_response(config, method, target));
    }
    if let (true, Some(config)) = (is_account_history, config) {
        return Some(postgres_read_model_http_response(config, method, target));
    }
    if let (true, Some(config)) = (is_wallet_account_balance, config) {
        return Some(postgres_read_model_http_response(config, method, target));
    }
    if let (true, Some(config)) = (is_wallet_account_history, config) {
        return Some(postgres_read_model_http_response(config, method, target));
    }
    if let (true, Some(config)) = (is_account_detail, config) {
        return Some(postgres_read_model_http_response(config, method, target));
    }
    if let (true, Some(config)) = (is_snapshot_detail, config) {
        return Some(postgres_read_model_http_response(config, method, target));
    }
    if let (true, Some(config)) = (is_block_detail, config) {
        return Some(postgres_read_model_http_response(config, method, target));
    }
    None
}

fn postgres_read_model_http_response(
    config: &PostgresReadModelConfig<'_>,
    method: &str,
    target: &str,
) -> Result<ApiHttpResponse, String> {
    if method != "GET" {
        return Ok(local_api_error_response(
            405,
            "method_not_allowed",
            "XRIQ Postgres read-model API scaffold currently supports GET only",
        ));
    }

    let path = target.split('?').next().unwrap_or(target);
    let transaction_detail_tx_hash = path
        .strip_prefix(POSTGRES_TRANSACTION_DETAIL_PREFIX)
        .filter(|tx_hash| !tx_hash.is_empty());
    let wallet_transaction_status_hash = postgres_wallet_transaction_status_hash_from_path(path);
    let iso20022_transaction_status_hash =
        postgres_iso20022_transaction_status_hash_from_path(path);
    let iso20022_account_statement_address =
        postgres_iso20022_account_statement_address_from_path(path);
    let account_detail_address = path
        .strip_prefix(POSTGRES_ACCOUNT_DETAIL_PREFIX)
        .filter(|address| !address.is_empty() && !address.contains('/'));
    let account_history_address = postgres_account_history_address_from_path(path);
    let wallet_account_balance_address = postgres_wallet_account_balance_address_from_path(path);
    let wallet_account_history_address = postgres_wallet_account_history_address_from_path(path);
    let snapshot_detail_name = postgres_snapshot_name_from_path(path);
    let block_detail_identifier = postgres_block_identifier_from_path(path);
    let (sql, label, renderer): (String, &str, PostgresReadModelRenderer) = if let Some(tx_hash) =
        transaction_detail_tx_hash
    {
        match postgres_transaction_detail_sql(tx_hash) {
            Ok(sql) => (
                sql,
                "postgres transaction detail",
                render_postgres_transaction_detail_json,
            ),
            Err(message) => {
                return Ok(local_api_error_response(400, "bad_request", &message));
            }
        }
    } else if let Some(tx_hash) = wallet_transaction_status_hash {
        match postgres_wallet_transaction_status_sql(tx_hash) {
            Ok(sql) => (
                sql,
                "postgres wallet transaction status",
                render_postgres_wallet_transaction_status_json,
            ),
            Err(message) => {
                return Ok(local_api_error_response(400, "bad_request", &message));
            }
        }
    } else if let Some(tx_hash) = iso20022_transaction_status_hash {
        match postgres_iso20022_transaction_status_sql(tx_hash) {
            Ok(sql) => (
                sql,
                "postgres iso20022 transaction status",
                render_postgres_iso20022_transaction_status_json,
            ),
            Err(message) => {
                return Ok(local_api_error_response(400, "bad_request", &message));
            }
        }
    } else if let Some(address) = iso20022_account_statement_address {
        match postgres_iso20022_account_statement_sql(address, target) {
            Ok(sql) => (
                sql,
                "postgres iso20022 account statement",
                render_postgres_iso20022_account_statement_json,
            ),
            Err(message) => {
                return Ok(local_api_error_response(400, "bad_request", &message));
            }
        }
    } else if let Some(address) = wallet_account_balance_address {
        match postgres_account_detail_sql(address) {
            Ok(sql) => (
                sql,
                "postgres wallet account balance",
                render_postgres_wallet_balance_json,
            ),
            Err(message) => {
                return Ok(local_api_error_response(400, "bad_request", &message));
            }
        }
    } else if let Some(address) = wallet_account_history_address {
        match postgres_account_history_sql(address, target) {
            Ok(sql) => (
                sql,
                "postgres wallet account history",
                render_postgres_account_history_json,
            ),
            Err(message) => {
                return Ok(local_api_error_response(400, "bad_request", &message));
            }
        }
    } else if let Some(address) = account_history_address {
        match postgres_account_history_sql(address, target) {
            Ok(sql) => (
                sql,
                "postgres account history",
                render_postgres_account_history_json,
            ),
            Err(message) => {
                return Ok(local_api_error_response(400, "bad_request", &message));
            }
        }
    } else if let Some(address) = account_detail_address {
        match postgres_account_detail_sql(address) {
            Ok(sql) => (
                sql,
                "postgres account detail",
                render_postgres_account_detail_json,
            ),
            Err(message) => {
                return Ok(local_api_error_response(400, "bad_request", &message));
            }
        }
    } else if let Some(snapshot_name) = snapshot_detail_name {
        match postgres_snapshot_detail_sql(snapshot_name) {
            Ok(sql) => (
                sql,
                "postgres snapshot detail",
                render_postgres_snapshot_detail_json,
            ),
            Err(message) => {
                return Ok(local_api_error_response(400, "bad_request", &message));
            }
        }
    } else if let Some(identifier) = block_detail_identifier {
        match postgres_block_detail_sql(identifier) {
            Ok(sql) => (
                sql,
                "postgres block detail",
                render_postgres_block_detail_json,
            ),
            Err(message) => {
                return Ok(local_api_error_response(400, "bad_request", &message));
            }
        }
    } else {
        match path {
            POSTGRES_READ_MODEL_STATUS_ROUTE => (
                postgres_read_model_status_sql().to_string(),
                "postgres read-model status",
                render_postgres_read_model_status_json,
            ),
            POSTGRES_NODE_STATUS_ROUTE => (
                postgres_node_status_sql().to_string(),
                "postgres node status",
                render_postgres_node_status_json,
            ),
            POSTGRES_INDEXER_STATUS_ROUTE => (
                postgres_indexer_status_sql().to_string(),
                "postgres indexer status",
                render_postgres_indexer_status_json,
            ),
            POSTGRES_EXPLORER_OVERVIEW_ROUTE => (
                postgres_explorer_overview_sql().to_string(),
                "postgres explorer overview",
                render_postgres_explorer_overview_json,
            ),
            POSTGRES_AUDIT_EVENTS_ROUTE => match postgres_audit_events_sql(target) {
                Ok(sql) => (
                    sql,
                    "postgres audit events",
                    render_postgres_audit_events_json,
                ),
                Err(message) => return Ok(local_api_error_response(400, "bad_request", &message)),
            },
            POSTGRES_BLOCKS_ROUTE => match postgres_blocks_sql(target) {
                Ok(sql) => (sql, "postgres blocks", render_postgres_blocks_json),
                Err(message) => return Ok(local_api_error_response(400, "bad_request", &message)),
            },
            POSTGRES_TRANSACTIONS_ROUTE => match postgres_transactions_sql(target) {
                Ok(sql) => (
                    sql,
                    "postgres transactions",
                    render_postgres_transactions_json,
                ),
                Err(message) => return Ok(local_api_error_response(400, "bad_request", &message)),
            },
            POSTGRES_MEMPOOL_ROUTE => match postgres_mempool_sql(target) {
                Ok(sql) => (sql, "postgres mempool", render_postgres_mempool_json),
                Err(message) => return Ok(local_api_error_response(400, "bad_request", &message)),
            },
            POSTGRES_WALLET_STATUS_ROUTE => (
                postgres_wallet_status_sql().to_string(),
                "postgres wallet status",
                render_postgres_wallet_status_json,
            ),
            POSTGRES_WALLET_DRAFT_PREVIEW_ROUTE => {
                match postgres_wallet_draft_preview_sql(target) {
                    Ok(sql) => (
                        sql,
                        "postgres wallet draft preview",
                        render_postgres_wallet_draft_preview_json,
                    ),
                    Err(message) => {
                        return Ok(local_api_error_response(400, "bad_request", &message))
                    }
                }
            }
            POSTGRES_ISO20022_PAYMENT_INITIATION_PREVIEW_ROUTE => {
                match postgres_iso20022_payment_initiation_preview_sql(target) {
                    Ok(sql) => (
                        sql,
                        "postgres iso20022 payment initiation preview",
                        render_postgres_iso20022_payment_initiation_preview_json,
                    ),
                    Err(message) => {
                        return Ok(local_api_error_response(400, "bad_request", &message))
                    }
                }
            }
            POSTGRES_ACCOUNTS_ROUTE => match postgres_accounts_sql(target) {
                Ok(sql) => (sql, "postgres accounts", render_postgres_accounts_json),
                Err(message) => return Ok(local_api_error_response(400, "bad_request", &message)),
            },
            POSTGRES_WALLET_ACCOUNTS_ROUTE => match postgres_accounts_sql(target) {
                Ok(sql) => (
                    sql,
                    "postgres wallet accounts",
                    render_postgres_accounts_json,
                ),
                Err(message) => return Ok(local_api_error_response(400, "bad_request", &message)),
            },
            POSTGRES_SNAPSHOTS_ROUTE => match postgres_snapshots_sql(target) {
                Ok(sql) => (sql, "postgres snapshots", render_postgres_snapshots_json),
                Err(message) => return Ok(local_api_error_response(400, "bad_request", &message)),
            },
            _ => {
                return Ok(local_api_error_response(
                    404,
                    "not_found",
                    "XRIQ Postgres read-model endpoint not found",
                ));
            }
        }
    };

    let output = docker_psql_query(config.docker_container, config.database, &sql, label)?;
    let values = parse_key_value_lines(&output, label)?;
    if matches!(
        label,
        "postgres transaction detail"
            | "postgres wallet transaction status"
            | "postgres iso20022 transaction status"
            | "postgres iso20022 payment initiation preview"
            | "postgres iso20022 account statement"
    ) && values.get("found").map(String::as_str) != Some("true")
    {
        return Ok(local_api_error_response(
            404,
            "not_found",
            "XRIQ transaction not found in Postgres read model",
        ));
    }
    if matches!(
        label,
        "postgres account detail" | "postgres wallet account balance"
    ) && values.get("found").map(String::as_str) != Some("true")
    {
        return Ok(local_api_error_response(
            404,
            "not_found",
            "XRIQ account not found in Postgres read model",
        ));
    }
    if label == "postgres snapshot detail"
        && values.get("found").map(String::as_str) != Some("true")
    {
        return Ok(local_api_error_response(
            404,
            "not_found",
            "XRIQ snapshot not found in Postgres read model",
        ));
    }
    if label == "postgres block detail" && values.get("found").map(String::as_str) != Some("true") {
        return Ok(local_api_error_response(
            404,
            "not_found",
            "XRIQ block not found in Postgres read model",
        ));
    }
    let body = renderer(config, &values)?;
    Ok(ApiHttpResponse {
        status_code: 200,
        reason: "OK",
        body,
    })
}

fn postgres_read_model_disabled_response() -> ApiHttpResponse {
    local_api_error_response(
        404,
        "not_found",
        "XRIQ Postgres read-model endpoint is disabled; restart serve-readonly with --postgres-docker-container and --postgres-database to enable it",
    )
}

fn local_api_error_response(status_code: u16, code: &str, message: &str) -> ApiHttpResponse {
    let reason = match status_code {
        400 => "Bad Request",
        404 => "Not Found",
        405 => "Method Not Allowed",
        503 => "Service Unavailable",
        _ => "Error",
    };
    ApiHttpResponse {
        status_code,
        reason,
        body: format!(
            "{{\n  \"error\": {{\n    \"code\": {},\n    \"message\": {}\n  }}\n}}",
            json_string(code),
            json_string(message)
        ),
    }
}

fn docker_psql_query(
    container: &str,
    database: &str,
    sql: &str,
    label: &str,
) -> Result<String, String> {
    validate_docker_name(container, "docker container")?;
    validate_postgres_identifier(database, "postgres database")?;
    let mut child = Command::new("docker")
        .arg("exec")
        .arg("-i")
        .arg(container)
        .arg("psql")
        .arg("-U")
        .arg("xriq")
        .arg("-d")
        .arg(database)
        .arg("-v")
        .arg("ON_ERROR_STOP=1")
        .arg("-t")
        .arg("-A")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| format!("could not start docker psql for {label}: {error}"))?;
    child
        .stdin
        .take()
        .ok_or_else(|| format!("could not open docker psql stdin for {label}"))?
        .write_all(sql.as_bytes())
        .map_err(|error| format!("could not send {label} SQL to docker psql: {error}"))?;
    let output = child
        .wait_with_output()
        .map_err(|error| format!("could not wait for docker psql {label}: {error}"))?;
    if output.status.success() {
        return Ok(String::from_utf8_lossy(&output.stdout).to_string());
    }

    let stderr = String::from_utf8_lossy(&output.stderr);
    Err(format!(
        "docker psql failed while reading {label}: {stderr}"
    ))
}

fn postgres_read_model_status_sql() -> &'static str {
    "\
SELECT 'blocks=' || count(*) FROM xriq_blocks;\n\
SELECT 'transactions=' || count(*) FROM xriq_transactions;\n\
SELECT 'accounts=' || count(*) FROM xriq_accounts;\n\
SELECT 'account_balances=' || count(*) FROM xriq_account_balances;\n\
SELECT 'account_transactions=' || count(*) FROM xriq_account_transactions;\n\
SELECT 'mempool_entries=' || count(*) FROM xriq_mempool_entries;\n\
SELECT 'audit_events=' || count(*) FROM xriq_audit_events;\n\
SELECT 'indexer_runs=' || count(*) FROM xriq_indexer_runs;\n\
SELECT 'latest_height=' || COALESCE(MAX(height)::text, 'none') FROM xriq_blocks;\n\
SELECT 'latest_block_hash=' || COALESCE((SELECT block_hash FROM xriq_blocks ORDER BY height DESC LIMIT 1), 'none');\n\
SELECT 'indexer_status=' || COALESCE((SELECT status FROM xriq_indexer_runs ORDER BY completed_at DESC NULLS LAST, started_at DESC LIMIT 1), 'unknown');\n"
}

fn postgres_node_status_sql() -> &'static str {
    r#"
WITH latest_block AS (
    SELECT height, block_hash, state_root
    FROM xriq_blocks
    ORDER BY height DESC
    LIMIT 1
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'current_height' AS key, COALESCE((SELECT height::text FROM latest_block), '0') AS value
    UNION ALL
    SELECT 1, 'latest_block_hash', COALESCE((SELECT block_hash FROM latest_block), 'none')
    UNION ALL
    SELECT 2, 'state_root', COALESCE((SELECT state_root FROM latest_block), 'none')
    UNION ALL
    SELECT 3, 'stored_blocks', count(*)::text FROM xriq_blocks
    UNION ALL
    SELECT 4, 'pending_transactions', count(*)::text FROM xriq_mempool_entries
) AS rows
ORDER BY sort_order;
"#
}

fn postgres_indexer_status_sql() -> &'static str {
    r#"
WITH latest_run AS (
    SELECT run_id, status, from_height, to_height, blocks_indexed, transactions_indexed
    FROM xriq_indexer_runs
    ORDER BY completed_at DESC NULLS LAST, started_at DESC
    LIMIT 1
),
latest_block AS (
    SELECT height, block_hash
    FROM xriq_blocks
    ORDER BY height DESC
    LIMIT 1
)
SELECT key || '=' || value
FROM (
    SELECT
        0 AS sort_order,
        'status' AS key,
        CASE
            WHEN COALESCE((SELECT status FROM latest_run), 'unknown') = 'completed'
            THEN 'current'
            ELSE COALESCE((SELECT status FROM latest_run), 'unknown')
        END AS value
    UNION ALL
    SELECT 1, 'latest_indexed_height', COALESCE((SELECT height::text FROM latest_block), '0')
    UNION ALL
    SELECT 2, 'latest_indexed_block_hash', COALESCE((SELECT block_hash FROM latest_block), 'none')
    UNION ALL
    SELECT 3, 'lag_blocks', '0'
    UNION ALL
    SELECT 4, 'last_run_id', COALESCE((SELECT run_id FROM latest_run), 'none')
    UNION ALL
    SELECT 5, 'last_run_status', COALESCE((SELECT status FROM latest_run), 'unknown')
    UNION ALL
    SELECT 6, 'last_run_from_height', COALESCE((SELECT from_height::text FROM latest_run), 'none')
    UNION ALL
    SELECT 7, 'last_run_to_height', COALESCE((SELECT to_height::text FROM latest_run), 'none')
    UNION ALL
    SELECT 8, 'last_run_blocks_indexed', COALESCE((SELECT blocks_indexed::text FROM latest_run), '0')
    UNION ALL
    SELECT 9, 'last_run_transactions_indexed', COALESCE((SELECT transactions_indexed::text FROM latest_run), '0')
) AS rows
ORDER BY sort_order;
"#
}

fn postgres_explorer_overview_sql() -> &'static str {
    "\
SELECT 'current_height=' || COALESCE(MAX(height)::text, '0') FROM xriq_blocks;\n\
SELECT 'latest_block_hash=' || COALESCE((SELECT block_hash FROM xriq_blocks ORDER BY height DESC LIMIT 1), 'none');\n\
SELECT 'state_root=' || COALESCE((SELECT state_root FROM xriq_blocks ORDER BY height DESC LIMIT 1), 'none');\n\
SELECT 'stored_blocks=' || count(*) FROM xriq_blocks;\n\
SELECT 'pending_transactions=' || count(*) FROM xriq_mempool_entries;\n\
SELECT 'transactions=' || count(*) FROM xriq_transactions;\n\
SELECT 'accounts=' || count(*) FROM xriq_account_balances;\n\
SELECT 'indexer_run_id=' || COALESCE((SELECT run_id FROM xriq_indexer_runs ORDER BY completed_at DESC NULLS LAST, started_at DESC LIMIT 1), 'none');\n\
SELECT 'indexer_status=' || COALESCE((SELECT status FROM xriq_indexer_runs ORDER BY completed_at DESC NULLS LAST, started_at DESC LIMIT 1), 'unknown');\n\
SELECT 'indexer_from_height=' || COALESCE((SELECT from_height::text FROM xriq_indexer_runs ORDER BY completed_at DESC NULLS LAST, started_at DESC LIMIT 1), 'none');\n\
SELECT 'indexer_to_height=' || COALESCE((SELECT to_height::text FROM xriq_indexer_runs ORDER BY completed_at DESC NULLS LAST, started_at DESC LIMIT 1), 'none');\n\
SELECT 'indexer_blocks_indexed=' || COALESCE((SELECT blocks_indexed::text FROM xriq_indexer_runs ORDER BY completed_at DESC NULLS LAST, started_at DESC LIMIT 1), '0');\n\
SELECT 'indexer_transactions_indexed=' || COALESCE((SELECT transactions_indexed::text FROM xriq_indexer_runs ORDER BY completed_at DESC NULLS LAST, started_at DESC LIMIT 1), '0');\n"
}

fn postgres_audit_events_sql(target: &str) -> Result<String, String> {
    let (_, query) = split_http_target(target);
    let limit = limit_from_query(query, 25)?;
    Ok(format!(
        r#"
WITH ranked AS (
    SELECT
        row_number() OVER (ORDER BY event_id DESC) - 1 AS row_index,
        event_id,
        actor,
        action,
        resource_type,
        COALESCE(resource_id, 'none') AS resource_id,
        environment
    FROM xriq_audit_events
    ORDER BY event_id DESC
    LIMIT {limit}
),
counts AS (
    SELECT count(*) AS total_audit_events FROM xriq_audit_events
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'limit' AS key, '{limit}' AS value
    UNION ALL
    SELECT 1, 'audit_event_count', count(*)::text FROM ranked
    UNION ALL
    SELECT
        2,
        'next_cursor',
        CASE
            WHEN (SELECT total_audit_events FROM counts) > (SELECT count(*) FROM ranked)
            THEN COALESCE((SELECT event_id FROM ranked ORDER BY row_index DESC LIMIT 1), 'none')
            ELSE 'none'
        END
    UNION ALL
    SELECT 100 + row_index * 20, 'audit_event_' || row_index || '_event_id', event_id FROM ranked
    UNION ALL
    SELECT 101 + row_index * 20, 'audit_event_' || row_index || '_actor', actor FROM ranked
    UNION ALL
    SELECT 102 + row_index * 20, 'audit_event_' || row_index || '_action', action FROM ranked
    UNION ALL
    SELECT 103 + row_index * 20, 'audit_event_' || row_index || '_resource_type', resource_type FROM ranked
    UNION ALL
    SELECT 104 + row_index * 20, 'audit_event_' || row_index || '_resource_id', resource_id FROM ranked
    UNION ALL
    SELECT 105 + row_index * 20, 'audit_event_' || row_index || '_environment', environment FROM ranked
) AS rows
ORDER BY sort_order;
"#
    ))
}

fn postgres_blocks_sql(target: &str) -> Result<String, String> {
    let (_, query) = split_http_target(target);
    let limit = limit_from_query(query, 25)?;
    Ok(format!(
        r#"
WITH ranked AS (
    SELECT
        row_number() OVER (ORDER BY height DESC) - 1 AS row_index,
        height,
        block_hash,
        previous_block_hash,
        state_root,
        transactions_root,
        transaction_count,
        COALESCE(to_char(timestamp_utc AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), '1970-01-01T00:00:00Z') AS timestamp_utc
    FROM xriq_blocks
    ORDER BY height DESC
    LIMIT {limit}
),
counts AS (
    SELECT count(*) AS total_blocks FROM xriq_blocks
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'limit' AS key, '{limit}' AS value
    UNION ALL
    SELECT 1, 'block_count', count(*)::text FROM ranked
    UNION ALL
    SELECT
        2,
        'next_cursor',
        CASE
            WHEN (SELECT total_blocks FROM counts) > (SELECT count(*) FROM ranked)
            THEN COALESCE((SELECT height::text FROM ranked ORDER BY row_index DESC LIMIT 1), 'none')
            ELSE 'none'
        END
    UNION ALL
    SELECT 100 + row_index * 20, 'block_' || row_index || '_height', height::text FROM ranked
    UNION ALL
    SELECT 101 + row_index * 20, 'block_' || row_index || '_block_hash', block_hash FROM ranked
    UNION ALL
    SELECT 102 + row_index * 20, 'block_' || row_index || '_previous_block_hash', previous_block_hash FROM ranked
    UNION ALL
    SELECT 103 + row_index * 20, 'block_' || row_index || '_state_root', state_root FROM ranked
    UNION ALL
    SELECT 104 + row_index * 20, 'block_' || row_index || '_transactions_root', transactions_root FROM ranked
    UNION ALL
    SELECT 105 + row_index * 20, 'block_' || row_index || '_transaction_count', transaction_count::text FROM ranked
    UNION ALL
    SELECT 106 + row_index * 20, 'block_' || row_index || '_timestamp_utc', timestamp_utc FROM ranked
) AS rows
ORDER BY sort_order;
"#
    ))
}

fn postgres_block_detail_sql(identifier: &str) -> Result<String, String> {
    validate_block_identifier(identifier, "block identifier")?;
    let lookup_condition = if is_postgres_block_height_identifier(identifier) {
        format!("height = {identifier}")
    } else {
        format!("block_hash = '{identifier}'")
    };
    Ok(format!(
        r#"
WITH selected_block AS (
    SELECT
        height,
        block_hash,
        previous_block_hash,
        state_root,
        transactions_root,
        transaction_count,
        COALESCE(to_char(timestamp_utc AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), '1970-01-01T00:00:00Z') AS timestamp_utc
    FROM xriq_blocks
    WHERE {lookup_condition}
    LIMIT 1
),
ranked_transactions AS (
    SELECT
        row_number() OVER (ORDER BY transaction_index ASC, tx_hash ASC) - 1 AS row_index,
        tx_hash,
        block_height,
        block_hash,
        transaction_index,
        status,
        from_address,
        to_address,
        amount_base_units::text AS amount_base_units,
        fee_base_units::text AS fee_base_units,
        nonce
    FROM xriq_transactions
    WHERE block_height = (SELECT height FROM selected_block)
      AND block_hash = (SELECT block_hash FROM selected_block)
      AND block_height IS NOT NULL
      AND block_hash IS NOT NULL
      AND transaction_index IS NOT NULL
    ORDER BY transaction_index ASC, tx_hash ASC
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'found' AS key, CASE WHEN EXISTS(SELECT 1 FROM selected_block) THEN 'true' ELSE 'false' END AS value
    UNION ALL
    SELECT 100, 'block_0_height', height::text FROM selected_block
    UNION ALL
    SELECT 101, 'block_0_block_hash', block_hash FROM selected_block
    UNION ALL
    SELECT 102, 'block_0_previous_block_hash', previous_block_hash FROM selected_block
    UNION ALL
    SELECT 103, 'block_0_state_root', state_root FROM selected_block
    UNION ALL
    SELECT 104, 'block_0_transactions_root', transactions_root FROM selected_block
    UNION ALL
    SELECT 105, 'block_0_transaction_count', transaction_count::text FROM selected_block
    UNION ALL
    SELECT 106, 'block_0_timestamp_utc', timestamp_utc FROM selected_block
    UNION ALL
    SELECT 107, 'block_0_transaction_entry_count', count(*)::text FROM ranked_transactions
    UNION ALL
    SELECT 200 + row_index * 20, 'transaction_' || row_index || '_tx_hash', tx_hash FROM ranked_transactions
    UNION ALL
    SELECT 201 + row_index * 20, 'transaction_' || row_index || '_block_height', block_height::text FROM ranked_transactions
    UNION ALL
    SELECT 202 + row_index * 20, 'transaction_' || row_index || '_block_hash', block_hash FROM ranked_transactions
    UNION ALL
    SELECT 203 + row_index * 20, 'transaction_' || row_index || '_transaction_index', transaction_index::text FROM ranked_transactions
    UNION ALL
    SELECT 204 + row_index * 20, 'transaction_' || row_index || '_status', status FROM ranked_transactions
    UNION ALL
    SELECT 205 + row_index * 20, 'transaction_' || row_index || '_from_address', from_address FROM ranked_transactions
    UNION ALL
    SELECT 206 + row_index * 20, 'transaction_' || row_index || '_to_address', to_address FROM ranked_transactions
    UNION ALL
    SELECT 207 + row_index * 20, 'transaction_' || row_index || '_amount_base_units', amount_base_units FROM ranked_transactions
    UNION ALL
    SELECT 208 + row_index * 20, 'transaction_' || row_index || '_fee_base_units', fee_base_units FROM ranked_transactions
    UNION ALL
    SELECT 209 + row_index * 20, 'transaction_' || row_index || '_nonce', nonce::text FROM ranked_transactions
) AS rows
ORDER BY sort_order;
"#
    ))
}

fn postgres_transactions_sql(target: &str) -> Result<String, String> {
    let (_, query) = split_http_target(target);
    let limit = limit_from_query(query, 25)?;
    Ok(format!(
        r#"
WITH ranked AS (
    SELECT
        row_number() OVER (ORDER BY block_height DESC, transaction_index DESC, tx_hash ASC) - 1 AS row_index,
        tx_hash,
        block_height,
        block_hash,
        transaction_index,
        status,
        from_address,
        to_address,
        amount_base_units::text AS amount_base_units,
        fee_base_units::text AS fee_base_units,
        nonce
    FROM xriq_transactions
    WHERE block_height IS NOT NULL
      AND block_hash IS NOT NULL
      AND transaction_index IS NOT NULL
    ORDER BY block_height DESC, transaction_index DESC, tx_hash ASC
    LIMIT {limit}
),
counts AS (
    SELECT count(*) AS total_transactions
    FROM xriq_transactions
    WHERE block_height IS NOT NULL
      AND block_hash IS NOT NULL
      AND transaction_index IS NOT NULL
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'limit' AS key, '{limit}' AS value
    UNION ALL
    SELECT 1, 'transaction_count', count(*)::text FROM ranked
    UNION ALL
    SELECT
        2,
        'next_cursor',
        CASE
            WHEN (SELECT total_transactions FROM counts) > (SELECT count(*) FROM ranked)
            THEN COALESCE((SELECT block_height::text || ':' || transaction_index::text FROM ranked ORDER BY row_index DESC LIMIT 1), 'none')
            ELSE 'none'
        END
    UNION ALL
    SELECT 100 + row_index * 20, 'transaction_' || row_index || '_tx_hash', tx_hash FROM ranked
    UNION ALL
    SELECT 101 + row_index * 20, 'transaction_' || row_index || '_block_height', block_height::text FROM ranked
    UNION ALL
    SELECT 102 + row_index * 20, 'transaction_' || row_index || '_block_hash', block_hash FROM ranked
    UNION ALL
    SELECT 103 + row_index * 20, 'transaction_' || row_index || '_transaction_index', transaction_index::text FROM ranked
    UNION ALL
    SELECT 104 + row_index * 20, 'transaction_' || row_index || '_status', status FROM ranked
    UNION ALL
    SELECT 105 + row_index * 20, 'transaction_' || row_index || '_from_address', from_address FROM ranked
    UNION ALL
    SELECT 106 + row_index * 20, 'transaction_' || row_index || '_to_address', to_address FROM ranked
    UNION ALL
    SELECT 107 + row_index * 20, 'transaction_' || row_index || '_amount_base_units', amount_base_units FROM ranked
    UNION ALL
    SELECT 108 + row_index * 20, 'transaction_' || row_index || '_fee_base_units', fee_base_units FROM ranked
    UNION ALL
    SELECT 109 + row_index * 20, 'transaction_' || row_index || '_nonce', nonce::text FROM ranked
) AS rows
ORDER BY sort_order;
"#
    ))
}

fn postgres_mempool_sql(target: &str) -> Result<String, String> {
    let (_, query) = split_http_target(target);
    let limit = limit_from_query(query, 25)?;
    Ok(format!(
        r#"
WITH ranked AS (
    SELECT
        row_number() OVER (ORDER BY last_seen_at DESC, tx_hash ASC) - 1 AS row_index,
        tx_hash,
        from_address,
        to_address,
        amount_base_units::text AS amount_base_units,
        fee_base_units::text AS fee_base_units,
        nonce,
        status,
        COALESCE(to_char(first_seen_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'none') AS first_seen_at_utc,
        COALESCE(to_char(last_seen_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'none') AS last_seen_at_utc
    FROM xriq_mempool_entries
    ORDER BY last_seen_at DESC, tx_hash ASC
    LIMIT {limit}
),
counts AS (
    SELECT
        (SELECT count(*) FROM xriq_mempool_entries) AS total_pending_count,
        COALESCE((SELECT max(height)::text FROM xriq_blocks), '0') AS current_height
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'limit' AS key, '{limit}' AS value
    UNION ALL
    SELECT 1, 'current_height', (SELECT current_height FROM counts)
    UNION ALL
    SELECT 2, 'entry_count', count(*)::text FROM ranked
    UNION ALL
    SELECT 3, 'pending_count', (SELECT total_pending_count::text FROM counts)
    UNION ALL
    SELECT
        4,
        'next_cursor',
        CASE
            WHEN (SELECT total_pending_count FROM counts) > (SELECT count(*) FROM ranked)
            THEN COALESCE((SELECT tx_hash FROM ranked ORDER BY row_index DESC LIMIT 1), 'none')
            ELSE 'none'
        END
    UNION ALL
    SELECT 100 + row_index * 20, 'mempool_entry_' || row_index || '_tx_hash', tx_hash FROM ranked
    UNION ALL
    SELECT 101 + row_index * 20, 'mempool_entry_' || row_index || '_from_address', from_address FROM ranked
    UNION ALL
    SELECT 102 + row_index * 20, 'mempool_entry_' || row_index || '_to_address', to_address FROM ranked
    UNION ALL
    SELECT 103 + row_index * 20, 'mempool_entry_' || row_index || '_amount_base_units', amount_base_units FROM ranked
    UNION ALL
    SELECT 104 + row_index * 20, 'mempool_entry_' || row_index || '_fee_base_units', fee_base_units FROM ranked
    UNION ALL
    SELECT 105 + row_index * 20, 'mempool_entry_' || row_index || '_nonce', nonce::text FROM ranked
    UNION ALL
    SELECT 106 + row_index * 20, 'mempool_entry_' || row_index || '_status', status FROM ranked
    UNION ALL
    SELECT 107 + row_index * 20, 'mempool_entry_' || row_index || '_first_seen_at_utc', first_seen_at_utc FROM ranked
    UNION ALL
    SELECT 108 + row_index * 20, 'mempool_entry_' || row_index || '_last_seen_at_utc', last_seen_at_utc FROM ranked
) AS rows
ORDER BY sort_order;
"#
    ))
}

fn postgres_wallet_status_sql() -> &'static str {
    r#"
WITH latest_block AS (
    SELECT height, block_hash, state_root
    FROM xriq_blocks
    ORDER BY height DESC
    LIMIT 1
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'current_height' AS key, COALESCE((SELECT height::text FROM latest_block), '0') AS value
    UNION ALL
    SELECT 1, 'latest_block_hash', COALESCE((SELECT block_hash FROM latest_block), 'none')
    UNION ALL
    SELECT 2, 'state_root', COALESCE((SELECT state_root FROM latest_block), 'none')
    UNION ALL
    SELECT 3, 'account_count', count(*)::text FROM xriq_account_balances
    UNION ALL
    SELECT 4, 'pending_transactions', count(*)::text FROM xriq_mempool_entries
) AS rows
ORDER BY sort_order;
"#
}

fn postgres_wallet_draft_preview_sql(target: &str) -> Result<String, String> {
    let (_, query) = split_http_target(target);
    let request = PostgresWalletDraftPreviewRequest::from_query(query)?;
    Ok(format!(
        r#"
WITH latest_block AS (
    SELECT height
    FROM xriq_blocks
    ORDER BY height DESC
    LIMIT 1
),
sender AS (
    SELECT
        balance_base_units::text AS available_base_units,
        nonce::text AS sender_nonce
    FROM xriq_account_balances
    WHERE address = '{from_address}'
    LIMIT 1
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'current_height' AS key, COALESCE((SELECT height::text FROM latest_block), '0') AS value
    UNION ALL
    SELECT 1, 'sender_found', CASE WHEN EXISTS(SELECT 1 FROM sender) THEN 'true' ELSE 'false' END
    UNION ALL
    SELECT 2, 'available_base_units', COALESCE((SELECT available_base_units FROM sender), 'none')
    UNION ALL
    SELECT 3, 'sender_nonce', COALESCE((SELECT sender_nonce FROM sender), 'none')
    UNION ALL
    SELECT 10, 'draft_chain_id', '{chain_id}'
    UNION ALL
    SELECT 11, 'draft_from_address', '{from_address}'
    UNION ALL
    SELECT 12, 'draft_to_address', '{to_address}'
    UNION ALL
    SELECT 13, 'draft_amount_base_units', '{amount_base_units}'
    UNION ALL
    SELECT 14, 'draft_fee_base_units', '{fee_base_units}'
    UNION ALL
    SELECT 15, 'draft_nonce', '{nonce}'
    UNION ALL
    SELECT 16, 'draft_expires_at_height', '{expires_at_height}'
) AS rows
ORDER BY sort_order;
"#,
        chain_id = request.chain_id,
        from_address = request.from_address,
        to_address = request.to_address,
        amount_base_units = request.amount_base_units,
        fee_base_units = request.fee_base_units,
        nonce = request.nonce,
        expires_at_height = request
            .expires_at_height
            .map(|height| height.to_string())
            .unwrap_or_else(|| "none".to_string())
    ))
}

fn postgres_transaction_detail_sql(tx_hash: &str) -> Result<String, String> {
    validate_transaction_hash(tx_hash, "tx_hash")?;
    Ok(format!(
        r#"
WITH selected AS (
    SELECT
        tx_hash,
        block_height,
        block_hash,
        transaction_index,
        status,
        from_address,
        to_address,
        amount_base_units::text AS amount_base_units,
        fee_base_units::text AS fee_base_units,
        nonce
    FROM xriq_transactions
    WHERE tx_hash = '{tx_hash}'
      AND block_height IS NOT NULL
      AND block_hash IS NOT NULL
      AND transaction_index IS NOT NULL
    LIMIT 1
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'found' AS key, CASE WHEN EXISTS(SELECT 1 FROM selected) THEN 'true' ELSE 'false' END AS value
    UNION ALL
    SELECT 100, 'transaction_0_tx_hash', tx_hash FROM selected
    UNION ALL
    SELECT 101, 'transaction_0_block_height', block_height::text FROM selected
    UNION ALL
    SELECT 102, 'transaction_0_block_hash', block_hash FROM selected
    UNION ALL
    SELECT 103, 'transaction_0_transaction_index', transaction_index::text FROM selected
    UNION ALL
    SELECT 104, 'transaction_0_status', status FROM selected
    UNION ALL
    SELECT 105, 'transaction_0_from_address', from_address FROM selected
    UNION ALL
    SELECT 106, 'transaction_0_to_address', to_address FROM selected
    UNION ALL
    SELECT 107, 'transaction_0_amount_base_units', amount_base_units FROM selected
    UNION ALL
    SELECT 108, 'transaction_0_fee_base_units', fee_base_units FROM selected
    UNION ALL
    SELECT 109, 'transaction_0_nonce', nonce::text FROM selected
) AS rows
ORDER BY sort_order;
"#
    ))
}

fn postgres_wallet_transaction_status_sql(tx_hash: &str) -> Result<String, String> {
    validate_transaction_hash(tx_hash, "tx_hash")?;
    Ok(format!(
        r#"
WITH confirmed AS (
    SELECT
        tx_hash,
        status,
        block_height::text AS block_height,
        block_hash,
        transaction_index::text AS transaction_index,
        0 AS sort_order
    FROM xriq_transactions
    WHERE tx_hash = '{tx_hash}'
      AND block_height IS NOT NULL
      AND block_hash IS NOT NULL
      AND transaction_index IS NOT NULL
    LIMIT 1
),
pending AS (
    SELECT
        tx_hash,
        status,
        'none' AS block_height,
        'none' AS block_hash,
        'none' AS transaction_index,
        1 AS sort_order
    FROM xriq_mempool_entries
    WHERE tx_hash = '{tx_hash}'
      AND NOT EXISTS (SELECT 1 FROM confirmed)
    LIMIT 1
),
selected AS (
    SELECT * FROM confirmed
    UNION ALL
    SELECT * FROM pending
    ORDER BY sort_order
    LIMIT 1
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'found' AS key, CASE WHEN EXISTS(SELECT 1 FROM selected) THEN 'true' ELSE 'false' END AS value
    UNION ALL
    SELECT 100, 'transaction_0_tx_hash', tx_hash FROM selected
    UNION ALL
    SELECT 101, 'transaction_0_block_height', block_height FROM selected
    UNION ALL
    SELECT 102, 'transaction_0_block_hash', block_hash FROM selected
    UNION ALL
    SELECT 103, 'transaction_0_transaction_index', transaction_index FROM selected
    UNION ALL
    SELECT 104, 'transaction_0_status', status FROM selected
) AS rows
ORDER BY sort_order;
"#
    ))
}

fn postgres_iso20022_transaction_status_sql(tx_hash: &str) -> Result<String, String> {
    validate_transaction_hash(tx_hash, "tx_hash")?;
    Ok(format!(
        r#"
WITH confirmed AS (
    SELECT
        tx_hash,
        COALESCE(block_height::text, 'none') AS confirmed_block_height,
        status,
        from_address,
        to_address,
        amount_base_units::text AS amount_base_units,
        fee_base_units::text AS fee_base_units,
        nonce::text AS nonce,
        0 AS sort_order
    FROM xriq_transactions
    WHERE tx_hash = '{tx_hash}'
    LIMIT 1
),
pending AS (
    SELECT
        tx_hash,
        'none' AS confirmed_block_height,
        status,
        from_address,
        to_address,
        amount_base_units::text AS amount_base_units,
        fee_base_units::text AS fee_base_units,
        nonce::text AS nonce,
        1 AS sort_order
    FROM xriq_mempool_entries
    WHERE tx_hash = '{tx_hash}'
      AND NOT EXISTS (SELECT 1 FROM confirmed)
    LIMIT 1
),
selected AS (
    SELECT * FROM confirmed
    UNION ALL
    SELECT * FROM pending
    ORDER BY sort_order
    LIMIT 1
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'found' AS key, CASE WHEN EXISTS(SELECT 1 FROM selected) THEN 'true' ELSE 'false' END AS value
    UNION ALL
    SELECT 100, 'transaction_0_tx_hash', tx_hash FROM selected
    UNION ALL
    SELECT 101, 'transaction_0_confirmed_block_height', confirmed_block_height FROM selected
    UNION ALL
    SELECT 102, 'transaction_0_status', status FROM selected
    UNION ALL
    SELECT 103, 'transaction_0_from_address', from_address FROM selected
    UNION ALL
    SELECT 104, 'transaction_0_to_address', to_address FROM selected
    UNION ALL
    SELECT 105, 'transaction_0_amount_base_units', amount_base_units FROM selected
    UNION ALL
    SELECT 106, 'transaction_0_fee_base_units', fee_base_units FROM selected
    UNION ALL
    SELECT 107, 'transaction_0_nonce', nonce FROM selected
) AS rows
ORDER BY sort_order;
"#
    ))
}

fn postgres_iso20022_payment_initiation_preview_sql(target: &str) -> Result<String, String> {
    let (_, query) = split_http_target(target);
    let tx_hash = required_query_param_any(query, &["tx_hash"])?;
    validate_transaction_hash(tx_hash, "tx_hash")?;
    Ok(format!(
        r#"
WITH selected AS (
    SELECT
        tx_hash,
        COALESCE(block_height::text, 'none') AS confirmed_block_height,
        status,
        from_address,
        to_address,
        amount_base_units::text AS amount_base_units,
        fee_base_units::text AS fee_base_units,
        nonce::text AS nonce
    FROM xriq_transactions
    WHERE tx_hash = '{tx_hash}'
      AND block_height IS NOT NULL
      AND block_hash IS NOT NULL
      AND transaction_index IS NOT NULL
    LIMIT 1
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'found' AS key, CASE WHEN EXISTS(SELECT 1 FROM selected) THEN 'true' ELSE 'false' END AS value
    UNION ALL
    SELECT 100, 'transaction_0_tx_hash', tx_hash FROM selected
    UNION ALL
    SELECT 101, 'transaction_0_confirmed_block_height', confirmed_block_height FROM selected
    UNION ALL
    SELECT 102, 'transaction_0_status', status FROM selected
    UNION ALL
    SELECT 103, 'transaction_0_from_address', from_address FROM selected
    UNION ALL
    SELECT 104, 'transaction_0_to_address', to_address FROM selected
    UNION ALL
    SELECT 105, 'transaction_0_amount_base_units', amount_base_units FROM selected
    UNION ALL
    SELECT 106, 'transaction_0_fee_base_units', fee_base_units FROM selected
    UNION ALL
    SELECT 107, 'transaction_0_nonce', nonce FROM selected
) AS rows
ORDER BY sort_order;
"#,
        tx_hash = tx_hash
    ))
}

fn postgres_iso20022_account_statement_sql(address: &str, target: &str) -> Result<String, String> {
    validate_xriq_address(address, "address")?;
    let (_, query) = split_http_target(target);
    let from = iso_statement_time_param(query, "from", "1970-01-01T00:00:00Z")?;
    let to = iso_statement_time_param(query, "to", "1970-01-01T00:00:02Z")?;
    Ok(format!(
        r#"
WITH selected_account AS (
    SELECT
        address,
        balance_base_units::text AS closing_balance_base_units
    FROM xriq_account_balances
    WHERE address = '{address}'
    LIMIT 1
),
ranked AS (
    SELECT
        row_number() OVER (
            ORDER BY block_height DESC, transaction_index DESC, tx_hash ASC, direction ASC
        ) - 1 AS row_index,
        tx_hash,
        direction,
        block_height,
        amount_base_units::text AS amount_base_units,
        fee_base_units::text AS fee_base_units
    FROM xriq_account_transactions
    WHERE address = '{address}'
      AND block_height IS NOT NULL
      AND transaction_index IS NOT NULL
      AND EXISTS (SELECT 1 FROM selected_account)
    ORDER BY block_height DESC, transaction_index DESC, tx_hash ASC, direction ASC
    LIMIT 25
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'found' AS key, CASE WHEN EXISTS(SELECT 1 FROM selected_account) THEN 'true' ELSE 'false' END AS value
    UNION ALL
    SELECT 1, 'address', address FROM selected_account
    UNION ALL
    SELECT 2, 'from', '{from}'
    UNION ALL
    SELECT 3, 'to', '{to}'
    UNION ALL
    SELECT 4, 'closing_balance_base_units', closing_balance_base_units FROM selected_account
    UNION ALL
    SELECT 5, 'transaction_count', count(*)::text FROM ranked
    UNION ALL
    SELECT 100 + row_index * 20, 'transaction_' || row_index || '_tx_hash', tx_hash FROM ranked
    UNION ALL
    SELECT 101 + row_index * 20, 'transaction_' || row_index || '_direction', direction FROM ranked
    UNION ALL
    SELECT 102 + row_index * 20, 'transaction_' || row_index || '_block_height', block_height::text FROM ranked
    UNION ALL
    SELECT 103 + row_index * 20, 'transaction_' || row_index || '_amount_base_units', amount_base_units FROM ranked
    UNION ALL
    SELECT 104 + row_index * 20, 'transaction_' || row_index || '_fee_base_units', fee_base_units FROM ranked
) AS rows
ORDER BY sort_order;
"#,
        address = address,
        from = from,
        to = to
    ))
}

fn postgres_accounts_sql(target: &str) -> Result<String, String> {
    let (_, query) = split_http_target(target);
    let limit = limit_from_query(query, 25)?;
    Ok(format!(
        r#"
WITH ranked AS (
    SELECT
        row_number() OVER (ORDER BY balance.address ASC) - 1 AS row_index,
        balance.address,
        balance.balance_base_units::text AS balance_base_units,
        balance.nonce,
        balance.height,
        balance.state_root,
        account.first_seen_height,
        account.last_seen_height
    FROM xriq_account_balances balance
    LEFT JOIN xriq_accounts account
        ON account.address = balance.address
    ORDER BY balance.address ASC
    LIMIT {limit}
),
counts AS (
    SELECT count(*) AS total_accounts FROM xriq_account_balances
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'limit' AS key, '{limit}' AS value
    UNION ALL
    SELECT 1, 'account_count', count(*)::text FROM ranked
    UNION ALL
    SELECT
        2,
        'next_cursor',
        CASE
            WHEN (SELECT total_accounts FROM counts) > (SELECT count(*) FROM ranked)
            THEN COALESCE((SELECT address FROM ranked ORDER BY row_index DESC LIMIT 1), 'none')
            ELSE 'none'
        END
    UNION ALL
    SELECT 100 + row_index * 20, 'account_' || row_index || '_address', address FROM ranked
    UNION ALL
    SELECT 101 + row_index * 20, 'account_' || row_index || '_balance_base_units', balance_base_units FROM ranked
    UNION ALL
    SELECT 102 + row_index * 20, 'account_' || row_index || '_nonce', nonce::text FROM ranked
    UNION ALL
    SELECT 103 + row_index * 20, 'account_' || row_index || '_height', height::text FROM ranked
    UNION ALL
    SELECT 104 + row_index * 20, 'account_' || row_index || '_state_root', state_root FROM ranked
    UNION ALL
    SELECT 105 + row_index * 20, 'account_' || row_index || '_first_seen_height', COALESCE(first_seen_height::text, 'none') FROM ranked
    UNION ALL
    SELECT 106 + row_index * 20, 'account_' || row_index || '_last_seen_height', COALESCE(last_seen_height::text, 'none') FROM ranked
) AS rows
ORDER BY sort_order;
"#
    ))
}

fn postgres_account_detail_sql(address: &str) -> Result<String, String> {
    validate_xriq_address(address, "address")?;
    Ok(format!(
        r#"
WITH selected AS (
    SELECT
        balance.address,
        balance.balance_base_units::text AS balance_base_units,
        balance.nonce,
        balance.height,
        balance.state_root,
        account.first_seen_height,
        account.last_seen_height
    FROM xriq_account_balances balance
    LEFT JOIN xriq_accounts account
        ON account.address = balance.address
    WHERE balance.address = '{address}'
    LIMIT 1
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'found' AS key, CASE WHEN EXISTS(SELECT 1 FROM selected) THEN 'true' ELSE 'false' END AS value
    UNION ALL
    SELECT 100, 'account_0_address', address FROM selected
    UNION ALL
    SELECT 101, 'account_0_balance_base_units', balance_base_units FROM selected
    UNION ALL
    SELECT 102, 'account_0_nonce', nonce::text FROM selected
    UNION ALL
    SELECT 103, 'account_0_height', height::text FROM selected
    UNION ALL
    SELECT 104, 'account_0_state_root', state_root FROM selected
    UNION ALL
    SELECT 105, 'account_0_first_seen_height', COALESCE(first_seen_height::text, 'none') FROM selected
    UNION ALL
    SELECT 106, 'account_0_last_seen_height', COALESCE(last_seen_height::text, 'none') FROM selected
) AS rows
ORDER BY sort_order;
"#
    ))
}

fn postgres_account_history_sql(address: &str, target: &str) -> Result<String, String> {
    validate_xriq_address(address, "address")?;
    let (_, query) = split_http_target(target);
    let limit = limit_from_query(query, 25)?;
    Ok(format!(
        r#"
WITH ranked AS (
    SELECT
        row_number() OVER (
            ORDER BY block_height DESC, transaction_index DESC, tx_hash ASC, direction ASC
        ) - 1 AS row_index,
        address,
        tx_hash,
        direction,
        block_height,
        transaction_index,
        amount_base_units::text AS amount_base_units,
        fee_base_units::text AS fee_base_units
    FROM xriq_account_transactions
    WHERE address = '{address}'
      AND block_height IS NOT NULL
      AND transaction_index IS NOT NULL
    ORDER BY block_height DESC, transaction_index DESC, tx_hash ASC, direction ASC
    LIMIT {limit}
),
counts AS (
    SELECT count(*) AS total_transactions
    FROM xriq_account_transactions
    WHERE address = '{address}'
      AND block_height IS NOT NULL
      AND transaction_index IS NOT NULL
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'address' AS key, '{address}' AS value
    UNION ALL
    SELECT 1, 'limit', '{limit}'
    UNION ALL
    SELECT 2, 'transaction_count', count(*)::text FROM ranked
    UNION ALL
    SELECT
        3,
        'next_cursor',
        CASE
            WHEN (SELECT total_transactions FROM counts) > (SELECT count(*) FROM ranked)
            THEN COALESCE((SELECT block_height::text || ':' || transaction_index::text || ':' || tx_hash FROM ranked ORDER BY row_index DESC LIMIT 1), 'none')
            ELSE 'none'
        END
    UNION ALL
    SELECT 100 + row_index * 20, 'transaction_' || row_index || '_address', address FROM ranked
    UNION ALL
    SELECT 101 + row_index * 20, 'transaction_' || row_index || '_tx_hash', tx_hash FROM ranked
    UNION ALL
    SELECT 102 + row_index * 20, 'transaction_' || row_index || '_direction', direction FROM ranked
    UNION ALL
    SELECT 103 + row_index * 20, 'transaction_' || row_index || '_block_height', block_height::text FROM ranked
    UNION ALL
    SELECT 104 + row_index * 20, 'transaction_' || row_index || '_transaction_index', transaction_index::text FROM ranked
    UNION ALL
    SELECT 105 + row_index * 20, 'transaction_' || row_index || '_amount_base_units', amount_base_units FROM ranked
    UNION ALL
    SELECT 106 + row_index * 20, 'transaction_' || row_index || '_fee_base_units', fee_base_units FROM ranked
) AS rows
ORDER BY sort_order;
"#
    ))
}

fn postgres_snapshots_sql(target: &str) -> Result<String, String> {
    let (_, query) = split_http_target(target);
    let limit = limit_from_query(query, 25)?;
    Ok(format!(
        r#"
WITH counts AS (
    SELECT
        (SELECT count(*) FROM xriq_blocks) AS block_count,
        (SELECT count(*) FROM xriq_transactions) AS transaction_count,
        (SELECT count(*) FROM xriq_audit_events) AS audit_event_count
),
ranked AS (
    SELECT
        row_number() OVER (ORDER BY snapshot.current_height DESC, snapshot.snapshot_name ASC) - 1 AS row_index,
        snapshot.snapshot_name,
        snapshot.snapshot_dir,
        snapshot.current_height,
        snapshot.latest_block_hash,
        snapshot.state_root,
        counts.block_count,
        counts.transaction_count,
        counts.audit_event_count
    FROM xriq_snapshots snapshot
    CROSS JOIN counts
    ORDER BY snapshot.current_height DESC, snapshot.snapshot_name ASC
    LIMIT {limit}
),
totals AS (
    SELECT count(*) AS total_snapshots FROM xriq_snapshots
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'limit' AS key, '{limit}' AS value
    UNION ALL
    SELECT 1, 'snapshot_count', count(*)::text FROM ranked
    UNION ALL
    SELECT
        2,
        'next_cursor',
        CASE
            WHEN (SELECT total_snapshots FROM totals) > (SELECT count(*) FROM ranked)
            THEN COALESCE((SELECT snapshot_name FROM ranked ORDER BY row_index DESC LIMIT 1), 'none')
            ELSE 'none'
        END
    UNION ALL
    SELECT 100 + row_index * 20, 'snapshot_' || row_index || '_snapshot_name', snapshot_name FROM ranked
    UNION ALL
    SELECT 101 + row_index * 20, 'snapshot_' || row_index || '_snapshot_dir', snapshot_dir FROM ranked
    UNION ALL
    SELECT 102 + row_index * 20, 'snapshot_' || row_index || '_current_height', current_height::text FROM ranked
    UNION ALL
    SELECT 103 + row_index * 20, 'snapshot_' || row_index || '_latest_block_hash', latest_block_hash FROM ranked
    UNION ALL
    SELECT 104 + row_index * 20, 'snapshot_' || row_index || '_state_root', state_root FROM ranked
    UNION ALL
    SELECT 105 + row_index * 20, 'snapshot_' || row_index || '_block_count', block_count::text FROM ranked
    UNION ALL
    SELECT 106 + row_index * 20, 'snapshot_' || row_index || '_transaction_count', transaction_count::text FROM ranked
    UNION ALL
    SELECT 107 + row_index * 20, 'snapshot_' || row_index || '_audit_event_count', audit_event_count::text FROM ranked
    UNION ALL
    SELECT 108 + row_index * 20, 'snapshot_' || row_index || '_export_status', 'disabled' FROM ranked
    UNION ALL
    SELECT 109 + row_index * 20, 'snapshot_' || row_index || '_import_status', 'disabled' FROM ranked
) AS rows
ORDER BY sort_order;
"#
    ))
}

fn postgres_snapshot_detail_sql(snapshot_name: &str) -> Result<String, String> {
    validate_snapshot_name(snapshot_name, "snapshot_name")?;
    Ok(format!(
        r#"
WITH counts AS (
    SELECT
        (SELECT count(*) FROM xriq_blocks) AS block_count,
        (SELECT count(*) FROM xriq_transactions) AS transaction_count,
        (SELECT count(*) FROM xriq_audit_events) AS audit_event_count
),
selected AS (
    SELECT
        snapshot.snapshot_name,
        snapshot.snapshot_dir,
        snapshot.current_height,
        snapshot.latest_block_hash,
        snapshot.state_root,
        counts.block_count,
        counts.transaction_count,
        counts.audit_event_count
    FROM xriq_snapshots snapshot
    CROSS JOIN counts
    WHERE snapshot.snapshot_name = '{snapshot_name}'
    LIMIT 1
)
SELECT key || '=' || value
FROM (
    SELECT 0 AS sort_order, 'found' AS key, CASE WHEN EXISTS(SELECT 1 FROM selected) THEN 'true' ELSE 'false' END AS value
    UNION ALL
    SELECT 100, 'snapshot_0_snapshot_name', snapshot_name FROM selected
    UNION ALL
    SELECT 101, 'snapshot_0_snapshot_dir', snapshot_dir FROM selected
    UNION ALL
    SELECT 102, 'snapshot_0_current_height', current_height::text FROM selected
    UNION ALL
    SELECT 103, 'snapshot_0_latest_block_hash', latest_block_hash FROM selected
    UNION ALL
    SELECT 104, 'snapshot_0_state_root', state_root FROM selected
    UNION ALL
    SELECT 105, 'snapshot_0_block_count', block_count::text FROM selected
    UNION ALL
    SELECT 106, 'snapshot_0_transaction_count', transaction_count::text FROM selected
    UNION ALL
    SELECT 107, 'snapshot_0_audit_event_count', audit_event_count::text FROM selected
    UNION ALL
    SELECT 108, 'snapshot_0_export_status', 'disabled' FROM selected
    UNION ALL
    SELECT 109, 'snapshot_0_import_status', 'disabled' FROM selected
) AS rows
ORDER BY sort_order;
"#
    ))
}

fn parse_key_value_lines(output: &str, context: &str) -> Result<BTreeMap<String, String>, String> {
    let mut values = BTreeMap::new();
    for line in output.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let Some((key, value)) = line.split_once('=') else {
            return Err(format!("{context}: expected key=value line, got {line:?}"));
        };
        values.insert(key.to_string(), value.to_string());
    }
    Ok(values)
}

fn render_postgres_read_model_status_json(
    config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let blocks = required_u64(values, "blocks")?;
    let transactions = required_u64(values, "transactions")?;
    let accounts = required_u64(values, "accounts")?;
    let account_balances = required_u64(values, "account_balances")?;
    let account_transactions = required_u64(values, "account_transactions")?;
    let mempool_entries = required_u64(values, "mempool_entries")?;
    let audit_events = required_u64(values, "audit_events")?;
    let indexer_runs = required_u64(values, "indexer_runs")?;
    let latest_height = optional_u64_json(values, "latest_height")?;
    let latest_block_hash = optional_string_json(values, "latest_block_hash")?;
    let indexer_status = values
        .get("indexer_status")
        .map(String::as_str)
        .unwrap_or("unknown");

    Ok(format!(
        concat!(
            "{{\n",
            "  \"environment\": \"private-devnet\",\n",
            "  \"service\": \"xriq-api\",\n",
            "  \"source\": \"postgres-read-model\",\n",
            "  \"warning\": {},\n",
            "  \"route\": {},\n",
            "  \"container\": {},\n",
            "  \"database\": {},\n",
            "  \"status\": \"available\",\n",
            "  \"read_only\": true,\n",
            "  \"indexer_status\": {},\n",
            "  \"latest_height\": {},\n",
            "  \"latest_block_hash\": {},\n",
            "  \"counts\": {{\n",
            "    \"blocks\": {},\n",
            "    \"transactions\": {},\n",
            "    \"accounts\": {},\n",
            "    \"account_balances\": {},\n",
            "    \"account_transactions\": {},\n",
            "    \"mempool_entries\": {},\n",
            "    \"audit_events\": {},\n",
            "    \"indexer_runs\": {}\n",
            "  }}\n",
            "}}"
        ),
        json_string(POSTGRES_READ_MODEL_WARNING),
        json_string(POSTGRES_READ_MODEL_STATUS_ROUTE),
        json_string(config.docker_container),
        json_string(config.database),
        json_string(indexer_status),
        latest_height,
        latest_block_hash,
        blocks,
        transactions,
        accounts,
        account_balances,
        account_transactions,
        mempool_entries,
        audit_events,
        indexer_runs
    ))
}

fn render_postgres_node_status_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let current_height = required_u64_for(values, "current_height", "postgres node status")?;
    let latest_block_hash = optional_string_json(values, "latest_block_hash")?;
    let state_root = optional_string_json(values, "state_root")?;
    let stored_blocks = required_u64_for(values, "stored_blocks", "postgres node status")?;
    let pending_transactions =
        required_u64_for(values, "pending_transactions", "postgres node status")?;

    Ok(format!(
        concat!(
            "{{\n",
            "  \"environment\": \"private-devnet\",\n",
            "  \"service\": \"xriq-api\",\n",
            "  \"status\": \"healthy\",\n",
            "  \"mode\": \"serve-readonly\",\n",
            "  \"source\": \"postgres-read-model\",\n",
            "  \"warning\": {},\n",
            "  \"read_only\": true,\n",
            "  \"network\": {},\n",
            "  \"current_height\": {},\n",
            "  \"latest_block_hash\": {},\n",
            "  \"state_root\": {},\n",
            "  \"stored_blocks\": {},\n",
            "  \"pending_transactions\": {},\n",
            "  \"wallet_submit_status\": \"disabled\",\n",
            "  \"block_production_status\": \"disabled\"\n",
            "}}"
        ),
        json_string(POSTGRES_READ_MODEL_WARNING),
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK),
        current_height,
        latest_block_hash,
        state_root,
        stored_blocks,
        pending_transactions
    ))
}

fn render_postgres_indexer_status_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let status = required_string_for(values, "status", "postgres indexer status")?;
    let latest_indexed_height =
        required_u64_for(values, "latest_indexed_height", "postgres indexer status")?;
    let latest_indexed_block_hash = optional_string_json(values, "latest_indexed_block_hash")?;
    let lag_blocks = required_u64_for(values, "lag_blocks", "postgres indexer status")?;
    let last_run_id = optional_string_json(values, "last_run_id")?;
    let last_run_status =
        required_string_for(values, "last_run_status", "postgres indexer status")?;
    let last_run_from_height =
        optional_u64_json_for(values, "last_run_from_height", "postgres indexer status")?;
    let last_run_to_height =
        optional_u64_json_for(values, "last_run_to_height", "postgres indexer status")?;
    let last_run_blocks_indexed =
        required_u64_for(values, "last_run_blocks_indexed", "postgres indexer status")?;
    let last_run_transactions_indexed = required_u64_for(
        values,
        "last_run_transactions_indexed",
        "postgres indexer status",
    )?;

    Ok(format!(
        concat!(
            "{{\n",
            "  \"environment\": \"private-devnet\",\n",
            "  \"service\": \"xriq-indexer\",\n",
            "  \"source\": \"postgres-read-model\",\n",
            "  \"warning\": {},\n",
            "  \"read_only\": true,\n",
            "  \"status\": {},\n",
            "  \"latest_indexed_height\": {},\n",
            "  \"latest_indexed_block_hash\": {},\n",
            "  \"lag_blocks\": {},\n",
            "  \"last_run\": {{\n",
            "    \"run_id\": {},\n",
            "    \"status\": {},\n",
            "    \"from_height\": {},\n",
            "    \"to_height\": {},\n",
            "    \"blocks_indexed\": {},\n",
            "    \"transactions_indexed\": {}\n",
            "  }}\n",
            "}}"
        ),
        json_string(POSTGRES_READ_MODEL_WARNING),
        json_string(status),
        latest_indexed_height,
        latest_indexed_block_hash,
        lag_blocks,
        last_run_id,
        json_string(last_run_status),
        last_run_from_height,
        last_run_to_height,
        last_run_blocks_indexed,
        last_run_transactions_indexed
    ))
}

fn render_postgres_explorer_overview_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let current_height = required_u64_for(values, "current_height", "postgres explorer overview")?;
    let latest_block_hash = optional_string_json(values, "latest_block_hash")?;
    let state_root = optional_string_json(values, "state_root")?;
    let stored_blocks = required_u64_for(values, "stored_blocks", "postgres explorer overview")?;
    let pending_transactions =
        required_u64_for(values, "pending_transactions", "postgres explorer overview")?;
    let transactions = required_u64_for(values, "transactions", "postgres explorer overview")?;
    let accounts = required_u64_for(values, "accounts", "postgres explorer overview")?;
    let indexer_run_id = optional_string_json(values, "indexer_run_id")?;
    let indexer_status = values
        .get("indexer_status")
        .map(String::as_str)
        .unwrap_or("unknown");
    let indexer_from_height =
        optional_u64_json_for(values, "indexer_from_height", "postgres explorer overview")?;
    let indexer_to_height =
        optional_u64_json_for(values, "indexer_to_height", "postgres explorer overview")?;
    let indexer_blocks_indexed = required_u64_for(
        values,
        "indexer_blocks_indexed",
        "postgres explorer overview",
    )?;
    let indexer_transactions_indexed = required_u64_for(
        values,
        "indexer_transactions_indexed",
        "postgres explorer overview",
    )?;

    Ok(format!(
        concat!(
            "{{\n",
            "  \"environment\": \"private-devnet\",\n",
            "  \"network\": {},\n",
            "  \"source\": \"postgres-read-model\",\n",
            "  \"warning\": {},\n",
            "  \"read_only\": true,\n",
            "  \"chain\": {{\n",
            "    \"current_height\": {},\n",
            "    \"latest_block_hash\": {},\n",
            "    \"state_root\": {},\n",
            "    \"stored_blocks\": {},\n",
            "    \"pending_transactions\": {}\n",
            "  }},\n",
            "  \"indexer\": {{\n",
            "    \"environment\": \"private-devnet\",\n",
            "    \"service\": \"xriq-indexer\",\n",
            "    \"status\": {},\n",
            "    \"latest_indexed_height\": {},\n",
            "    \"latest_indexed_block_hash\": {},\n",
            "    \"lag_blocks\": 0,\n",
            "    \"last_run\": {{\n",
            "      \"run_id\": {},\n",
            "      \"status\": {},\n",
            "      \"from_height\": {},\n",
            "      \"to_height\": {},\n",
            "      \"blocks_indexed\": {},\n",
            "      \"transactions_indexed\": {}\n",
            "    }}\n",
            "  }},\n",
            "  \"totals\": {{\n",
            "    \"blocks\": {},\n",
            "    \"transactions\": {},\n",
            "    \"accounts\": {}\n",
            "  }}\n",
            "}}"
        ),
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK),
        json_string(POSTGRES_READ_MODEL_WARNING),
        current_height,
        latest_block_hash,
        state_root,
        stored_blocks,
        pending_transactions,
        json_string(indexer_status),
        current_height,
        latest_block_hash,
        indexer_run_id,
        json_string(indexer_status),
        indexer_from_height,
        indexer_to_height,
        indexer_blocks_indexed,
        indexer_transactions_indexed,
        stored_blocks,
        transactions,
        accounts
    ))
}

fn render_postgres_audit_events_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let limit = required_u64_for(values, "limit", "postgres audit events")?;
    let audit_event_count = required_u64_for(values, "audit_event_count", "postgres audit events")?;
    let next_cursor = optional_string_json(values, "next_cursor")?;
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(&mut output, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    writeln!(&mut output, "  \"limit\": {},", limit).expect("write to String");
    writeln!(&mut output, "  \"next_cursor\": {},", next_cursor).expect("write to String");
    output.push_str("  \"audit_events\": [");
    for index in 0..audit_event_count {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_postgres_audit_event_json_inline(values, index, 4)?);
    }
    if audit_event_count > 0 {
        output.push('\n');
    }
    output.push_str("  ],\n");
    let local_refusal_audit_events = local_refusal_audit_events();
    writeln!(
        &mut output,
        "  \"local_refusal_audit_count\": {},",
        local_refusal_audit_events.len()
    )
    .expect("write to String");
    output.push_str("  \"local_refusal_audit_events\": [");
    for (index, event) in local_refusal_audit_events.iter().enumerate() {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_local_refusal_audit_event_json_inline(event, 4));
    }
    if !local_refusal_audit_events.is_empty() {
        output.push('\n');
    }
    output.push_str("  ]\n}");
    Ok(output)
}

fn render_postgres_audit_event_json_inline(
    values: &BTreeMap<String, String>,
    index: u64,
    indent: usize,
) -> Result<String, String> {
    let prefix = format!("audit_event_{index}_");
    let event_id = required_string_for(
        values,
        &format!("{prefix}event_id"),
        "postgres audit events",
    )?;
    let actor = required_string_for(values, &format!("{prefix}actor"), "postgres audit events")?;
    let action = required_string_for(values, &format!("{prefix}action"), "postgres audit events")?;
    let resource_type = required_string_for(
        values,
        &format!("{prefix}resource_type"),
        "postgres audit events",
    )?;
    let resource_id = optional_string_json(values, &format!("{prefix}resource_id"))?;
    let environment = required_string_for(
        values,
        &format!("{prefix}environment"),
        "postgres audit events",
    )?;
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    Ok(format!(
        "{spaces}{{\n{nested}\"event_id\": {},\n{nested}\"actor\": {},\n{nested}\"action\": {},\n{nested}\"resource_type\": {},\n{nested}\"resource_id\": {},\n{nested}\"environment\": {}\n{spaces}}}",
        json_string(event_id),
        json_string(actor),
        json_string(action),
        json_string(resource_type),
        resource_id,
        json_string(environment)
    ))
}

fn render_local_refusal_audit_event_json_inline(
    event: &LocalRefusalAuditEventResponse,
    indent: usize,
) -> String {
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    let metadata = " ".repeat(indent + 4);
    format!(
        "{spaces}{{\n{nested}\"event_id\": {},\n{nested}\"actor\": {},\n{nested}\"action\": {},\n{nested}\"resource_type\": {},\n{nested}\"resource_id\": {},\n{nested}\"environment\": {},\n{nested}\"audit_scope\": {},\n{nested}\"recording\": {},\n{nested}\"outcome\": {},\n{nested}\"status\": {},\n{nested}\"mutation\": {},\n{nested}\"metadata\": {{\n{metadata}\"endpoint\": {},\n{metadata}\"refusal_code\": {},\n{metadata}\"explicit_flag\": {},\n{metadata}\"local_request_id\": {},\n{metadata}\"resource_id_policy\": {},\n{metadata}\"metadata_policy\": {}\n{nested}}}\n{spaces}}}",
        json_string(event.event_id),
        json_string(event.actor),
        json_string(event.action),
        json_string(event.resource_type),
        json_string(event.resource_id),
        json_string(event.environment),
        json_string(event.audit_scope),
        json_string(event.recording),
        json_string(event.outcome),
        json_string(event.status),
        json_string(event.mutation),
        json_string(event.metadata.endpoint),
        json_string(event.metadata.refusal_code),
        json_string(event.metadata.explicit_flag),
        json_string(event.metadata.local_request_id),
        json_string(event.metadata.resource_id_policy),
        json_string(event.metadata.metadata_policy)
    )
}

fn render_postgres_blocks_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let limit = required_u64_for(values, "limit", "postgres blocks")?;
    let block_count = required_u64_for(values, "block_count", "postgres blocks")?;
    let next_cursor = optional_string_json(values, "next_cursor")?;
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(&mut output, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    writeln!(&mut output, "  \"limit\": {},", limit).expect("write to String");
    writeln!(&mut output, "  \"next_cursor\": {},", next_cursor).expect("write to String");
    output.push_str("  \"blocks\": [");
    for index in 0..block_count {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_postgres_block_json_inline(values, index, 4)?);
    }
    if block_count > 0 {
        output.push('\n');
    }
    output.push_str("  ]\n}");
    Ok(output)
}

fn render_postgres_block_json_inline(
    values: &BTreeMap<String, String>,
    index: u64,
    indent: usize,
) -> Result<String, String> {
    let prefix = format!("block_{index}_");
    let height = required_u64_for(values, &format!("{prefix}height"), "postgres blocks")?;
    let block_hash =
        required_string_for(values, &format!("{prefix}block_hash"), "postgres blocks")?;
    let previous_block_hash = required_string_for(
        values,
        &format!("{prefix}previous_block_hash"),
        "postgres blocks",
    )?;
    let state_root =
        required_string_for(values, &format!("{prefix}state_root"), "postgres blocks")?;
    let transactions_root = required_string_for(
        values,
        &format!("{prefix}transactions_root"),
        "postgres blocks",
    )?;
    let transaction_count = required_u64_for(
        values,
        &format!("{prefix}transaction_count"),
        "postgres blocks",
    )?;
    let timestamp_utc =
        required_string_for(values, &format!("{prefix}timestamp_utc"), "postgres blocks")?;
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    Ok(format!(
        "{spaces}{{\n{nested}\"height\": {},\n{nested}\"block_hash\": {},\n{nested}\"previous_block_hash\": {},\n{nested}\"state_root\": {},\n{nested}\"transactions_root\": {},\n{nested}\"transaction_count\": {},\n{nested}\"timestamp_utc\": {}\n{spaces}}}",
        height,
        json_string(block_hash),
        json_string(previous_block_hash),
        json_string(state_root),
        json_string(transactions_root),
        transaction_count,
        json_string(timestamp_utc)
    ))
}

fn render_postgres_block_detail_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let context = "postgres block detail";
    let prefix = "block_0_";
    let height = required_u64_for(values, &format!("{prefix}height"), context)?;
    let block_hash = required_string_for(values, &format!("{prefix}block_hash"), context)?;
    let previous_block_hash =
        required_string_for(values, &format!("{prefix}previous_block_hash"), context)?;
    let state_root = required_string_for(values, &format!("{prefix}state_root"), context)?;
    let transactions_root =
        required_string_for(values, &format!("{prefix}transactions_root"), context)?;
    let transaction_count =
        required_u64_for(values, &format!("{prefix}transaction_count"), context)?;
    let timestamp_utc = required_string_for(values, &format!("{prefix}timestamp_utc"), context)?;
    let transaction_entry_count =
        required_u64_for(values, &format!("{prefix}transaction_entry_count"), context)?;

    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(&mut output, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    writeln!(&mut output, "  \"height\": {},", height).expect("write to String");
    writeln!(
        &mut output,
        "  \"block_hash\": {},",
        json_string(block_hash)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"previous_block_hash\": {},",
        json_string(previous_block_hash)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"state_root\": {},",
        json_string(state_root)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"transactions_root\": {},",
        json_string(transactions_root)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"transaction_count\": {},",
        transaction_count
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"timestamp_utc\": {},",
        json_string(timestamp_utc)
    )
    .expect("write to String");
    output.push_str("  \"transactions\": [");
    for index in 0..transaction_entry_count {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_postgres_transaction_json_inline(values, index, 4)?);
    }
    if transaction_entry_count > 0 {
        output.push('\n');
    }
    output.push_str("  ]\n}");
    Ok(output)
}

fn render_postgres_transactions_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let limit = required_u64_for(values, "limit", "postgres transactions")?;
    let transaction_count = required_u64_for(values, "transaction_count", "postgres transactions")?;
    let next_cursor = optional_string_json(values, "next_cursor")?;
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(&mut output, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    writeln!(&mut output, "  \"limit\": {},", limit).expect("write to String");
    writeln!(&mut output, "  \"next_cursor\": {},", next_cursor).expect("write to String");
    output.push_str("  \"transactions\": [");
    for index in 0..transaction_count {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_postgres_transaction_json_inline(values, index, 4)?);
    }
    if transaction_count > 0 {
        output.push('\n');
    }
    output.push_str("  ]\n}");
    Ok(output)
}

fn render_postgres_mempool_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let limit = required_u64_for(values, "limit", "postgres mempool")?;
    let current_height = required_u64_for(values, "current_height", "postgres mempool")?;
    let entry_count = required_u64_for(values, "entry_count", "postgres mempool")?;
    let pending_count = required_u64_for(values, "pending_count", "postgres mempool")?;
    let next_cursor = optional_string_json(values, "next_cursor")?;
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(&mut output, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(MEMPOOL_READONLY_WARNING)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"read_model_warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    writeln!(&mut output, "  \"current_height\": {},", current_height).expect("write to String");
    writeln!(&mut output, "  \"pending_count\": {},", pending_count).expect("write to String");
    writeln!(&mut output, "  \"limit\": {},", limit).expect("write to String");
    writeln!(&mut output, "  \"next_cursor\": {},", next_cursor).expect("write to String");
    writeln!(&mut output, "  \"inspect_status\": \"enabled\",").expect("write to String");
    writeln!(&mut output, "  \"submit_status\": \"disabled\",").expect("write to String");
    writeln!(&mut output, "  \"produce_block_status\": \"disabled\",").expect("write to String");
    output.push_str("  \"entries\": [");
    for index in 0..entry_count {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_postgres_mempool_entry_json_inline(
            values, index, 4,
        )?);
    }
    if entry_count > 0 {
        output.push('\n');
    }
    output.push_str("  ]\n}");
    Ok(output)
}

fn render_postgres_wallet_status_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let current_height = required_u64_for(values, "current_height", "postgres wallet status")?;
    let latest_block_hash =
        required_string_for(values, "latest_block_hash", "postgres wallet status")?;
    let state_root = required_string_for(values, "state_root", "postgres wallet status")?;
    let account_count = required_u64_for(values, "account_count", "postgres wallet status")?;
    let pending_transactions =
        required_u64_for(values, "pending_transactions", "postgres wallet status")?;

    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(&mut output, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(WALLET_PREVIEW_WARNING)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"read_model_warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    writeln!(&mut output, "  \"current_height\": {},", current_height).expect("write to String");
    writeln!(
        &mut output,
        "  \"latest_block_hash\": {},",
        json_string(latest_block_hash)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"state_root\": {},",
        json_string(state_root)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"account_count\": {},", account_count).expect("write to String");
    writeln!(
        &mut output,
        "  \"pending_transactions\": {},",
        pending_transactions
    )
    .expect("write to String");
    writeln!(&mut output, "  \"capabilities\": {{").expect("write to String");
    writeln!(&mut output, "    \"draft\": true,").expect("write to String");
    writeln!(&mut output, "    \"submit\": false,").expect("write to String");
    writeln!(&mut output, "    \"send\": false").expect("write to String");
    output.push_str("  }\n}");
    Ok(output)
}

fn render_postgres_wallet_draft_preview_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let context = "postgres wallet draft preview";
    let current_height = required_u64_for(values, "current_height", context)?;
    let sender_found = required_string_for(values, "sender_found", context)? == "true";
    let available_base_units = optional_u128_from_values(values, "available_base_units", context)?;
    let sender_nonce = optional_u64_from_values(values, "sender_nonce", context)?;
    let chain_id = required_string_for(values, "draft_chain_id", context)?;
    let from_address = required_string_for(values, "draft_from_address", context)?;
    let to_address = required_string_for(values, "draft_to_address", context)?;
    let amount_base_units = required_u128_for(values, "draft_amount_base_units", context)?;
    let fee_base_units = required_u128_for(values, "draft_fee_base_units", context)?;
    let nonce = required_u64_for(values, "draft_nonce", context)?;
    let expires_at_height = optional_u64_from_values(values, "draft_expires_at_height", context)?;

    let debit_base_units = amount_base_units.checked_add(fee_base_units);
    let remaining_base_units = match (available_base_units, debit_base_units) {
        (Some(balance), Some(debit)) if balance >= debit => Some(balance - debit),
        _ => None,
    };
    let mut errors = Vec::new();

    if !sender_found {
        errors.push("sender account not found".to_string());
    }
    if from_address == to_address {
        errors.push("sender and recipient must differ".to_string());
    }
    if amount_base_units == 0 {
        errors.push("amount must be greater than zero".to_string());
    }
    if fee_base_units < PRIVATE_DEVNET_MIN_FEE_BASE_UNITS {
        errors.push(format!(
            "fee must be at least {PRIVATE_DEVNET_MIN_FEE_BASE_UNITS} base units"
        ));
    }
    if let Some(sender_nonce) = sender_nonce {
        if nonce != sender_nonce {
            errors.push(format!("nonce must match sender nonce {sender_nonce}"));
        }
    }
    if expires_at_height.is_some_and(|height| height <= current_height) {
        errors.push("expiry must be greater than current height".to_string());
    }
    if debit_base_units.is_none() {
        errors.push("amount plus fee overflows base-unit range".to_string());
    }
    if matches!(
        (available_base_units, debit_base_units),
        (Some(balance), Some(debit)) if debit > balance
    ) {
        errors.push("debit exceeds available balance".to_string());
    }

    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(&mut output, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(WALLET_PREVIEW_WARNING)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"read_model_warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    writeln!(&mut output, "  \"mutation\": \"none\",").expect("write to String");
    writeln!(&mut output, "  \"validation\": {{").expect("write to String");
    writeln!(&mut output, "    \"ok\": {},", errors.is_empty()).expect("write to String");
    writeln!(
        &mut output,
        "    \"errors\": {}",
        json_string_array(&errors)
    )
    .expect("write to String");
    writeln!(&mut output, "  }},").expect("write to String");
    writeln!(&mut output, "  \"draft\": {{").expect("write to String");
    writeln!(&mut output, "    \"chain_id\": {},", json_string(chain_id)).expect("write to String");
    writeln!(
        &mut output,
        "    \"from_address\": {},",
        json_string(from_address)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"to_address\": {},",
        json_string(to_address)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"amount_base_units\": {},",
        json_string(&amount_base_units.to_string())
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"fee_base_units\": {},",
        json_string(&fee_base_units.to_string())
    )
    .expect("write to String");
    writeln!(&mut output, "    \"nonce\": {},", nonce).expect("write to String");
    writeln!(
        &mut output,
        "    \"expires_at_height\": {}",
        json_optional_u64_value(expires_at_height)
    )
    .expect("write to String");
    writeln!(&mut output, "  }},").expect("write to String");
    writeln!(&mut output, "  \"balance\": {{").expect("write to String");
    writeln!(
        &mut output,
        "    \"available_base_units\": {},",
        json_optional_u128_string(available_base_units)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"debit_base_units\": {},",
        json_optional_u128_string(debit_base_units)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"remaining_base_units\": {}",
        json_optional_u128_string(remaining_base_units)
    )
    .expect("write to String");
    output.push_str("  }\n}");
    Ok(output)
}

fn render_postgres_transaction_detail_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let prefix = "transaction_0_";
    let tx_hash = required_string_for(
        values,
        &format!("{prefix}tx_hash"),
        "postgres transaction detail",
    )?;
    let block_height = required_u64_for(
        values,
        &format!("{prefix}block_height"),
        "postgres transaction detail",
    )?;
    let block_hash = required_string_for(
        values,
        &format!("{prefix}block_hash"),
        "postgres transaction detail",
    )?;
    let transaction_index = required_u64_for(
        values,
        &format!("{prefix}transaction_index"),
        "postgres transaction detail",
    )?;
    let status = required_string_for(
        values,
        &format!("{prefix}status"),
        "postgres transaction detail",
    )?;
    let from_address = required_string_for(
        values,
        &format!("{prefix}from_address"),
        "postgres transaction detail",
    )?;
    let to_address = required_string_for(
        values,
        &format!("{prefix}to_address"),
        "postgres transaction detail",
    )?;
    let amount_base_units = required_string_for(
        values,
        &format!("{prefix}amount_base_units"),
        "postgres transaction detail",
    )?;
    let fee_base_units = required_string_for(
        values,
        &format!("{prefix}fee_base_units"),
        "postgres transaction detail",
    )?;
    let nonce = required_u64_for(
        values,
        &format!("{prefix}nonce"),
        "postgres transaction detail",
    )?;

    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(&mut output, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    writeln!(&mut output, "  \"tx_hash\": {},", json_string(tx_hash)).expect("write to String");
    writeln!(&mut output, "  \"block_height\": {},", block_height).expect("write to String");
    writeln!(
        &mut output,
        "  \"block_hash\": {},",
        json_string(block_hash)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"transaction_index\": {},",
        transaction_index
    )
    .expect("write to String");
    writeln!(&mut output, "  \"status\": {},", json_string(status)).expect("write to String");
    writeln!(
        &mut output,
        "  \"from_address\": {},",
        json_string(from_address)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"to_address\": {},",
        json_string(to_address)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"amount_base_units\": {},",
        json_string(amount_base_units)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"fee_base_units\": {},",
        json_string(fee_base_units)
    )
    .expect("write to String");
    write!(&mut output, "  \"nonce\": {}\n}}", nonce).expect("write to String");
    Ok(output)
}

fn render_postgres_wallet_transaction_status_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let prefix = "transaction_0_";
    let tx_hash = required_string_for(
        values,
        &format!("{prefix}tx_hash"),
        "postgres wallet transaction status",
    )?;
    let block_height = optional_u64_json_for(
        values,
        &format!("{prefix}block_height"),
        "postgres wallet transaction status",
    )?;
    let block_hash = optional_string_json(values, &format!("{prefix}block_hash"))?;
    let transaction_index = optional_u64_json_for(
        values,
        &format!("{prefix}transaction_index"),
        "postgres wallet transaction status",
    )?;
    let status = required_string_for(
        values,
        &format!("{prefix}status"),
        "postgres wallet transaction status",
    )?;

    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(&mut output, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    writeln!(&mut output, "  \"tx_hash\": {},", json_string(tx_hash)).expect("write to String");
    writeln!(&mut output, "  \"status\": {},", json_string(status)).expect("write to String");
    writeln!(&mut output, "  \"block_height\": {},", block_height).expect("write to String");
    writeln!(&mut output, "  \"block_hash\": {},", block_hash).expect("write to String");
    write!(
        &mut output,
        "  \"transaction_index\": {}\n}}",
        transaction_index
    )
    .expect("write to String");
    Ok(output)
}

fn render_postgres_iso20022_transaction_status_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let context = "postgres iso20022 transaction status";
    let prefix = "transaction_0_";
    let tx_hash = required_string_for(values, &format!("{prefix}tx_hash"), context)?;
    let confirmed_block_height =
        optional_u64_from_values(values, &format!("{prefix}confirmed_block_height"), context)?;
    let status = required_string_for(values, &format!("{prefix}status"), context)?;
    let from_address = required_string_for(values, &format!("{prefix}from_address"), context)?;
    let to_address = required_string_for(values, &format!("{prefix}to_address"), context)?;
    let amount_base_units =
        required_string_for(values, &format!("{prefix}amount_base_units"), context)?;
    let fee_base_units = required_string_for(values, &format!("{prefix}fee_base_units"), context)?;
    let nonce = required_u64_for(values, &format!("{prefix}nonce"), context)?;
    let transaction = XriqIsoTransaction {
        tx_hash: tx_hash.to_string(),
        confirmed_block_height,
        status: status.to_string(),
        from_address: from_address.to_string(),
        to_address: to_address.to_string(),
        amount_base_units: amount_base_units.to_string(),
        fee_base_units: fee_base_units.to_string(),
        nonce,
    };
    let preview = payment_status_preview(&transaction);

    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(
        &mut output,
        "  \"environment\": {},",
        json_string(preview.environment)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"read_model_warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    writeln!(
        &mut output,
        "  \"not_certified\": {},",
        preview.not_certified
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"mapping_version\": {},",
        json_string(preview.mapping_version)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"message_type\": {},",
        json_string(preview.message_type)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"message_id\": {},",
        json_string(&preview.message_id)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"source_tx_hash\": {},",
        json_string(&preview.source_tx_hash)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"xriq_status\": {},",
        json_string(&preview.xriq_status)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"iso20022_aligned\": {{").expect("write to String");
    writeln!(
        &mut output,
        "    \"original_end_to_end_id\": {},",
        json_string(&preview.iso20022_aligned.original_end_to_end_id)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"transaction_status\": {},",
        json_string(preview.iso20022_aligned.transaction_status)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"status_reason\": {},",
        json_string(preview.iso20022_aligned.status_reason)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"confirmed_block_height\": {}",
        json_optional_u64_value(preview.iso20022_aligned.confirmed_block_height)
    )
    .expect("write to String");
    writeln!(&mut output, "  }},").expect("write to String");
    write!(
        &mut output,
        "  \"unsupported_fields\": {}\n}}",
        json_borrowed_string_array(&preview.unsupported_fields)
    )
    .expect("write to String");
    Ok(output)
}

fn render_postgres_iso20022_payment_initiation_preview_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let context = "postgres iso20022 payment initiation preview";
    let prefix = "transaction_0_";
    let tx_hash = required_string_for(values, &format!("{prefix}tx_hash"), context)?;
    let confirmed_block_height =
        optional_u64_from_values(values, &format!("{prefix}confirmed_block_height"), context)?;
    let status = required_string_for(values, &format!("{prefix}status"), context)?;
    let from_address = required_string_for(values, &format!("{prefix}from_address"), context)?;
    let to_address = required_string_for(values, &format!("{prefix}to_address"), context)?;
    let amount_base_units =
        required_string_for(values, &format!("{prefix}amount_base_units"), context)?;
    let fee_base_units = required_string_for(values, &format!("{prefix}fee_base_units"), context)?;
    let nonce = required_u64_for(values, &format!("{prefix}nonce"), context)?;
    let transaction = XriqIsoTransaction {
        tx_hash: tx_hash.to_string(),
        confirmed_block_height,
        status: status.to_string(),
        from_address: from_address.to_string(),
        to_address: to_address.to_string(),
        amount_base_units: amount_base_units.to_string(),
        fee_base_units: fee_base_units.to_string(),
        nonce,
    };
    let preview = payment_initiation_preview(&transaction);

    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(
        &mut output,
        "  \"environment\": {},",
        json_string(preview.environment)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"read_model_warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    writeln!(
        &mut output,
        "  \"not_certified\": {},",
        preview.not_certified
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"mapping_version\": {},",
        json_string(preview.mapping_version)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"message_type\": {},",
        json_string(preview.message_type)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"message_id\": {},",
        json_string(&preview.message_id)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"source_tx_hash\": {},",
        json_string(&preview.source_tx_hash)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"xriq\": {{").expect("write to String");
    writeln!(
        &mut output,
        "    \"from_address\": {},",
        json_string(&preview.xriq.from_address)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"to_address\": {},",
        json_string(&preview.xriq.to_address)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"amount_base_units\": {},",
        json_string(&preview.xriq.amount_base_units)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"fee_base_units\": {},",
        json_string(&preview.xriq.fee_base_units)
    )
    .expect("write to String");
    writeln!(&mut output, "    \"nonce\": {}", preview.xriq.nonce).expect("write to String");
    writeln!(&mut output, "  }},").expect("write to String");
    writeln!(&mut output, "  \"iso20022_aligned\": {{").expect("write to String");
    writeln!(
        &mut output,
        "    \"creditor_account\": {},",
        json_string(&preview.iso20022_aligned.creditor_account)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"debtor_account\": {},",
        json_string(&preview.iso20022_aligned.debtor_account)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"instructed_amount\": {},",
        json_string(&preview.iso20022_aligned.instructed_amount)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"currency\": {},",
        json_string(preview.iso20022_aligned.currency)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"end_to_end_id\": {}",
        json_string(&preview.iso20022_aligned.end_to_end_id)
    )
    .expect("write to String");
    writeln!(&mut output, "  }},").expect("write to String");
    write!(
        &mut output,
        "  \"unsupported_fields\": {}\n}}",
        json_borrowed_string_array(&preview.unsupported_fields)
    )
    .expect("write to String");
    Ok(output)
}

fn render_postgres_iso20022_account_statement_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let context = "postgres iso20022 account statement";
    let address = required_string_for(values, "address", context)?;
    let from = required_string_for(values, "from", context)?;
    let to = required_string_for(values, "to", context)?;
    let closing_balance_base_units =
        required_string_for(values, "closing_balance_base_units", context)?;
    let transaction_count = required_u64_for(values, "transaction_count", context)?;
    let mut transactions = Vec::new();
    for index in 0..transaction_count {
        let prefix = format!("transaction_{index}_");
        transactions.push(XriqIsoAccountTransaction {
            tx_hash: required_string_for(values, &format!("{prefix}tx_hash"), context)?.to_string(),
            direction: required_string_for(values, &format!("{prefix}direction"), context)?
                .to_string(),
            block_height: required_u64_for(values, &format!("{prefix}block_height"), context)?,
            amount_base_units: required_string_for(
                values,
                &format!("{prefix}amount_base_units"),
                context,
            )?
            .to_string(),
            fee_base_units: required_string_for(
                values,
                &format!("{prefix}fee_base_units"),
                context,
            )?
            .to_string(),
        });
    }
    let opening_balance_base_units =
        postgres_statement_opening_balance(closing_balance_base_units, &transactions);
    let history = XriqIsoAccountHistory {
        address: address.to_string(),
        transactions,
    };
    let preview = account_statement_preview(
        &history,
        opening_balance_base_units,
        closing_balance_base_units.to_string(),
        from,
        to,
    );

    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(
        &mut output,
        "  \"environment\": {},",
        json_string(preview.environment)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"read_model_warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    writeln!(
        &mut output,
        "  \"not_certified\": {},",
        preview.not_certified
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"mapping_version\": {},",
        json_string(preview.mapping_version)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"message_type\": {},",
        json_string(preview.message_type)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"message_id\": {},",
        json_string(&preview.message_id)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"account_address\": {},",
        json_string(&preview.account_address)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"from\": {},", json_string(&preview.from)).expect("write to String");
    writeln!(&mut output, "  \"to\": {},", json_string(&preview.to)).expect("write to String");
    writeln!(
        &mut output,
        "  \"opening_balance_base_units\": {},",
        json_string(&preview.opening_balance_base_units)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"closing_balance_base_units\": {},",
        json_string(&preview.closing_balance_base_units)
    )
    .expect("write to String");
    output.push_str("  \"entries\": [");
    for (index, entry) in preview.entries.iter().enumerate() {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        let spaces = "    ";
        let nested = "      ";
        write!(
            &mut output,
            "{spaces}{{\n{nested}\"tx_hash\": {},\n{nested}\"direction\": {},\n{nested}\"amount_base_units\": {},\n{nested}\"fee_base_units\": {},\n{nested}\"status\": {},\n{nested}\"block_height\": {}\n{spaces}}}",
            json_string(&entry.tx_hash),
            json_string(entry.direction),
            json_string(&entry.amount_base_units),
            json_string(&entry.fee_base_units),
            json_string(entry.status),
            entry.block_height
        )
        .expect("write to String");
    }
    if !preview.entries.is_empty() {
        output.push('\n');
    }
    output.push_str("  ],\n");
    write!(
        &mut output,
        "  \"unsupported_fields\": {}\n}}",
        json_borrowed_string_array(&preview.unsupported_fields)
    )
    .expect("write to String");
    Ok(output)
}

fn postgres_statement_opening_balance(
    closing_balance_base_units: &str,
    transactions: &[XriqIsoAccountTransaction],
) -> String {
    let Some(mut opening) = closing_balance_base_units.parse::<u128>().ok() else {
        return closing_balance_base_units.to_string();
    };

    for transaction in transactions {
        let Some(amount) = transaction.amount_base_units.parse::<u128>().ok() else {
            return closing_balance_base_units.to_string();
        };
        let Some(fee) = transaction.fee_base_units.parse::<u128>().ok() else {
            return closing_balance_base_units.to_string();
        };
        match transaction.direction.as_str() {
            "sent" => {
                let Some(debit) = amount.checked_add(fee) else {
                    return closing_balance_base_units.to_string();
                };
                let Some(next_opening) = opening.checked_add(debit) else {
                    return closing_balance_base_units.to_string();
                };
                opening = next_opening;
            }
            "received" => {
                let Some(next_opening) = opening.checked_sub(amount) else {
                    return closing_balance_base_units.to_string();
                };
                opening = next_opening;
            }
            _ => {}
        }
    }

    opening.to_string()
}

fn render_postgres_transaction_json_inline(
    values: &BTreeMap<String, String>,
    index: u64,
    indent: usize,
) -> Result<String, String> {
    let prefix = format!("transaction_{index}_");
    let tx_hash =
        required_string_for(values, &format!("{prefix}tx_hash"), "postgres transactions")?;
    let block_height = required_u64_for(
        values,
        &format!("{prefix}block_height"),
        "postgres transactions",
    )?;
    let block_hash = required_string_for(
        values,
        &format!("{prefix}block_hash"),
        "postgres transactions",
    )?;
    let transaction_index = required_u64_for(
        values,
        &format!("{prefix}transaction_index"),
        "postgres transactions",
    )?;
    let status = required_string_for(values, &format!("{prefix}status"), "postgres transactions")?;
    let from_address = required_string_for(
        values,
        &format!("{prefix}from_address"),
        "postgres transactions",
    )?;
    let to_address = required_string_for(
        values,
        &format!("{prefix}to_address"),
        "postgres transactions",
    )?;
    let amount_base_units = required_string_for(
        values,
        &format!("{prefix}amount_base_units"),
        "postgres transactions",
    )?;
    let fee_base_units = required_string_for(
        values,
        &format!("{prefix}fee_base_units"),
        "postgres transactions",
    )?;
    let nonce = required_u64_for(values, &format!("{prefix}nonce"), "postgres transactions")?;
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    Ok(format!(
        "{spaces}{{\n{nested}\"tx_hash\": {},\n{nested}\"block_height\": {},\n{nested}\"block_hash\": {},\n{nested}\"transaction_index\": {},\n{nested}\"status\": {},\n{nested}\"from_address\": {},\n{nested}\"to_address\": {},\n{nested}\"amount_base_units\": {},\n{nested}\"fee_base_units\": {},\n{nested}\"nonce\": {}\n{spaces}}}",
        json_string(tx_hash),
        block_height,
        json_string(block_hash),
        transaction_index,
        json_string(status),
        json_string(from_address),
        json_string(to_address),
        json_string(amount_base_units),
        json_string(fee_base_units),
        nonce
    ))
}

fn render_postgres_mempool_entry_json_inline(
    values: &BTreeMap<String, String>,
    index: u64,
    indent: usize,
) -> Result<String, String> {
    let prefix = format!("mempool_entry_{index}_");
    let tx_hash = required_string_for(values, &format!("{prefix}tx_hash"), "postgres mempool")?;
    let from_address =
        required_string_for(values, &format!("{prefix}from_address"), "postgres mempool")?;
    let to_address =
        required_string_for(values, &format!("{prefix}to_address"), "postgres mempool")?;
    let amount_base_units = required_string_for(
        values,
        &format!("{prefix}amount_base_units"),
        "postgres mempool",
    )?;
    let fee_base_units = required_string_for(
        values,
        &format!("{prefix}fee_base_units"),
        "postgres mempool",
    )?;
    let nonce = required_u64_for(values, &format!("{prefix}nonce"), "postgres mempool")?;
    let status = required_string_for(values, &format!("{prefix}status"), "postgres mempool")?;
    let first_seen_at_utc = optional_string_json(values, &format!("{prefix}first_seen_at_utc"))?;
    let last_seen_at_utc = optional_string_json(values, &format!("{prefix}last_seen_at_utc"))?;
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    Ok(format!(
        "{spaces}{{\n{nested}\"tx_hash\": {},\n{nested}\"from_address\": {},\n{nested}\"to_address\": {},\n{nested}\"amount_base_units\": {},\n{nested}\"fee_base_units\": {},\n{nested}\"nonce\": {},\n{nested}\"status\": {},\n{nested}\"first_seen_at_utc\": {},\n{nested}\"last_seen_at_utc\": {}\n{spaces}}}",
        json_string(tx_hash),
        json_string(from_address),
        json_string(to_address),
        json_string(amount_base_units),
        json_string(fee_base_units),
        nonce,
        json_string(status),
        first_seen_at_utc,
        last_seen_at_utc
    ))
}

fn render_postgres_accounts_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let limit = required_u64_for(values, "limit", "postgres accounts")?;
    let account_count = required_u64_for(values, "account_count", "postgres accounts")?;
    let next_cursor = optional_string_json(values, "next_cursor")?;
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(&mut output, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    writeln!(&mut output, "  \"limit\": {},", limit).expect("write to String");
    writeln!(&mut output, "  \"next_cursor\": {},", next_cursor).expect("write to String");
    output.push_str("  \"accounts\": [");
    for index in 0..account_count {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_postgres_account_json_inline(values, index, 4)?);
    }
    if account_count > 0 {
        output.push('\n');
    }
    output.push_str("  ]\n}");
    Ok(output)
}

fn render_postgres_snapshots_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let limit = required_u64_for(values, "limit", "postgres snapshots")?;
    let snapshot_count = required_u64_for(values, "snapshot_count", "postgres snapshots")?;
    let next_cursor = optional_string_json(values, "next_cursor")?;
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(&mut output, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(SNAPSHOT_READONLY_WARNING)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"read_model_warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    writeln!(&mut output, "  \"limit\": {},", limit).expect("write to String");
    writeln!(&mut output, "  \"next_cursor\": {},", next_cursor).expect("write to String");
    output.push_str("  \"snapshots\": [");
    for index in 0..snapshot_count {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_postgres_snapshot_json_inline(values, index, 4)?);
    }
    if snapshot_count > 0 {
        output.push('\n');
    }
    output.push_str("  ]\n}");
    Ok(output)
}

fn render_postgres_snapshot_json_inline(
    values: &BTreeMap<String, String>,
    index: u64,
    indent: usize,
) -> Result<String, String> {
    let snapshot = render_postgres_snapshot_fields(values, index, "postgres snapshots")?;
    let spaces = " ".repeat(indent);
    let mut output = format!("{spaces}{{\n");
    write_postgres_snapshot_fields(&mut output, &snapshot, indent + 2, false);
    output.push('\n');
    output.push_str(&spaces);
    output.push('}');
    Ok(output)
}

fn render_postgres_snapshot_detail_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let snapshot = render_postgres_snapshot_fields(values, 0, "postgres snapshot detail")?;
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(&mut output, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(SNAPSHOT_READONLY_WARNING)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"read_model_warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    write_postgres_snapshot_fields(&mut output, &snapshot, 2, false);
    output.push_str("\n}");
    Ok(output)
}

struct PostgresSnapshotFields<'a> {
    snapshot_name: &'a str,
    snapshot_dir: &'a str,
    current_height: u64,
    latest_block_hash: &'a str,
    state_root: &'a str,
    block_count: u64,
    transaction_count: u64,
    audit_event_count: u64,
    export_status: &'a str,
    import_status: &'a str,
}

fn render_postgres_snapshot_fields<'a>(
    values: &'a BTreeMap<String, String>,
    index: u64,
    context: &str,
) -> Result<PostgresSnapshotFields<'a>, String> {
    let prefix = format!("snapshot_{index}_");
    Ok(PostgresSnapshotFields {
        snapshot_name: required_string_for(values, &format!("{prefix}snapshot_name"), context)?,
        snapshot_dir: required_string_for(values, &format!("{prefix}snapshot_dir"), context)?,
        current_height: required_u64_for(values, &format!("{prefix}current_height"), context)?,
        latest_block_hash: required_string_for(
            values,
            &format!("{prefix}latest_block_hash"),
            context,
        )?,
        state_root: required_string_for(values, &format!("{prefix}state_root"), context)?,
        block_count: required_u64_for(values, &format!("{prefix}block_count"), context)?,
        transaction_count: required_u64_for(
            values,
            &format!("{prefix}transaction_count"),
            context,
        )?,
        audit_event_count: required_u64_for(
            values,
            &format!("{prefix}audit_event_count"),
            context,
        )?,
        export_status: required_string_for(values, &format!("{prefix}export_status"), context)?,
        import_status: required_string_for(values, &format!("{prefix}import_status"), context)?,
    })
}

fn write_postgres_snapshot_fields(
    output: &mut String,
    snapshot: &PostgresSnapshotFields<'_>,
    indent: usize,
    trailing_comma: bool,
) {
    let spaces = " ".repeat(indent);
    writeln!(
        output,
        "{spaces}\"snapshot_name\": {},",
        json_string(snapshot.snapshot_name)
    )
    .expect("write to String");
    writeln!(
        output,
        "{spaces}\"snapshot_dir\": {},",
        json_string(snapshot.snapshot_dir)
    )
    .expect("write to String");
    writeln!(
        output,
        "{spaces}\"current_height\": {},",
        snapshot.current_height
    )
    .expect("write to String");
    writeln!(
        output,
        "{spaces}\"latest_block_hash\": {},",
        json_string(snapshot.latest_block_hash)
    )
    .expect("write to String");
    writeln!(
        output,
        "{spaces}\"state_root\": {},",
        json_string(snapshot.state_root)
    )
    .expect("write to String");
    writeln!(output, "{spaces}\"block_count\": {},", snapshot.block_count)
        .expect("write to String");
    writeln!(
        output,
        "{spaces}\"transaction_count\": {},",
        snapshot.transaction_count
    )
    .expect("write to String");
    writeln!(
        output,
        "{spaces}\"audit_event_count\": {},",
        snapshot.audit_event_count
    )
    .expect("write to String");
    writeln!(
        output,
        "{spaces}\"export_status\": {},",
        json_string(snapshot.export_status)
    )
    .expect("write to String");
    write!(
        output,
        "{spaces}\"import_status\": {}{}",
        json_string(snapshot.import_status),
        if trailing_comma { "," } else { "" }
    )
    .expect("write to String");
}

fn render_postgres_account_detail_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let account = render_postgres_account_fields(values, 0, "postgres account detail")?;
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(&mut output, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    write_postgres_account_fields(&mut output, &account, 2, false);
    output.push_str("\n}");
    Ok(output)
}

fn render_postgres_wallet_balance_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let account = render_postgres_account_fields(values, 0, "postgres wallet account balance")?;
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(&mut output, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    writeln!(
        &mut output,
        "  \"address\": {},",
        json_string(account.address)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"balance_base_units\": {},",
        json_string(account.balance_base_units)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"nonce\": {},", account.nonce).expect("write to String");
    writeln!(&mut output, "  \"height\": {},", account.height).expect("write to String");
    write!(
        &mut output,
        "  \"state_root\": {}\n}}",
        json_string(account.state_root)
    )
    .expect("write to String");
    Ok(output)
}

fn render_postgres_account_history_json(
    _config: &PostgresReadModelConfig<'_>,
    values: &BTreeMap<String, String>,
) -> Result<String, String> {
    let address = required_string_for(values, "address", "postgres account history")?;
    let limit = required_u64_for(values, "limit", "postgres account history")?;
    let transaction_count =
        required_u64_for(values, "transaction_count", "postgres account history")?;
    let next_cursor = optional_string_json(values, "next_cursor")?;
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(&mut output, "  \"environment\": \"private-devnet\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(POSTGRES_PRIVATE_DEVNET_NETWORK)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"source\": \"postgres-read-model\",").expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(POSTGRES_READ_MODEL_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"read_only\": true,").expect("write to String");
    writeln!(&mut output, "  \"address\": {},", json_string(address)).expect("write to String");
    writeln!(&mut output, "  \"limit\": {},", limit).expect("write to String");
    writeln!(&mut output, "  \"next_cursor\": {},", next_cursor).expect("write to String");
    output.push_str("  \"transactions\": [");
    for index in 0..transaction_count {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_postgres_account_transaction_json_inline(
            values, index, 4,
        )?);
    }
    if transaction_count > 0 {
        output.push('\n');
    }
    output.push_str("  ]\n}");
    Ok(output)
}

fn render_postgres_account_transaction_json_inline(
    values: &BTreeMap<String, String>,
    index: u64,
    indent: usize,
) -> Result<String, String> {
    let transaction =
        render_postgres_account_transaction_fields(values, index, "postgres account history")?;
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    Ok(format!(
        "{spaces}{{\n{nested}\"address\": {},\n{nested}\"tx_hash\": {},\n{nested}\"direction\": {},\n{nested}\"block_height\": {},\n{nested}\"transaction_index\": {},\n{nested}\"amount_base_units\": {},\n{nested}\"fee_base_units\": {}\n{spaces}}}",
        json_string(transaction.address),
        json_string(transaction.tx_hash),
        json_string(transaction.direction),
        transaction.block_height,
        transaction.transaction_index,
        json_string(transaction.amount_base_units),
        json_string(transaction.fee_base_units)
    ))
}

struct PostgresAccountTransactionFields<'a> {
    address: &'a str,
    tx_hash: &'a str,
    direction: &'a str,
    block_height: u64,
    transaction_index: u64,
    amount_base_units: &'a str,
    fee_base_units: &'a str,
}

fn render_postgres_account_transaction_fields<'a>(
    values: &'a BTreeMap<String, String>,
    index: u64,
    context: &str,
) -> Result<PostgresAccountTransactionFields<'a>, String> {
    let prefix = format!("transaction_{index}_");
    Ok(PostgresAccountTransactionFields {
        address: required_string_for(values, &format!("{prefix}address"), context)?,
        tx_hash: required_string_for(values, &format!("{prefix}tx_hash"), context)?,
        direction: required_string_for(values, &format!("{prefix}direction"), context)?,
        block_height: required_u64_for(values, &format!("{prefix}block_height"), context)?,
        transaction_index: required_u64_for(
            values,
            &format!("{prefix}transaction_index"),
            context,
        )?,
        amount_base_units: required_string_for(
            values,
            &format!("{prefix}amount_base_units"),
            context,
        )?,
        fee_base_units: required_string_for(values, &format!("{prefix}fee_base_units"), context)?,
    })
}

fn render_postgres_account_json_inline(
    values: &BTreeMap<String, String>,
    index: u64,
    indent: usize,
) -> Result<String, String> {
    let account = render_postgres_account_fields(values, index, "postgres accounts")?;
    let spaces = " ".repeat(indent);
    let mut output = format!("{spaces}{{\n");
    write_postgres_account_fields(&mut output, &account, indent + 2, false);
    output.push('\n');
    output.push_str(&spaces);
    output.push('}');
    Ok(output)
}

struct PostgresAccountFields<'a> {
    address: &'a str,
    balance_base_units: &'a str,
    nonce: u64,
    height: u64,
    state_root: &'a str,
    first_seen_height: String,
    last_seen_height: String,
}

fn render_postgres_account_fields<'a>(
    values: &'a BTreeMap<String, String>,
    index: u64,
    context: &str,
) -> Result<PostgresAccountFields<'a>, String> {
    let prefix = format!("account_{index}_");
    Ok(PostgresAccountFields {
        address: required_string_for(values, &format!("{prefix}address"), context)?,
        balance_base_units: required_string_for(
            values,
            &format!("{prefix}balance_base_units"),
            context,
        )?,
        nonce: required_u64_for(values, &format!("{prefix}nonce"), context)?,
        height: required_u64_for(values, &format!("{prefix}height"), context)?,
        state_root: required_string_for(values, &format!("{prefix}state_root"), context)?,
        first_seen_height: optional_u64_json_for(
            values,
            &format!("{prefix}first_seen_height"),
            context,
        )?,
        last_seen_height: optional_u64_json_for(
            values,
            &format!("{prefix}last_seen_height"),
            context,
        )?,
    })
}

fn write_postgres_account_fields(
    output: &mut String,
    account: &PostgresAccountFields<'_>,
    indent: usize,
    trailing_comma: bool,
) {
    let spaces = " ".repeat(indent);
    writeln!(
        output,
        "{spaces}\"address\": {},",
        json_string(account.address)
    )
    .expect("write to String");
    writeln!(
        output,
        "{spaces}\"balance_base_units\": {},",
        json_string(account.balance_base_units)
    )
    .expect("write to String");
    writeln!(output, "{spaces}\"nonce\": {},", account.nonce).expect("write to String");
    writeln!(output, "{spaces}\"height\": {},", account.height).expect("write to String");
    writeln!(
        output,
        "{spaces}\"state_root\": {},",
        json_string(account.state_root)
    )
    .expect("write to String");
    writeln!(
        output,
        "{spaces}\"first_seen_height\": {},",
        account.first_seen_height
    )
    .expect("write to String");
    write!(
        output,
        "{spaces}\"last_seen_height\": {}{}",
        account.last_seen_height,
        if trailing_comma { "," } else { "" }
    )
    .expect("write to String");
}

fn required_u64(values: &BTreeMap<String, String>, key: &str) -> Result<u64, String> {
    required_u64_for(values, key, "postgres read-model status")
}

fn required_u64_for(
    values: &BTreeMap<String, String>,
    key: &str,
    context: &str,
) -> Result<u64, String> {
    values
        .get(key)
        .ok_or_else(|| format!("{context}: missing {key}"))?
        .parse::<u64>()
        .map_err(|_| format!("{context}: invalid integer for {key}"))
}

fn required_u128_for(
    values: &BTreeMap<String, String>,
    key: &str,
    context: &str,
) -> Result<u128, String> {
    values
        .get(key)
        .ok_or_else(|| format!("{context}: missing {key}"))?
        .parse::<u128>()
        .map_err(|_| format!("{context}: invalid integer for {key}"))
}

fn required_string_for<'a>(
    values: &'a BTreeMap<String, String>,
    key: &str,
    context: &str,
) -> Result<&'a str, String> {
    values
        .get(key)
        .map(String::as_str)
        .ok_or_else(|| format!("{context}: missing {key}"))
}

fn optional_u64_json(values: &BTreeMap<String, String>, key: &str) -> Result<String, String> {
    optional_u64_json_for(values, key, "postgres read-model status")
}

fn optional_u64_json_for(
    values: &BTreeMap<String, String>,
    key: &str,
    context: &str,
) -> Result<String, String> {
    match values.get(key).map(String::as_str) {
        Some("none") | None => Ok("null".to_string()),
        Some(value) => value
            .parse::<u64>()
            .map(|number| number.to_string())
            .map_err(|_| format!("{context}: invalid integer for {key}")),
    }
}

fn optional_u64_from_values(
    values: &BTreeMap<String, String>,
    key: &str,
    context: &str,
) -> Result<Option<u64>, String> {
    match values.get(key).map(String::as_str) {
        Some("none") | None => Ok(None),
        Some(value) => value
            .parse::<u64>()
            .map(Some)
            .map_err(|_| format!("{context}: invalid integer for {key}")),
    }
}

fn optional_u128_from_values(
    values: &BTreeMap<String, String>,
    key: &str,
    context: &str,
) -> Result<Option<u128>, String> {
    match values.get(key).map(String::as_str) {
        Some("none") | None => Ok(None),
        Some(value) => value
            .parse::<u128>()
            .map(Some)
            .map_err(|_| format!("{context}: invalid integer for {key}")),
    }
}

fn optional_string_json(values: &BTreeMap<String, String>, key: &str) -> Result<String, String> {
    match values.get(key).map(String::as_str) {
        Some("none") | None => Ok("null".to_string()),
        Some(value) => Ok(json_string(value)),
    }
}

fn split_http_target(target: &str) -> (&str, Option<&str>) {
    target
        .split_once('?')
        .map_or((target, None), |(path, query)| (path, Some(query)))
}

fn limit_from_query(query: Option<&str>, default_limit: u64) -> Result<u64, String> {
    let Some(value) = query_param(query, "limit") else {
        return Ok(default_limit);
    };
    value
        .parse::<u64>()
        .map_err(|_| format!("invalid limit: {value}"))
}

fn query_param<'a>(query: Option<&'a str>, key: &str) -> Option<&'a str> {
    query?.split('&').find_map(|pair| {
        let (candidate, value) = pair.split_once('=')?;
        if candidate == key {
            Some(value)
        } else {
            None
        }
    })
}

fn required_query_param_any<'a>(query: Option<&'a str>, keys: &[&str]) -> Result<&'a str, String> {
    keys.iter()
        .find_map(|key| query_param(query, key))
        .ok_or_else(|| format!("missing required query parameter: {}", keys[0]))
}

fn iso_statement_time_param(
    query: Option<&str>,
    key: &str,
    default_value: &str,
) -> Result<String, String> {
    let value = query_param(query, key).unwrap_or(default_value);
    if !value.is_empty()
        && value.len() <= 64
        && value.chars().all(|character| {
            character.is_ascii_alphanumeric()
                || matches!(character, '-' | ':' | '.' | '+' | 'T' | 'Z')
        })
    {
        return Ok(value.to_string());
    }
    Err(format!("invalid {key}: expected ISO-like timestamp value"))
}

fn parse_u128_query(value: &str, key: &str) -> Result<u128, String> {
    value
        .parse::<u128>()
        .map_err(|_| format!("invalid {key}: {value}"))
}

fn parse_u64_query(value: &str, key: &str) -> Result<u64, String> {
    value
        .parse::<u64>()
        .map_err(|_| format!("invalid {key}: {value}"))
}

fn optional_u16_query(query: Option<&str>, key: &str) -> Result<Option<u16>, String> {
    let Some(value) = query_param(query, key) else {
        return Ok(None);
    };
    value
        .parse::<u16>()
        .map(Some)
        .map_err(|_| format!("invalid {key}: {value}"))
}

fn help_text() -> String {
    [
        "xriq-api private-devnet commands:",
        "  xriq-api request --chain-file <path> [--pending-file <path>] [--alice-balance <base-units>] [--method GET|POST] [--enable-local-wallet-submit true] [--enable-local-wallet-send true] [--enable-local-wallet-submit-signed true] [--enable-local-block-production true] --target <api-path>",
        "  xriq-api request-postgres [--docker-container xriq-postgres] [--database xriq_phase1_1_smoke] [--method GET] --target /api/v1/admin/postgres/read-model-status|/api/v1/admin/node/status|/api/v1/admin/indexer/status|/api/v1/admin/audit-events?limit=5|/api/v1/explorer/overview|/api/v1/blocks?limit=5|/api/v1/blocks/<height-or-hash>|/api/v1/transactions?limit=5|/api/v1/mempool?limit=5|/api/v1/wallet/status|/api/v1/wallet/transfers/draft-preview?...|/api/v1/transactions/<tx_hash>|/api/v1/wallet/transactions/<tx_hash>/status|/api/v1/iso20022/transactions/<tx_hash>/status|/api/v1/iso20022/payment-initiation/preview?tx_hash=<tx_hash>|/api/v1/iso20022/accounts/<address>/statement?from=...&to=...|/api/v1/accounts?limit=5|/api/v1/accounts/<address>|/api/v1/accounts/<address>/transactions?limit=5|/api/v1/wallet/accounts?limit=5|/api/v1/wallet/accounts/<address>/balance|/api/v1/wallet/accounts/<address>/history?limit=5|/api/v1/snapshots?limit=5|/api/v1/snapshots/<snapshot_name>",
        "  xriq-api serve-readonly --chain-file <path> [--pending-file <path>] [--alice-balance <base-units>] [--bind 127.0.0.1:8090] [--enable-local-wallet-submit true] [--enable-local-wallet-send true] [--enable-local-wallet-submit-signed true] [--enable-local-block-production true] [--postgres-docker-container <container> --postgres-database <database>]",
        "",
        "Examples:",
        "  xriq-api request --chain-file target/xriq-devnet.bin --alice-balance 100 --target /api/v1/health",
        "  xriq-api request --chain-file target/xriq-devnet.bin --pending-file target/xriq-devnet-pending.tsv --alice-balance 100 --method POST --enable-local-wallet-submit true --target /api/v1/wallet/transfers/submit?local_request_id=local-1&draft_id=draft-1&from_address=xriqdev1alice00000000000&to_address=xriqdev1carol00000000000&amount_base_units=5&fee_base_units=2&nonce=0&expires_at_height=100",
        "  xriq-api request --chain-file target/xriq-devnet.bin --pending-file target/xriq-devnet-pending.tsv --alice-balance 100 --method POST --enable-local-wallet-send true --target /api/v1/wallet/transfers/send?local_request_id=local-1&from_address=xriqdev1alice00000000000&to_address=xriqdev1carol00000000000&amount_base_units=5&fee_base_units=2&nonce=0&expires_at_height=100",
        "  xriq-api request --chain-file target/xriq-devnet.bin --pending-file target/xriq-devnet-pending.tsv --alice-balance 100 --method POST --enable-local-wallet-submit-signed true --target /api/v1/wallet/transfers/submit-signed?local_request_id=local-1&format_version=xriq-local-signed-transfer-envelope-v1&version=1&chain_id=xriq-devnet&from_address=xriqdev1alice00000000000&to_address=xriqdev1carol00000000000&amount_base_units=5&fee_base_units=2&nonce=1&expires_at_height=100&transaction_signing_hash=<hash>&transaction_hash=<hash>&signature_algorithm=test-only&signature_encoding=test-only-prefix-plus-signing-hash",
        "  xriq-api request --chain-file target/xriq-devnet.bin --pending-file target/xriq-devnet-pending.tsv --alice-balance 100 --method POST --enable-local-block-production true --target /api/v1/blocks/produce?local_request_id=local-1&producer=xriqdev1author00000000000&max_transactions=4&timestamp_ms=2000",
        "  xriq-api request-postgres --target /api/v1/admin/postgres/read-model-status",
        "  xriq-api request-postgres --target /api/v1/admin/node/status",
        "  xriq-api request-postgres --target /api/v1/admin/indexer/status",
        "  xriq-api request-postgres --target /api/v1/admin/audit-events?limit=5",
        "  xriq-api request-postgres --target /api/v1/explorer/overview",
        "  xriq-api request-postgres --target /api/v1/blocks?limit=5",
        "  xriq-api request-postgres --target /api/v1/blocks/1",
        "  xriq-api request-postgres --target /api/v1/transactions?limit=5",
        "  xriq-api request-postgres --target /api/v1/mempool?limit=5",
        "  xriq-api request-postgres --target /api/v1/wallet/status",
        "  xriq-api request-postgres --target /api/v1/wallet/transfers/draft-preview?from_address=xriqdev1alice00000000000&to_address=xriqdev1carol00000000000&amount_base_units=5&fee_base_units=2&nonce=1&expires_at_height=100",
        "  xriq-api request-postgres --target /api/v1/transactions/<tx_hash>",
        "  xriq-api request-postgres --target /api/v1/wallet/transactions/<tx_hash>/status",
        "  xriq-api request-postgres --target /api/v1/iso20022/transactions/<tx_hash>/status",
        "  xriq-api request-postgres --target /api/v1/iso20022/payment-initiation/preview?tx_hash=<tx_hash>",
        "  xriq-api request-postgres --target /api/v1/iso20022/accounts/<address>/statement?from=1970-01-01T00:00:00Z&to=1970-01-01T00:00:02Z",
        "  xriq-api request-postgres --target /api/v1/accounts?limit=5",
        "  xriq-api request-postgres --target /api/v1/accounts/<address>",
        "  xriq-api request-postgres --target /api/v1/accounts/<address>/transactions?limit=5",
        "  xriq-api request-postgres --target /api/v1/wallet/accounts?limit=5",
        "  xriq-api request-postgres --target /api/v1/wallet/accounts/<address>/balance",
        "  xriq-api request-postgres --target /api/v1/wallet/accounts/<address>/history?limit=5",
        "  xriq-api request-postgres --target /api/v1/snapshots?limit=5",
        "  xriq-api request-postgres --target /api/v1/snapshots/current-indexed-chain",
        "  xriq-api serve-readonly --chain-file target/xriq-devnet.bin --alice-balance 100",
        "  xriq-api serve-readonly --chain-file target/xriq-devnet.bin --alice-balance 100 --postgres-docker-container xriq-postgres --postgres-database xriq_phase1_1_smoke",
    ]
    .join("\n")
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct RequestConfig<'a> {
    chain_file: &'a str,
    pending_file: Option<&'a str>,
    alice_balance: Option<XriqAmount>,
    method: &'a str,
    target: &'a str,
    enable_local_wallet_submit: bool,
    enable_local_wallet_send: bool,
    enable_local_wallet_signed_submit: bool,
    enable_local_block_production: bool,
}

impl<'a> RequestConfig<'a> {
    fn parse(args: &'a [&'a str]) -> Result<Self, String> {
        let flags = FlagParser::parse(args)?;
        flags.reject_unknown(&[
            "--chain-file",
            "--pending-file",
            "--alice-balance",
            "--method",
            "--target",
            "--enable-local-wallet-submit",
            "--enable-local-wallet-send",
            "--enable-local-wallet-submit-signed",
            "--enable-local-block-production",
        ])?;
        Ok(Self {
            chain_file: flags.required("--chain-file")?,
            pending_file: flags.optional("--pending-file"),
            alice_balance: flags
                .optional("--alice-balance")
                .map(parse_amount)
                .transpose()?,
            method: flags.optional("--method").unwrap_or("GET"),
            target: flags.required("--target")?,
            enable_local_wallet_submit: flags
                .optional("--enable-local-wallet-submit")
                .map(|value| parse_bool_flag("--enable-local-wallet-submit", value))
                .transpose()?
                .unwrap_or(false),
            enable_local_wallet_send: flags
                .optional("--enable-local-wallet-send")
                .map(|value| parse_bool_flag("--enable-local-wallet-send", value))
                .transpose()?
                .unwrap_or(false),
            enable_local_wallet_signed_submit: flags
                .optional("--enable-local-wallet-submit-signed")
                .map(|value| parse_bool_flag("--enable-local-wallet-submit-signed", value))
                .transpose()?
                .unwrap_or(false),
            enable_local_block_production: flags
                .optional("--enable-local-block-production")
                .map(|value| parse_bool_flag("--enable-local-block-production", value))
                .transpose()?
                .unwrap_or(false),
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct PostgresRequestConfig<'a> {
    read_model: PostgresReadModelConfig<'a>,
    method: &'a str,
    target: &'a str,
}

impl<'a> PostgresRequestConfig<'a> {
    fn parse(args: &'a [&'a str]) -> Result<Self, String> {
        let flags = FlagParser::parse(args)?;
        flags.reject_unknown(&["--docker-container", "--database", "--method", "--target"])?;
        let docker_container = flags
            .optional("--docker-container")
            .unwrap_or("xriq-postgres");
        let database = flags
            .optional("--database")
            .unwrap_or("xriq_phase1_1_smoke");
        Ok(Self {
            read_model: PostgresReadModelConfig::new(docker_container, database)?,
            method: flags.optional("--method").unwrap_or("GET"),
            target: flags.required("--target")?,
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct PostgresReadModelConfig<'a> {
    docker_container: &'a str,
    database: &'a str,
}

impl<'a> PostgresReadModelConfig<'a> {
    fn new(docker_container: &'a str, database: &'a str) -> Result<Self, String> {
        validate_docker_name(docker_container, "docker container")?;
        validate_postgres_identifier(database, "postgres database")?;
        Ok(Self {
            docker_container,
            database,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct PostgresWalletDraftPreviewRequest<'a> {
    chain_id: &'a str,
    from_address: &'a str,
    to_address: &'a str,
    amount_base_units: u128,
    fee_base_units: u128,
    nonce: u64,
    expires_at_height: Option<u64>,
}

impl<'a> PostgresWalletDraftPreviewRequest<'a> {
    fn from_query(query: Option<&'a str>) -> Result<Self, String> {
        let chain_id = query_param(query, "chain_id").unwrap_or(POSTGRES_PRIVATE_DEVNET_NETWORK);
        if chain_id != POSTGRES_PRIVATE_DEVNET_NETWORK {
            return Err(format!(
                "chain_id must be {POSTGRES_PRIVATE_DEVNET_NETWORK}"
            ));
        }

        let from_address = required_query_param_any(query, &["from_address", "from"])?;
        let to_address = required_query_param_any(query, &["to_address", "to"])?;
        Address::parse(from_address).map_err(|error| {
            format!(
                "invalid from_address: {from_address}; expected private-devnet address ({error:?})"
            )
        })?;
        Address::parse(to_address).map_err(|error| {
            format!("invalid to_address: {to_address}; expected private-devnet address ({error:?})")
        })?;

        Ok(Self {
            chain_id,
            from_address,
            to_address,
            amount_base_units: parse_u128_query(
                required_query_param_any(query, &["amount_base_units", "amount"])?,
                "amount_base_units",
            )?,
            fee_base_units: parse_u128_query(
                required_query_param_any(query, &["fee_base_units", "fee"])?,
                "fee_base_units",
            )?,
            nonce: parse_u64_query(required_query_param_any(query, &["nonce"])?, "nonce")?,
            expires_at_height: query_param(query, "expires_at_height")
                .map(|value| parse_u64_query(value, "expires_at_height"))
                .transpose()?,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ServeConfig<'a> {
    chain_file: &'a str,
    pending_file: Option<&'a str>,
    alice_balance: Option<XriqAmount>,
    bind: &'a str,
    postgres_read_model: Option<PostgresReadModelConfig<'a>>,
    enable_local_wallet_submit: bool,
    enable_local_wallet_send: bool,
    enable_local_wallet_signed_submit: bool,
    enable_local_block_production: bool,
}

impl<'a> ServeConfig<'a> {
    fn parse(args: &'a [&'a str]) -> Result<Self, String> {
        let flags = FlagParser::parse(args)?;
        flags.reject_unknown(&[
            "--chain-file",
            "--pending-file",
            "--alice-balance",
            "--bind",
            "--enable-local-wallet-submit",
            "--enable-local-wallet-send",
            "--enable-local-wallet-submit-signed",
            "--enable-local-block-production",
            "--postgres-docker-container",
            "--postgres-database",
        ])?;
        let postgres_read_model = match (
            flags.optional("--postgres-docker-container"),
            flags.optional("--postgres-database"),
        ) {
            (None, None) => None,
            (Some(docker_container), Some(database)) => {
                Some(PostgresReadModelConfig::new(docker_container, database)?)
            }
            (Some(_), None) => {
                return Err(
                    "missing required flag when enabling Postgres read model: --postgres-database"
                        .to_string(),
                );
            }
            (None, Some(_)) => {
                return Err(
                    "missing required flag when enabling Postgres read model: --postgres-docker-container"
                        .to_string(),
                );
            }
        };
        Ok(Self {
            chain_file: flags.required("--chain-file")?,
            pending_file: flags.optional("--pending-file"),
            alice_balance: flags
                .optional("--alice-balance")
                .map(parse_amount)
                .transpose()?,
            bind: flags.optional("--bind").unwrap_or(DEFAULT_BIND),
            postgres_read_model,
            enable_local_wallet_submit: flags
                .optional("--enable-local-wallet-submit")
                .map(|value| parse_bool_flag("--enable-local-wallet-submit", value))
                .transpose()?
                .unwrap_or(false),
            enable_local_wallet_send: flags
                .optional("--enable-local-wallet-send")
                .map(|value| parse_bool_flag("--enable-local-wallet-send", value))
                .transpose()?
                .unwrap_or(false),
            enable_local_wallet_signed_submit: flags
                .optional("--enable-local-wallet-submit-signed")
                .map(|value| parse_bool_flag("--enable-local-wallet-submit-signed", value))
                .transpose()?
                .unwrap_or(false),
            enable_local_block_production: flags
                .optional("--enable-local-block-production")
                .map(|value| parse_bool_flag("--enable-local-block-production", value))
                .transpose()?
                .unwrap_or(false),
        })
    }
}

fn parse_bool_flag(flag: &'static str, value: &str) -> Result<bool, String> {
    match value {
        "true" | "1" | "yes" => Ok(true),
        "false" | "0" | "no" => Ok(false),
        _ => Err(format!("{flag} must be true or false, got {value:?}")),
    }
}

fn parse_amount(value: &str) -> Result<XriqAmount, String> {
    let base_units = value
        .parse::<u128>()
        .map_err(|_| format!("invalid amount: {value}"))?;
    Ok(XriqAmount::from_base_units(base_units))
}

fn validate_postgres_identifier(value: &str, context: &str) -> Result<(), String> {
    if value
        .chars()
        .next()
        .is_some_and(|character| character.is_ascii_alphabetic() || character == '_')
        && value.len() <= 63
        && value
            .chars()
            .all(|character| character.is_ascii_alphanumeric() || character == '_')
    {
        return Ok(());
    }
    Err(format!(
        "{context}: expected letters, digits, and underscores only, got {value:?}"
    ))
}

fn validate_docker_name(value: &str, context: &str) -> Result<(), String> {
    if !value.is_empty()
        && value.len() <= 128
        && value.chars().all(|character| {
            character.is_ascii_alphanumeric()
                || character == '_'
                || character == '-'
                || character == '.'
        })
    {
        return Ok(());
    }
    Err(format!(
        "{context}: expected Docker name characters only, got {value:?}"
    ))
}

fn validate_transaction_hash(value: &str, context: &str) -> Result<(), String> {
    if value.len() == 64 && value.chars().all(|character| character.is_ascii_hexdigit()) {
        return Ok(());
    }
    Err(format!(
        "invalid {context}: expected 64-character hex string, got {value:?}"
    ))
}

fn validate_block_identifier(value: &str, context: &str) -> Result<(), String> {
    if is_postgres_block_height_identifier(value) {
        return Ok(());
    }
    validate_transaction_hash(value, context)
}

fn is_postgres_block_height_identifier(value: &str) -> bool {
    value
        .parse::<i64>()
        .map(|height| height >= 0)
        .unwrap_or(false)
}

fn validate_xriq_address(value: &str, context: &str) -> Result<(), String> {
    Address::parse(value)
        .map(|_| ())
        .map_err(|error| format!("invalid {context}: {error:?}, got {value:?}"))
}

fn validate_snapshot_name(value: &str, context: &str) -> Result<(), String> {
    if !value.is_empty()
        && value.len() <= 128
        && value.chars().all(|character| {
            character.is_ascii_alphanumeric() || matches!(character, '-' | '_' | '.')
        })
    {
        return Ok(());
    }
    Err(format!(
        "invalid {context}: expected letters, digits, dash, underscore, or dot, got {value:?}"
    ))
}

fn json_string(value: &str) -> String {
    let mut output = String::with_capacity(value.len() + 2);
    output.push('"');
    for character in value.chars() {
        match character {
            '"' => output.push_str("\\\""),
            '\\' => output.push_str("\\\\"),
            '\n' => output.push_str("\\n"),
            '\r' => output.push_str("\\r"),
            '\t' => output.push_str("\\t"),
            '\u{08}' => output.push_str("\\b"),
            '\u{0c}' => output.push_str("\\f"),
            character if character < '\u{20}' => {
                write!(&mut output, "\\u{:04x}", character as u32).expect("write to String");
            }
            character => output.push(character),
        }
    }
    output.push('"');
    output
}

fn json_optional_u64_value(value: Option<u64>) -> String {
    value
        .map(|number| number.to_string())
        .unwrap_or_else(|| "null".to_string())
}

fn json_optional_u128_string(value: Option<u128>) -> String {
    value
        .map(|number| json_string(&number.to_string()))
        .unwrap_or_else(|| "null".to_string())
}

fn json_string_array(values: &[String]) -> String {
    let mut output = String::from("[");
    for (index, value) in values.iter().enumerate() {
        if index > 0 {
            output.push_str(", ");
        }
        output.push_str(&json_string(value));
    }
    output.push(']');
    output
}

fn json_borrowed_string_array(values: &[&str]) -> String {
    let mut output = String::from("[");
    for (index, value) in values.iter().enumerate() {
        if index > 0 {
            output.push_str(", ");
        }
        output.push_str(&json_string(value));
    }
    output.push(']');
    output
}

fn hash_hex(hash: Hash32) -> String {
    let mut output = String::with_capacity(64);
    for byte in hash.as_bytes() {
        write!(&mut output, "{byte:02x}").expect("write to String");
    }
    output
}

fn timestamp_ms_to_utc(timestamp_ms: u64) -> String {
    let seconds = timestamp_ms / 1000;
    let days = seconds / 86_400;
    let seconds_of_day = seconds % 86_400;
    let (year, month, day) = civil_from_days(days as i64);
    let hour = seconds_of_day / 3_600;
    let minute = (seconds_of_day % 3_600) / 60;
    let second = seconds_of_day % 60;
    format!("{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}Z")
}

fn civil_from_days(days_since_unix_epoch: i64) -> (i64, u32, u32) {
    let z = days_since_unix_epoch + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let day_of_era = z - era * 146_097;
    let year_of_era =
        (day_of_era - day_of_era / 1_460 + day_of_era / 36_524 - day_of_era / 146_096) / 365;
    let year = year_of_era + era * 400;
    let day_of_year = day_of_era - (365 * year_of_era + year_of_era / 4 - year_of_era / 100);
    let month_prime = (5 * day_of_year + 2) / 153;
    let day = day_of_year - (153 * month_prime + 2) / 5 + 1;
    let month = month_prime + if month_prime < 10 { 3 } else { -9 };
    let year = year + if month <= 2 { 1 } else { 0 };
    (year, month as u32, day as u32)
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct FlagParser<'a> {
    pairs: Vec<(&'a str, &'a str)>,
}

impl<'a> FlagParser<'a> {
    fn parse(args: &'a [&'a str]) -> Result<Self, String> {
        let mut pairs = Vec::new();
        let mut index = 0;
        while index < args.len() {
            let flag = args[index];
            if !flag.starts_with("--") {
                return Err(format!("unexpected argument: {flag}"));
            }
            let value = args
                .get(index + 1)
                .ok_or_else(|| format!("missing required flag value: {flag}"))?;
            if value.starts_with("--") {
                return Err(format!("missing required flag value: {flag}"));
            }
            if pairs
                .iter()
                .any(|(existing_flag, _)| existing_flag == &flag)
            {
                return Err(format!("duplicate flag: {flag}"));
            }
            pairs.push((flag, *value));
            index += 2;
        }
        Ok(Self { pairs })
    }

    fn required(&self, flag: &str) -> Result<&'a str, String> {
        self.optional(flag)
            .ok_or_else(|| format!("missing required flag: {flag}"))
    }

    fn optional(&self, flag: &str) -> Option<&'a str> {
        self.pairs
            .iter()
            .find(|(candidate, _)| candidate == &flag)
            .map(|(_, value)| *value)
    }

    fn reject_unknown(&self, allowed: &[&str]) -> Result<(), String> {
        for (flag, _) in &self.pairs {
            if !allowed.iter().any(|allowed_flag| allowed_flag == flag) {
                return Err(format!("unknown flag: {flag}"));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_store_path(label: &str) -> std::path::PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("xriq-api-{label}-{nanos}.bin"))
    }

    fn pending_transfer_body() -> String {
        [
            "warning=private-devnet-test-identity-only",
            "version=1",
            "chain_id=xriq-devnet",
            "from=xriqdev1alice00000000000",
            "to=xriqdev1bobbb00000000000",
            "amount=25",
            "fee=2",
            "nonce=0",
            "expires_at_height=100",
            "signature_bytes=48",
        ]
        .join("\n")
    }

    fn wallet_submit_target(local_request_id: &str, draft_id: &str, from_address: &str) -> String {
        format!(
            "/api/v1/wallet/transfers/submit?local_request_id={local_request_id}&draft_id={draft_id}&from_address={from_address}&to_address=xriqdev1carol00000000000&amount_base_units=5&fee_base_units=2&nonce=0&expires_at_height=100"
        )
    }

    fn wallet_signed_submit_target(local_request_id: &str) -> String {
        format!(
            "/api/v1/wallet/transfers/submit-signed?local_request_id={local_request_id}&transaction_signing_hash=3c0f7f54bca53ad4c49ff98ba9ba2930ac6147a3cb510ead3265c894fcf1850b&transaction_hash=628ac2587bbae121654089ffb42cd1e2b1a59384c8e9b9206c925873783d40f7&signature_algorithm=xriq-dev-test-only"
        )
    }

    fn wallet_signed_submit_preview_target(local_request_id: &str) -> String {
        format!(
            "/api/v1/wallet/transfers/submit-signed?local_request_id={local_request_id}&format_version=xriq-local-signed-transfer-envelope-v1&version=1&chain_id=xriq-devnet&from_address=xriqdev1alice00000000000&to_address=xriqdev1carol00000000000&amount_base_units=5&fee_base_units=2&nonce=1&expires_at_height=100&transaction_signing_hash=3c0f7f54bca53ad4c49ff98ba9ba2930ac6147a3cb510ead3265c894fcf1850b&transaction_hash=628ac2587bbae121654089ffb42cd1e2b1a59384c8e9b9206c925873783d40f7&signature_algorithm=test-only&signature_encoding=test-only-prefix-plus-signing-hash"
        )
    }

    fn wallet_send_target(local_request_id: &str, from_address: &str) -> String {
        format!(
            "/api/v1/wallet/transfers/send?local_request_id={local_request_id}&from_address={from_address}&to_address=xriqdev1carol00000000000&amount_base_units=5&fee_base_units=2&nonce=0&expires_at_height=100"
        )
    }

    fn confirmed_signed_submit_preview_service(
        label: &str,
    ) -> (std::path::PathBuf, std::path::PathBuf, XriqApiService) {
        let path = temp_store_path(label);
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        xriq_node::private_devnet_file_submit_pending_transfer_body(
            &path_text,
            &pending_text,
            Some(XriqAmount::from_base_units(100)),
            &pending_transfer_body(),
        )
        .unwrap();
        xriq_node::private_devnet_file_produce_pending_block(
            &path_text,
            &pending_text,
            Some(XriqAmount::from_base_units(100)),
            2_000,
            0,
        )
        .unwrap();
        let service = build_service(
            &path_text,
            Some(&pending_text),
            Some(XriqAmount::from_base_units(100)),
        )
        .unwrap();
        (path, pending_path, service)
    }

    #[test]
    fn request_config_defaults_to_get_and_requires_target() {
        let config = RequestConfig::parse(&[
            "--chain-file",
            "target/xriq.bin",
            "--alice-balance",
            "100",
            "--target",
            "/api/v1/health",
        ])
        .unwrap();

        assert_eq!(config.chain_file, "target/xriq.bin");
        assert_eq!(config.pending_file, None);
        assert_eq!(config.alice_balance.unwrap().base_units(), 100);
        assert_eq!(config.method, "GET");
        assert_eq!(config.target, "/api/v1/health");
        assert!(!config.enable_local_wallet_submit);
        assert!(!config.enable_local_wallet_send);
        assert!(!config.enable_local_wallet_signed_submit);
        assert!(!config.enable_local_block_production);

        let error = RequestConfig::parse(&["--chain-file", "target/xriq.bin"]).unwrap_err();
        assert!(error.contains("missing required flag: --target"));

        let wallet_enabled = RequestConfig::parse(&[
            "--chain-file",
            "target/xriq.bin",
            "--target",
            "/api/v1/wallet/transfers/submit",
            "--enable-local-wallet-submit",
            "true",
        ])
        .unwrap();
        assert!(wallet_enabled.enable_local_wallet_submit);

        let wallet_send_enabled = RequestConfig::parse(&[
            "--chain-file",
            "target/xriq.bin",
            "--target",
            "/api/v1/wallet/transfers/send",
            "--enable-local-wallet-send",
            "true",
        ])
        .unwrap();
        assert!(wallet_send_enabled.enable_local_wallet_send);

        let wallet_signed_submit_enabled = RequestConfig::parse(&[
            "--chain-file",
            "target/xriq.bin",
            "--target",
            "/api/v1/wallet/transfers/submit-signed",
            "--enable-local-wallet-submit-signed",
            "true",
        ])
        .unwrap();
        assert!(wallet_signed_submit_enabled.enable_local_wallet_signed_submit);

        let enabled = RequestConfig::parse(&[
            "--chain-file",
            "target/xriq.bin",
            "--target",
            "/api/v1/blocks/produce",
            "--enable-local-block-production",
            "true",
        ])
        .unwrap();
        assert!(enabled.enable_local_block_production);
    }

    #[test]
    fn local_wallet_submit_request_requires_explicit_enablement() {
        let path = temp_store_path("disabled-wallet-submit");
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        FileChainStore::open(&path).unwrap();
        let target = wallet_submit_target(
            "local-wallet-disabled",
            "draft-wallet-disabled",
            PRIVATE_DEVNET_TEST_SENDER,
        );

        let response = run([
            "request",
            "--chain-file",
            &path_text,
            "--pending-file",
            &pending_text,
            "--alice-balance",
            "100",
            "--method",
            "POST",
            "--target",
            &target,
        ])
        .unwrap();

        assert!(response.contains("status_code=403"));
        assert!(response.contains("\"code\": \"wallet_submit_disabled\""));
        assert!(!pending_path.exists());

        let _ = fs::remove_file(path);
    }

    #[test]
    fn local_wallet_signed_submit_request_requires_explicit_enablement() {
        let path = temp_store_path("disabled-wallet-signed-submit");
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        FileChainStore::open(&path).unwrap();
        let target = wallet_signed_submit_target("local-signed-submit-disabled");

        let response = run([
            "request",
            "--chain-file",
            &path_text,
            "--pending-file",
            &pending_text,
            "--alice-balance",
            "100",
            "--method",
            "POST",
            "--target",
            &target,
        ])
        .unwrap();

        assert!(response.contains("status_code=403"));
        assert!(response.contains("\"code\": \"signed_submit_disabled\""));
        assert!(response.contains("\"endpoint\": \"POST /api/v1/wallet/transfers/submit-signed\""));
        assert!(response.contains("\"explicit_flag\": \"--enable-local-wallet-submit-signed\""));
        assert!(
            response.contains("\"event_id\": \"wallet-transfer-signed-submit:local_request_id\"")
        );
        assert!(response.contains("\"mutation\": \"none\""));
        assert!(response.contains("test-only signed-submit verifier is not enabled"));
        assert!(response.contains("pending state is not changed"));
        assert!(response.contains("chain state is not changed"));
        assert!(!response.contains("private_key"));
        assert!(!response.contains("seed_phrase"));
        assert!(!response.contains("mnemonic"));
        assert!(!pending_path.exists());

        let _ = fs::remove_file(path);
    }

    #[test]
    fn local_wallet_signed_submit_preview_adapter_verifies_fixture_without_mutation() {
        let (path, pending_path, service) =
            confirmed_signed_submit_preview_service("signed-submit-preview");
        assert_eq!(service.snapshot().current_height, 1);
        assert_eq!(
            service.account("xriqdev1alice00000000000").unwrap().nonce,
            1
        );
        assert_eq!(service.mempool(usize::MAX).pending_count, 0);
        let target = wallet_signed_submit_preview_target("local-signed-submit-preview");
        let (_, query) = split_http_target(&target);
        let request = LocalWalletSignedSubmitPreviewRequest::from_query(query).unwrap();

        let verified = request.verify_preview(&service).unwrap();

        assert_eq!(request.local_request_id, "local-signed-submit-preview");
        assert_eq!(verified.endpoint, SIGNED_SUBMIT_ENDPOINT);
        assert_eq!(verified.status, "verified");
        assert_eq!(verified.mutation, "none");
        assert_eq!(
            verified.signature_algorithm,
            SIGNED_SUBMIT_TEST_SIGNATURE_ALGORITHM
        );
        assert_eq!(verified.verifier, SIGNED_SUBMIT_TEST_VERIFIER);
        assert!(verified.verified);
        assert_eq!(
            verified.transaction_signing_hash,
            "3c0f7f54bca53ad4c49ff98ba9ba2930ac6147a3cb510ead3265c894fcf1850b"
        );
        assert_eq!(
            verified.transaction_hash,
            "628ac2587bbae121654089ffb42cd1e2b1a59384c8e9b9206c925873783d40f7"
        );
        assert_eq!(service.mempool(usize::MAX).pending_count, 0);

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn local_wallet_signed_submit_preview_adapter_returns_refusals_without_mutation() {
        let (path, pending_path, service) =
            confirmed_signed_submit_preview_service("signed-submit-preview-refusals");
        let target = wallet_signed_submit_preview_target("local-signed-submit-preview-refusal");

        let missing_format =
            target.replace("format_version=xriq-local-signed-transfer-envelope-v1&", "");
        let (_, missing_format_query) = split_http_target(&missing_format);
        let missing_format_request =
            LocalWalletSignedSubmitPreviewRequest::from_query(missing_format_query).unwrap();
        let missing_format_refusal = missing_format_request.verify_preview(&service).unwrap_err();
        assert_eq!(missing_format_refusal.code, "malformed_signed_envelope");
        assert_eq!(
            missing_format_refusal.verifier_error,
            "MissingRequiredField(format_version)"
        );
        assert_eq!(missing_format_refusal.mutation, "none");
        assert!(!missing_format_refusal.pending_write_allowed);
        assert!(missing_format_refusal.pending_state_unchanged);
        assert!(missing_format_refusal.chain_state_unchanged);

        let wrong_chain = target.replace("chain_id=xriq-devnet", "chain_id=xriq-devnet-other");
        let (_, wrong_chain_query) = split_http_target(&wrong_chain);
        let wrong_chain_request =
            LocalWalletSignedSubmitPreviewRequest::from_query(wrong_chain_query).unwrap();
        let wrong_chain_refusal = wrong_chain_request.verify_preview(&service).unwrap_err();
        assert_eq!(wrong_chain_refusal.code, "wrong_chain_id");
        assert_eq!(wrong_chain_refusal.verifier_error, "WrongChainId");
        assert_eq!(
            wrong_chain_refusal.audit_event_id,
            "signed-submit-wrong-chain-id:local_request_id"
        );

        let duplicate_service =
            service
                .clone()
                .with_pending_mempool_entries(vec![xriq_api::MempoolEntryResponse {
                    tx_hash: "628ac2587bbae121654089ffb42cd1e2b1a59384c8e9b9206c925873783d40f7"
                        .to_string(),
                    from_address: "xriqdev1alice00000000000".to_string(),
                    to_address: "xriqdev1carol00000000000".to_string(),
                    amount_base_units: "5".to_string(),
                    fee_base_units: "2".to_string(),
                    nonce: 1,
                    status: "pending".to_string(),
                    first_seen_at_utc: None,
                    last_seen_at_utc: None,
                }]);
        let (_, duplicate_query) = split_http_target(&target);
        let duplicate_request =
            LocalWalletSignedSubmitPreviewRequest::from_query(duplicate_query).unwrap();
        let duplicate_refusal = duplicate_request
            .verify_preview(&duplicate_service)
            .unwrap_err();
        assert_eq!(duplicate_refusal.code, "duplicate_pending_transaction");
        assert_eq!(duplicate_refusal.http_status, 409);
        assert_eq!(
            duplicate_refusal.verifier_error,
            "DuplicatePendingTransaction"
        );
        assert_eq!(duplicate_refusal.mutation, "none");
        assert_eq!(service.mempool(usize::MAX).pending_count, 0);

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn local_wallet_signed_submit_request_appends_pending_with_explicit_local_flag() {
        let (path, pending_path, service) =
            confirmed_signed_submit_preview_service("signed-submit-accepted");
        assert_eq!(service.snapshot().current_height, 1);
        assert_eq!(service.mempool(usize::MAX).pending_count, 0);
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        let target = wallet_signed_submit_preview_target("local-signed-submit-accepted");

        let response = run([
            "request",
            "--chain-file",
            &path_text,
            "--pending-file",
            &pending_text,
            "--alice-balance",
            "100",
            "--method",
            "POST",
            "--target",
            &target,
            "--enable-local-wallet-submit-signed",
            "true",
        ])
        .unwrap();

        assert!(response.contains("status_code=201"));
        assert!(response.contains("\"code\": \"signed_submit_accepted_local_only\""));
        assert!(response.contains("\"status\": \"pending\""));
        assert!(response.contains("\"mutation\": \"pending_state_only\""));
        assert!(response.contains("\"warning\": \"local-private-devnet-test-signature-only\""));
        assert!(response.contains("\"signature_algorithm\": \"test-only\""));
        assert!(response.contains("\"verifier\": \"TestOnlySignatureVerifier\""));
        assert!(response.contains("\"verified\": true"));
        assert!(response.contains(
            "\"transaction_signing_hash\": \"3c0f7f54bca53ad4c49ff98ba9ba2930ac6147a3cb510ead3265c894fcf1850b\""
        ));
        assert!(response.contains(
            "\"tx_hash\": \"628ac2587bbae121654089ffb42cd1e2b1a59384c8e9b9206c925873783d40f7\""
        ));
        assert!(response.contains("\"before_count\": 0"));
        assert!(response.contains("\"after_count\": 1"));
        assert!(response.contains("\"chain_unchanged\": true"));
        assert!(response
            .contains("\"event_id\": \"signed-submit-accepted:local-signed-submit-accepted\""));
        assert!(response.contains("\"action\": \"wallet_transfer_signed_submit_attempt\""));
        assert!(response.contains("\"explicit_flag\": \"--enable-local-wallet-submit-signed\""));
        assert!(response.contains("\"from_address\": \"xriqdev1alice00000000000\""));
        assert!(response.contains("\"to_address\": \"xriqdev1carol00000000000\""));
        assert!(!response.contains("private_key"));
        assert!(!response.contains("seed_phrase"));
        assert!(!response.contains("mnemonic"));

        let pending_text = fs::read_to_string(&pending_path).unwrap();
        assert!(pending_text.contains("xriq-pending-transaction-v1"));
        assert!(pending_text
            .contains("628ac2587bbae121654089ffb42cd1e2b1a59384c8e9b9206c925873783d40f7"));
        assert!(pending_text.contains("xriqdev1carol00000000000"));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn local_wallet_signed_submit_request_refuses_invalid_or_forbidden_fields_without_pending_write(
    ) {
        let (path, pending_path, _service) =
            confirmed_signed_submit_preview_service("signed-submit-accepted-invalid");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        let base_pending_text = fs::read_to_string(&pending_path).unwrap();
        let invalid_target = wallet_signed_submit_preview_target("local-signed-submit-invalid")
            .replace(
                "signature_algorithm=test-only",
                "signature_algorithm=not-test-only",
            );

        let response = run([
            "request",
            "--chain-file",
            &path_text,
            "--pending-file",
            &pending_text,
            "--alice-balance",
            "100",
            "--method",
            "POST",
            "--target",
            &invalid_target,
            "--enable-local-wallet-submit-signed",
            "true",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"unsupported_signature_algorithm\""));
        assert!(response.contains("\"mutation\": \"none\""));
        assert!(response.contains("\"pending_write_allowed\": false"));
        assert_eq!(
            fs::read_to_string(&pending_path).unwrap(),
            base_pending_text
        );

        let forbidden_target = format!(
            "{}&private_key=not-allowed",
            wallet_signed_submit_preview_target("local-signed-submit-forbidden")
        );
        let forbidden_response = run([
            "request",
            "--chain-file",
            &path_text,
            "--pending-file",
            &pending_text,
            "--alice-balance",
            "100",
            "--method",
            "POST",
            "--target",
            &forbidden_target,
            "--enable-local-wallet-submit-signed",
            "true",
        ])
        .unwrap();

        assert!(forbidden_response.contains("status_code=400"));
        assert!(forbidden_response.contains("\"code\": \"forbidden_signed_submit_field\""));
        assert_eq!(
            fs::read_to_string(&pending_path).unwrap(),
            base_pending_text
        );

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn local_wallet_signed_submit_runtime_refreshes_pending_mempool() {
        let (path, pending_path, service) =
            confirmed_signed_submit_preview_service("server-signed-submit");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        let mut runtime = LocalApiRuntime {
            service,
            postgres_read_model: None,
            chain_file: path_text.clone(),
            pending_file: Some(pending_text.clone()),
            alice_balance: Some(XriqAmount::from_base_units(100)),
            enable_local_wallet_submit: false,
            enable_local_wallet_send: false,
            enable_local_wallet_signed_submit: true,
            enable_local_block_production: false,
        };
        let target = wallet_signed_submit_preview_target("local-signed-submit-server-1");

        let response = local_api_http_response(&mut runtime, "POST", &target);

        assert_eq!(response.status_code, 201);
        assert!(response
            .body
            .contains("\"code\": \"signed_submit_accepted_local_only\""));
        let mempool = local_api_http_response(&mut runtime, "GET", "/api/v1/mempool?limit=5");
        assert_eq!(mempool.status_code, 200);
        assert!(mempool.body.contains("\"pending_count\": 1"));
        assert!(mempool
            .body
            .contains("628ac2587bbae121654089ffb42cd1e2b1a59384c8e9b9206c925873783d40f7"));
        assert!(mempool.body.contains("xriqdev1carol00000000000"));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn local_wallet_submit_request_appends_pending_with_explicit_local_flag() {
        let path = temp_store_path("enabled-wallet-submit");
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        FileChainStore::open(&path).unwrap();
        let target = wallet_submit_target(
            "local-wallet-submit-1",
            "draft-wallet-submit-1",
            PRIVATE_DEVNET_TEST_SENDER,
        );

        let response = run([
            "request",
            "--chain-file",
            &path_text,
            "--pending-file",
            &pending_text,
            "--alice-balance",
            "100",
            "--method",
            "POST",
            "--target",
            &target,
            "--enable-local-wallet-submit",
            "true",
        ])
        .unwrap();

        assert!(response.contains("status_code=201"));
        assert!(response.contains("\"code\": \"wallet_submit_accepted_local_only\""));
        assert!(response.contains("\"status\": \"pending\""));
        assert!(response.contains("\"mutation\": \"pending_state_only\""));
        assert!(response.contains("\"before_count\": 0"));
        assert!(response.contains("\"after_count\": 1"));
        assert!(response.contains("\"chain_unchanged\": true"));
        assert!(response.contains("\"event_id\": \"wallet-transfer-submit:local-wallet-submit-1\""));
        assert!(response.contains("\"draft_id\": \"draft-wallet-submit-1\""));
        assert!(response.contains("\"from_address\": \"xriqdev1alice00000000000\""));
        assert!(response.contains("\"to_address\": \"xriqdev1carol00000000000\""));
        let pending_text = fs::read_to_string(&pending_path).unwrap();
        assert!(pending_text.contains("xriq-pending-transaction-v1"));
        assert!(pending_text.contains("xriqdev1carol00000000000"));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn local_wallet_submit_runtime_refreshes_pending_mempool() {
        let path = temp_store_path("server-wallet-submit");
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        FileChainStore::open(&path).unwrap();
        let service = build_service(
            &path_text,
            Some(&pending_text),
            Some(XriqAmount::from_base_units(100)),
        )
        .unwrap();
        let mut runtime = LocalApiRuntime {
            service,
            postgres_read_model: None,
            chain_file: path_text.clone(),
            pending_file: Some(pending_text.clone()),
            alice_balance: Some(XriqAmount::from_base_units(100)),
            enable_local_wallet_submit: true,
            enable_local_wallet_send: false,
            enable_local_wallet_signed_submit: false,
            enable_local_block_production: false,
        };
        let target = wallet_submit_target(
            "local-wallet-server-1",
            "draft-wallet-server-1",
            PRIVATE_DEVNET_TEST_SENDER,
        );

        let response = local_api_http_response(&mut runtime, "POST", &target);

        assert_eq!(response.status_code, 201);
        assert!(response
            .body
            .contains("\"code\": \"wallet_submit_accepted_local_only\""));
        let mempool = local_api_http_response(&mut runtime, "GET", "/api/v1/mempool?limit=5");
        assert_eq!(mempool.status_code, 200);
        assert!(mempool.body.contains("\"pending_count\": 1"));
        assert!(mempool.body.contains("xriqdev1carol00000000000"));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn local_wallet_submit_request_validates_local_contract_fields() {
        let path = temp_store_path("invalid-wallet-submit");
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        FileChainStore::open(&path).unwrap();
        let target = wallet_submit_target(
            "local-wallet-submit-2",
            "draft-wallet-submit-2",
            "xriqdev1bobbb00000000000",
        );

        let response = run([
            "request",
            "--chain-file",
            &path_text,
            "--pending-file",
            &pending_text,
            "--alice-balance",
            "100",
            "--method",
            "POST",
            "--target",
            &target,
            "--enable-local-wallet-submit",
            "true",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"invalid_sender\""));
        assert!(!pending_path.exists());

        let _ = fs::remove_file(path);
    }

    #[test]
    fn local_wallet_send_request_requires_explicit_enablement() {
        let path = temp_store_path("disabled-wallet-send");
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        FileChainStore::open(&path).unwrap();
        let target = wallet_send_target("local-wallet-send-disabled", PRIVATE_DEVNET_TEST_SENDER);

        let response = run([
            "request",
            "--chain-file",
            &path_text,
            "--pending-file",
            &pending_text,
            "--alice-balance",
            "100",
            "--method",
            "POST",
            "--target",
            &target,
        ])
        .unwrap();

        assert!(response.contains("status_code=403"));
        assert!(response.contains("\"code\": \"wallet_send_disabled\""));
        assert!(!pending_path.exists());

        let _ = fs::remove_file(path);
    }

    #[test]
    fn local_wallet_send_request_appends_pending_with_explicit_local_flag() {
        let path = temp_store_path("enabled-wallet-send");
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        FileChainStore::open(&path).unwrap();
        let target = wallet_send_target("local-wallet-send-1", PRIVATE_DEVNET_TEST_SENDER);

        let response = run([
            "request",
            "--chain-file",
            &path_text,
            "--pending-file",
            &pending_text,
            "--alice-balance",
            "100",
            "--method",
            "POST",
            "--target",
            &target,
            "--enable-local-wallet-send",
            "true",
        ])
        .unwrap();

        assert!(response.contains("status_code=201"));
        assert!(response.contains("\"code\": \"wallet_send_accepted_local_only\""));
        assert!(response.contains("\"status\": \"pending\""));
        assert!(response.contains("\"mutation\": \"pending_state_only\""));
        assert!(response.contains("\"before_count\": 0"));
        assert!(response.contains("\"after_count\": 1"));
        assert!(response.contains("\"chain_unchanged\": true"));
        assert!(response.contains("\"event_id\": \"wallet-transfer-send:local-wallet-send-1\""));
        assert!(response.contains("\"resource_id\": \"local_request_id\""));
        assert!(response.contains("\"from_address\": \"xriqdev1alice00000000000\""));
        assert!(response.contains("\"to_address\": \"xriqdev1carol00000000000\""));
        let pending_text = fs::read_to_string(&pending_path).unwrap();
        assert!(pending_text.contains("xriq-pending-transaction-v1"));
        assert!(pending_text.contains("xriqdev1carol00000000000"));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn local_wallet_send_runtime_refreshes_pending_mempool() {
        let path = temp_store_path("server-wallet-send");
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        FileChainStore::open(&path).unwrap();
        let service = build_service(
            &path_text,
            Some(&pending_text),
            Some(XriqAmount::from_base_units(100)),
        )
        .unwrap();
        let mut runtime = LocalApiRuntime {
            service,
            postgres_read_model: None,
            chain_file: path_text.clone(),
            pending_file: Some(pending_text.clone()),
            alice_balance: Some(XriqAmount::from_base_units(100)),
            enable_local_wallet_submit: false,
            enable_local_wallet_send: true,
            enable_local_wallet_signed_submit: false,
            enable_local_block_production: false,
        };
        let target = wallet_send_target("local-wallet-send-server-1", PRIVATE_DEVNET_TEST_SENDER);

        let response = local_api_http_response(&mut runtime, "POST", &target);

        assert_eq!(response.status_code, 201);
        assert!(response
            .body
            .contains("\"code\": \"wallet_send_accepted_local_only\""));
        let mempool = local_api_http_response(&mut runtime, "GET", "/api/v1/mempool?limit=5");
        assert_eq!(mempool.status_code, 200);
        assert!(mempool.body.contains("\"pending_count\": 1"));
        assert!(mempool.body.contains("xriqdev1carol00000000000"));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn local_wallet_send_request_validates_local_contract_fields() {
        let path = temp_store_path("invalid-wallet-send");
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        FileChainStore::open(&path).unwrap();
        let target = wallet_send_target("local-wallet-send-2", "xriqdev1bobbb00000000000");

        let response = run([
            "request",
            "--chain-file",
            &path_text,
            "--pending-file",
            &pending_text,
            "--alice-balance",
            "100",
            "--method",
            "POST",
            "--target",
            &target,
            "--enable-local-wallet-send",
            "true",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"invalid_sender\""));
        assert!(!pending_path.exists());

        let _ = fs::remove_file(path);
    }

    #[test]
    fn local_block_production_request_requires_explicit_enablement() {
        let path = temp_store_path("disabled-block-production");
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        let pending_detail = xriq_node::private_devnet_file_submit_pending_transfer_body(
            &path_text,
            &pending_text,
            Some(XriqAmount::from_base_units(100)),
            &pending_transfer_body(),
        )
        .unwrap();
        let target = "/api/v1/blocks/produce?local_request_id=local-test-1&producer=xriqdev1author00000000000&max_transactions=4&timestamp_ms=2000";

        let response = run([
            "request",
            "--chain-file",
            &path_text,
            "--pending-file",
            &pending_text,
            "--alice-balance",
            "100",
            "--method",
            "POST",
            "--target",
            target,
        ])
        .unwrap();

        assert!(response.contains("status_code=403"));
        assert!(response.contains("\"code\": \"block_production_disabled\""));
        assert!(fs::read_to_string(&pending_path)
            .unwrap()
            .contains(&hash_hex(pending_detail.tx_hash)));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn local_block_production_request_confirms_pending_with_explicit_local_flag() {
        let path = temp_store_path("enabled-block-production");
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        let pending_detail = xriq_node::private_devnet_file_submit_pending_transfer_body(
            &path_text,
            &pending_text,
            Some(XriqAmount::from_base_units(100)),
            &pending_transfer_body(),
        )
        .unwrap();
        let tx_hash = hash_hex(pending_detail.tx_hash);
        let target = "/api/v1/blocks/produce?local_request_id=local-test-2&producer=xriqdev1author00000000000&max_transactions=4&timestamp_ms=2000";

        let response = run([
            "request",
            "--chain-file",
            &path_text,
            "--pending-file",
            &pending_text,
            "--alice-balance",
            "100",
            "--method",
            "POST",
            "--target",
            target,
            "--enable-local-block-production",
            "true",
        ])
        .unwrap();

        assert!(response.contains("status_code=201"));
        assert!(response.contains("\"code\": \"block_production_accepted_local_only\""));
        assert!(response.contains("\"status\": \"confirmed\""));
        assert!(response.contains("\"mutation\": \"chain_and_pending_state_local_only\""));
        assert!(response.contains("\"before_count\": 1"));
        assert!(response.contains("\"after_count\": 0"));
        assert!(response.contains("\"previous_height\": 0"));
        assert!(response.contains("\"current_height\": 1"));
        assert!(response.contains("\"audit_scope\": \"api-local-accepted\""));
        assert!(response.contains("\"event_id\": \"block-production:local-test-2\""));
        assert!(response.contains(&tx_hash));
        assert_eq!(fs::read_to_string(&pending_path).unwrap(), "");

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn local_block_production_request_validates_local_contract_fields() {
        let path = temp_store_path("invalid-block-production");
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        xriq_node::private_devnet_file_submit_pending_transfer_body(
            &path_text,
            &pending_text,
            Some(XriqAmount::from_base_units(100)),
            &pending_transfer_body(),
        )
        .unwrap();

        let response = run([
            "request",
            "--chain-file",
            &path_text,
            "--pending-file",
            &pending_text,
            "--alice-balance",
            "100",
            "--method",
            "POST",
            "--target",
            "/api/v1/blocks/produce?local_request_id=local-test-3&producer=xriqdev1bobbb00000000000&max_transactions=4&timestamp_ms=2000",
            "--enable-local-block-production",
            "true",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"invalid_producer\""));
        assert!(fs::read_to_string(&pending_path)
            .unwrap()
            .contains("xriq-pending-transaction-v1"));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn postgres_request_config_defaults_to_local_smoke_database() {
        let config =
            PostgresRequestConfig::parse(&["--target", POSTGRES_READ_MODEL_STATUS_ROUTE]).unwrap();

        assert_eq!(config.read_model.docker_container, "xriq-postgres");
        assert_eq!(config.read_model.database, "xriq_phase1_1_smoke");
        assert_eq!(config.method, "GET");
        assert_eq!(config.target, POSTGRES_READ_MODEL_STATUS_ROUTE);

        let explicit = PostgresRequestConfig::parse(&[
            "--docker-container",
            "xriq-postgres",
            "--database",
            "xriq_phase1_1_smoke",
            "--method",
            "GET",
            "--target",
            POSTGRES_READ_MODEL_STATUS_ROUTE,
        ])
        .unwrap();
        assert_eq!(explicit, config);
    }

    #[test]
    fn postgres_request_rejects_unsupported_route_without_docker() {
        let missing = run([
            "request-postgres",
            "--target",
            "/api/v1/admin/postgres/missing",
        ])
        .unwrap();
        assert!(missing.contains("status_code=404"));
        assert!(missing.contains("\"code\": \"not_found\""));

        let unsupported_method = run([
            "request-postgres",
            "--method",
            "POST",
            "--target",
            POSTGRES_READ_MODEL_STATUS_ROUTE,
        ])
        .unwrap();
        assert!(unsupported_method.contains("status_code=405"));
        assert!(unsupported_method.contains("\"code\": \"method_not_allowed\""));
    }

    #[test]
    fn postgres_status_json_renders_counts_and_preview_warning() {
        let config =
            PostgresRequestConfig::parse(&["--target", POSTGRES_READ_MODEL_STATUS_ROUTE]).unwrap();
        let values = parse_key_value_lines(
            "\
blocks=1
transactions=1
accounts=3
account_balances=3
account_transactions=2
mempool_entries=1
audit_events=1
indexer_runs=1
latest_height=1
latest_block_hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
indexer_status=completed
",
            "test postgres status",
        )
        .unwrap();

        let body = render_postgres_read_model_status_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains(POSTGRES_READ_MODEL_WARNING));
        assert!(body.contains("\"database\": \"xriq_phase1_1_smoke\""));
        assert!(body.contains("\"latest_height\": 1"));
        assert!(body.contains("\"blocks\": 1"));
        assert!(body.contains("\"account_transactions\": 2"));
        assert!(body.contains("\"mempool_entries\": 1"));
        assert!(body.contains("\"indexer_status\": \"completed\""));
    }

    #[test]
    fn postgres_node_status_json_renders_product_shape() {
        let config =
            PostgresRequestConfig::parse(&["--target", POSTGRES_NODE_STATUS_ROUTE]).unwrap();
        let values = parse_key_value_lines(
            "\
current_height=1
latest_block_hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
state_root=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
stored_blocks=1
pending_transactions=0
",
            "test postgres node status",
        )
        .unwrap();

        let body = render_postgres_node_status_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains(POSTGRES_READ_MODEL_WARNING));
        assert!(body.contains("\"service\": \"xriq-api\""));
        assert!(body.contains("\"status\": \"healthy\""));
        assert!(body.contains("\"mode\": \"serve-readonly\""));
        assert!(body.contains("\"network\": \"xriq-devnet\""));
        assert!(body.contains("\"current_height\": 1"));
        assert!(body.contains(
            "\"latest_block_hash\": \"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\""
        ));
        assert!(body.contains(
            "\"state_root\": \"abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789\""
        ));
        assert!(body.contains("\"stored_blocks\": 1"));
        assert!(body.contains("\"pending_transactions\": 0"));
        assert!(body.contains("\"wallet_submit_status\": \"disabled\""));
        assert!(body.contains("\"block_production_status\": \"disabled\""));
    }

    #[test]
    fn postgres_indexer_status_json_renders_product_shape() {
        let config =
            PostgresRequestConfig::parse(&["--target", POSTGRES_INDEXER_STATUS_ROUTE]).unwrap();
        let values = parse_key_value_lines(
            "\
status=current
latest_indexed_height=1
latest_indexed_block_hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
lag_blocks=0
last_run_id=private-devnet-replay-1-0123456789abcdef
last_run_status=completed
last_run_from_height=1
last_run_to_height=1
last_run_blocks_indexed=1
last_run_transactions_indexed=1
",
            "test postgres indexer status",
        )
        .unwrap();

        let body = render_postgres_indexer_status_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains(POSTGRES_READ_MODEL_WARNING));
        assert!(body.contains("\"service\": \"xriq-indexer\""));
        assert!(body.contains("\"status\": \"current\""));
        assert!(body.contains("\"latest_indexed_height\": 1"));
        assert!(body.contains(
            "\"latest_indexed_block_hash\": \"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\""
        ));
        assert!(body.contains("\"lag_blocks\": 0"));
        assert!(body.contains("\"run_id\": \"private-devnet-replay-1-0123456789abcdef\""));
        assert!(body.contains("\"from_height\": 1"));
        assert!(body.contains("\"to_height\": 1"));
        assert!(body.contains("\"blocks_indexed\": 1"));
        assert!(body.contains("\"transactions_indexed\": 1"));
    }

    #[test]
    fn postgres_overview_json_renders_product_shape_from_read_model_counts() {
        let config =
            PostgresRequestConfig::parse(&["--target", POSTGRES_EXPLORER_OVERVIEW_ROUTE]).unwrap();
        let values = parse_key_value_lines(
            "\
current_height=1
latest_block_hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
state_root=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
stored_blocks=1
pending_transactions=0
transactions=1
accounts=3
indexer_run_id=private-devnet-replay-1-0123456789abcdef
indexer_status=completed
indexer_from_height=1
indexer_to_height=1
indexer_blocks_indexed=1
indexer_transactions_indexed=1
",
            "test postgres overview",
        )
        .unwrap();

        let body = render_postgres_explorer_overview_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains(POSTGRES_READ_MODEL_WARNING));
        assert!(body.contains("\"network\": \"xriq-devnet\""));
        assert!(body.contains("\"current_height\": 1"));
        assert!(body.contains("\"pending_transactions\": 0"));
        assert!(body.contains("\"status\": \"completed\""));
        assert!(body.contains("\"transactions_indexed\": 1"));
        assert!(body.contains("\"accounts\": 3"));
    }

    #[test]
    fn postgres_audit_events_json_renders_product_list_shape() {
        let config =
            PostgresRequestConfig::parse(&["--target", "/api/v1/admin/audit-events?limit=5"])
                .unwrap();
        let values = parse_key_value_lines(
            "\
limit=5
audit_event_count=1
next_cursor=none
audit_event_0_event_id=index-block:1:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
audit_event_0_actor=xriq-indexer
audit_event_0_action=index_block
audit_event_0_resource_type=block
audit_event_0_resource_id=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
audit_event_0_environment=private-devnet
",
            "test postgres audit events",
        )
        .unwrap();

        let body = render_postgres_audit_events_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains("\"limit\": 5"));
        assert!(body.contains("\"next_cursor\": null"));
        assert!(body.contains("\"audit_events\": ["));
        assert!(body.contains(
            "\"event_id\": \"index-block:1:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\""
        ));
        assert!(body.contains("\"actor\": \"xriq-indexer\""));
        assert!(body.contains("\"action\": \"index_block\""));
        assert!(body.contains("\"resource_type\": \"block\""));
        assert!(body.contains(
            "\"resource_id\": \"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\""
        ));
        assert!(body.contains("\"environment\": \"private-devnet\""));
        assert!(body.contains("\"local_refusal_audit_count\": 4"));
        assert!(body.contains("\"local_refusal_audit_events\": ["));
        assert!(body.contains("\"event_id\": \"wallet-transfer-submit:local_request_id\""));
        assert!(body.contains("\"event_id\": \"wallet-transfer-send:local_request_id\""));
        assert!(body.contains("\"event_id\": \"block-production:local_request_id\""));
        assert!(body.contains("\"event_id\": \"wallet-transfer-signed-submit:local_request_id\""));
        assert!(body.contains("\"action\": \"wallet_transfer_signed_submit_attempt\""));
        assert!(body.contains("\"action\": \"block_production_attempt\""));
        assert!(body.contains("\"resource_type\": \"block_production\""));
        assert!(body.contains("\"audit_scope\": \"api-local-refusal\""));
        assert!(body.contains("\"recording\": \"api-local-response\""));
        assert!(body.contains("\"outcome\": \"refused\""));
        assert!(body.contains("\"mutation\": \"none\""));
        assert!(!body.contains("private_key"));
        assert!(!body.contains("seed_phrase"));
        assert!(!body.contains("mnemonic"));
    }

    #[test]
    fn postgres_blocks_json_renders_product_list_shape() {
        let config = PostgresRequestConfig::parse(&["--target", "/api/v1/blocks?limit=5"]).unwrap();
        let values = parse_key_value_lines(
            "\
limit=5
block_count=1
next_cursor=none
block_0_height=1
block_0_block_hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
block_0_previous_block_hash=0000000000000000000000000000000000000000000000000000000000000000
block_0_state_root=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
block_0_transactions_root=1111111111111111111111111111111111111111111111111111111111111111
block_0_transaction_count=1
block_0_timestamp_utc=1970-01-01T00:00:01Z
",
            "test postgres blocks",
        )
        .unwrap();

        let body = render_postgres_blocks_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"limit\": 5"));
        assert!(body.contains("\"next_cursor\": null"));
        assert!(body.contains("\"blocks\": ["));
        assert!(body.contains("\"height\": 1"));
        assert!(body.contains("\"transaction_count\": 1"));
        assert!(body.contains("\"timestamp_utc\": \"1970-01-01T00:00:01Z\""));
    }

    #[test]
    fn postgres_block_detail_json_renders_product_shape() {
        let config = PostgresRequestConfig::parse(&["--target", "/api/v1/blocks/1"]).unwrap();
        let values = parse_key_value_lines(
            "\
found=true
block_0_height=1
block_0_block_hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
block_0_previous_block_hash=0000000000000000000000000000000000000000000000000000000000000000
block_0_state_root=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
block_0_transactions_root=1111111111111111111111111111111111111111111111111111111111111111
block_0_transaction_count=1
block_0_timestamp_utc=1970-01-01T00:00:01Z
block_0_transaction_entry_count=1
transaction_0_tx_hash=2222222222222222222222222222222222222222222222222222222222222222
transaction_0_block_height=1
transaction_0_block_hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
transaction_0_transaction_index=0
transaction_0_status=confirmed
transaction_0_from_address=xriqdev1alice00000000000
transaction_0_to_address=xriqdev1bobbb00000000000
transaction_0_amount_base_units=25
transaction_0_fee_base_units=2
transaction_0_nonce=0
",
            "test postgres block detail",
        )
        .unwrap();

        let body = render_postgres_block_detail_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains("\"height\": 1"));
        assert!(body.contains(
            "\"block_hash\": \"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\""
        ));
        assert!(body.contains("\"transaction_count\": 1"));
        assert!(body.contains("\"timestamp_utc\": \"1970-01-01T00:00:01Z\""));
        assert!(body.contains("\"transactions\": ["));
        assert!(body.contains(
            "\"tx_hash\": \"2222222222222222222222222222222222222222222222222222222222222222\""
        ));
        assert!(body.contains("\"status\": \"confirmed\""));
        assert!(body.contains("\"amount_base_units\": \"25\""));
    }

    #[test]
    fn postgres_block_detail_sql_accepts_height_or_hash() {
        let by_height = postgres_block_detail_sql("1").unwrap();
        assert!(by_height.contains("WHERE height = 1"));

        let block_hash = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
        let by_hash = postgres_block_detail_sql(block_hash).unwrap();
        assert!(by_hash.contains(&format!("WHERE block_hash = '{block_hash}'")));
    }

    #[test]
    fn postgres_transactions_json_renders_product_list_shape() {
        let config =
            PostgresRequestConfig::parse(&["--target", "/api/v1/transactions?limit=5"]).unwrap();
        let values = parse_key_value_lines(
            "\
limit=5
transaction_count=1
next_cursor=none
transaction_0_tx_hash=2222222222222222222222222222222222222222222222222222222222222222
transaction_0_block_height=1
transaction_0_block_hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
transaction_0_transaction_index=0
transaction_0_status=confirmed
transaction_0_from_address=xriqdev1alice00000000000
transaction_0_to_address=xriqdev1bobbb00000000000
transaction_0_amount_base_units=25
transaction_0_fee_base_units=2
transaction_0_nonce=0
",
            "test postgres transactions",
        )
        .unwrap();

        let body = render_postgres_transactions_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"limit\": 5"));
        assert!(body.contains("\"next_cursor\": null"));
        assert!(body.contains("\"transactions\": ["));
        assert!(body.contains("\"status\": \"confirmed\""));
        assert!(body.contains("\"amount_base_units\": \"25\""));
        assert!(body.contains("\"fee_base_units\": \"2\""));
        assert!(body.contains("\"nonce\": 0"));
    }

    #[test]
    fn postgres_mempool_json_renders_product_list_shape() {
        let config =
            PostgresRequestConfig::parse(&["--target", "/api/v1/mempool?limit=5"]).unwrap();
        let values = parse_key_value_lines(
            "\
limit=5
current_height=1
entry_count=1
pending_count=1
next_cursor=none
mempool_entry_0_tx_hash=3333333333333333333333333333333333333333333333333333333333333333
mempool_entry_0_from_address=xriqdev1alice00000000000
mempool_entry_0_to_address=xriqdev1carol00000000000
mempool_entry_0_amount_base_units=5
mempool_entry_0_fee_base_units=2
mempool_entry_0_nonce=1
mempool_entry_0_status=pending
mempool_entry_0_first_seen_at_utc=1970-01-01T00:00:01Z
mempool_entry_0_last_seen_at_utc=1970-01-01T00:00:01Z
",
            "test postgres mempool",
        )
        .unwrap();

        let body = render_postgres_mempool_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains(MEMPOOL_READONLY_WARNING));
        assert!(body.contains(POSTGRES_READ_MODEL_WARNING));
        assert!(body.contains("\"current_height\": 1"));
        assert!(body.contains("\"pending_count\": 1"));
        assert!(body.contains("\"limit\": 5"));
        assert!(body.contains("\"next_cursor\": null"));
        assert!(body.contains("\"inspect_status\": \"enabled\""));
        assert!(body.contains("\"submit_status\": \"disabled\""));
        assert!(body.contains("\"produce_block_status\": \"disabled\""));
        assert!(body.contains("\"entries\": ["));
        assert!(body.contains(
            "\"tx_hash\": \"3333333333333333333333333333333333333333333333333333333333333333\""
        ));
        assert!(body.contains("\"to_address\": \"xriqdev1carol00000000000\""));
        assert!(body.contains("\"amount_base_units\": \"5\""));
        assert!(body.contains("\"fee_base_units\": \"2\""));
        assert!(body.contains("\"nonce\": 1"));
        assert!(body.contains("\"status\": \"pending\""));
        assert!(body.contains("\"first_seen_at_utc\": \"1970-01-01T00:00:01Z\""));
        assert!(body.contains("\"last_seen_at_utc\": \"1970-01-01T00:00:01Z\""));
    }

    #[test]
    fn postgres_wallet_status_json_renders_product_shape() {
        let config = PostgresRequestConfig::parse(&["--target", "/api/v1/wallet/status"]).unwrap();
        let values = parse_key_value_lines(
            "\
current_height=1
latest_block_hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
state_root=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
account_count=3
pending_transactions=1
",
            "test postgres wallet status",
        )
        .unwrap();

        let body = render_postgres_wallet_status_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains(WALLET_PREVIEW_WARNING));
        assert!(body.contains(POSTGRES_READ_MODEL_WARNING));
        assert!(body.contains("\"current_height\": 1"));
        assert!(body.contains(
            "\"latest_block_hash\": \"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\""
        ));
        assert!(body.contains(
            "\"state_root\": \"abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789\""
        ));
        assert!(body.contains("\"account_count\": 3"));
        assert!(body.contains("\"pending_transactions\": 1"));
        assert!(body.contains("\"draft\": true"));
        assert!(body.contains("\"submit\": false"));
        assert!(body.contains("\"send\": false"));
    }

    #[test]
    fn postgres_wallet_draft_preview_json_renders_product_shape() {
        let config = PostgresRequestConfig::parse(&[
            "--target",
            "/api/v1/wallet/transfers/draft-preview?from_address=xriqdev1alice00000000000&to_address=xriqdev1carol00000000000&amount_base_units=5&fee_base_units=2&nonce=1&expires_at_height=100",
        ])
        .unwrap();
        let values = parse_key_value_lines(
            "\
current_height=1
sender_found=true
available_base_units=73
sender_nonce=1
draft_chain_id=xriq-devnet
draft_from_address=xriqdev1alice00000000000
draft_to_address=xriqdev1carol00000000000
draft_amount_base_units=5
draft_fee_base_units=2
draft_nonce=1
draft_expires_at_height=100
",
            "test postgres wallet draft preview",
        )
        .unwrap();

        let body = render_postgres_wallet_draft_preview_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains(WALLET_PREVIEW_WARNING));
        assert!(body.contains(POSTGRES_READ_MODEL_WARNING));
        assert!(body.contains("\"mutation\": \"none\""));
        assert!(body.contains("\"ok\": true"));
        assert!(body.contains("\"errors\": []"));
        assert!(body.contains("\"chain_id\": \"xriq-devnet\""));
        assert!(body.contains("\"from_address\": \"xriqdev1alice00000000000\""));
        assert!(body.contains("\"to_address\": \"xriqdev1carol00000000000\""));
        assert!(body.contains("\"amount_base_units\": \"5\""));
        assert!(body.contains("\"fee_base_units\": \"2\""));
        assert!(body.contains("\"nonce\": 1"));
        assert!(body.contains("\"expires_at_height\": 100"));
        assert!(body.contains("\"available_base_units\": \"73\""));
        assert!(body.contains("\"debit_base_units\": \"7\""));
        assert!(body.contains("\"remaining_base_units\": \"66\""));
    }

    #[test]
    fn postgres_wallet_draft_preview_json_renders_validation_errors() {
        let config = PostgresRequestConfig::parse(&[
            "--target",
            "/api/v1/wallet/transfers/draft-preview?from_address=xriqdev1alice00000000000&to_address=xriqdev1alice00000000000&amount_base_units=0&fee_base_units=1&nonce=0&expires_at_height=1",
        ])
        .unwrap();
        let values = parse_key_value_lines(
            "\
current_height=1
sender_found=true
available_base_units=73
sender_nonce=1
draft_chain_id=xriq-devnet
draft_from_address=xriqdev1alice00000000000
draft_to_address=xriqdev1alice00000000000
draft_amount_base_units=0
draft_fee_base_units=1
draft_nonce=0
draft_expires_at_height=1
",
            "test postgres wallet draft preview validation errors",
        )
        .unwrap();

        let body = render_postgres_wallet_draft_preview_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"ok\": false"));
        assert!(body.contains("sender and recipient must differ"));
        assert!(body.contains("amount must be greater than zero"));
        assert!(body.contains("fee must be at least 2 base units"));
        assert!(body.contains("nonce must match sender nonce 1"));
        assert!(body.contains("expiry must be greater than current height"));
        assert!(body.contains("\"available_base_units\": \"73\""));
        assert!(body.contains("\"debit_base_units\": \"1\""));
        assert!(body.contains("\"remaining_base_units\": \"72\""));
    }

    #[test]
    fn postgres_wallet_draft_preview_sql_rejects_invalid_amount_before_docker() {
        let output = run([
            "request-postgres",
            "--target",
            "/api/v1/wallet/transfers/draft-preview?from_address=xriqdev1alice00000000000&to_address=xriqdev1carol00000000000&amount_base_units=abc&fee_base_units=2&nonce=1&expires_at_height=100",
        ])
        .unwrap();

        assert!(output.contains("status_code=400"));
        assert!(output.contains("reason=Bad Request"));
        assert!(output.contains("\"code\": \"bad_request\""));
        assert!(output.contains("invalid amount_base_units: abc"));
    }

    #[test]
    fn postgres_transaction_detail_json_renders_product_shape() {
        let config = PostgresRequestConfig::parse(&[
            "--target",
            "/api/v1/transactions/2222222222222222222222222222222222222222222222222222222222222222",
        ])
        .unwrap();
        let values = parse_key_value_lines(
            "\
found=true
transaction_0_tx_hash=2222222222222222222222222222222222222222222222222222222222222222
transaction_0_block_height=1
transaction_0_block_hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
transaction_0_transaction_index=0
transaction_0_status=confirmed
transaction_0_from_address=xriqdev1alice00000000000
transaction_0_to_address=xriqdev1bobbb00000000000
transaction_0_amount_base_units=25
transaction_0_fee_base_units=2
transaction_0_nonce=0
",
            "test postgres transaction detail",
        )
        .unwrap();

        let body = render_postgres_transaction_detail_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains(
            "\"tx_hash\": \"2222222222222222222222222222222222222222222222222222222222222222\""
        ));
        assert!(body.contains("\"block_height\": 1"));
        assert!(body.contains("\"status\": \"confirmed\""));
        assert!(body.contains("\"amount_base_units\": \"25\""));
        assert!(body.contains("\"fee_base_units\": \"2\""));
        assert!(body.contains("\"nonce\": 0"));
    }

    #[test]
    fn postgres_wallet_transaction_status_json_renders_product_shape() {
        let config = PostgresRequestConfig::parse(&[
            "--target",
            "/api/v1/wallet/transactions/2222222222222222222222222222222222222222222222222222222222222222/status",
        ])
        .unwrap();
        let values = parse_key_value_lines(
            "\
found=true
transaction_0_tx_hash=2222222222222222222222222222222222222222222222222222222222222222
transaction_0_block_height=1
transaction_0_block_hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
transaction_0_transaction_index=0
transaction_0_status=confirmed
transaction_0_from_address=xriqdev1alice00000000000
transaction_0_to_address=xriqdev1bobbb00000000000
transaction_0_amount_base_units=25
transaction_0_fee_base_units=2
transaction_0_nonce=0
",
            "test postgres wallet transaction status",
        )
        .unwrap();

        let body =
            render_postgres_wallet_transaction_status_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains(
            "\"tx_hash\": \"2222222222222222222222222222222222222222222222222222222222222222\""
        ));
        assert!(body.contains("\"status\": \"confirmed\""));
        assert!(body.contains("\"block_height\": 1"));
        assert!(body.contains("\"transaction_index\": 0"));
        assert!(!body.contains("from_address"));
        assert!(!body.contains("amount_base_units"));
        assert!(!body.contains("fee_base_units"));
        assert!(!body.contains("\"nonce\""));
    }

    #[test]
    fn postgres_wallet_transaction_status_json_renders_pending_shape() {
        let config = PostgresRequestConfig::parse(&[
            "--target",
            "/api/v1/wallet/transactions/3333333333333333333333333333333333333333333333333333333333333333/status",
        ])
        .unwrap();
        let values = parse_key_value_lines(
            "\
found=true
transaction_0_tx_hash=3333333333333333333333333333333333333333333333333333333333333333
transaction_0_block_height=none
transaction_0_block_hash=none
transaction_0_transaction_index=none
transaction_0_status=pending
",
            "test postgres pending wallet transaction status",
        )
        .unwrap();

        let body =
            render_postgres_wallet_transaction_status_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains(
            "\"tx_hash\": \"3333333333333333333333333333333333333333333333333333333333333333\""
        ));
        assert!(body.contains("\"status\": \"pending\""));
        assert!(body.contains("\"block_height\": null"));
        assert!(body.contains("\"block_hash\": null"));
        assert!(body.contains("\"transaction_index\": null"));
        assert!(!body.contains("from_address"));
        assert!(!body.contains("amount_base_units"));
        assert!(!body.contains("fee_base_units"));
        assert!(!body.contains("\"nonce\""));
    }

    #[test]
    fn postgres_iso20022_transaction_status_json_renders_confirmed_preview_shape() {
        let config = PostgresRequestConfig::parse(&[
            "--target",
            "/api/v1/iso20022/transactions/2222222222222222222222222222222222222222222222222222222222222222/status",
        ])
        .unwrap();
        let values = parse_key_value_lines(
            "\
found=true
transaction_0_tx_hash=2222222222222222222222222222222222222222222222222222222222222222
transaction_0_confirmed_block_height=1
transaction_0_status=confirmed
transaction_0_from_address=xriqdev1alice00000000000
transaction_0_to_address=xriqdev1bobbb00000000000
transaction_0_amount_base_units=25
transaction_0_fee_base_units=2
transaction_0_nonce=0
",
            "test postgres iso20022 transaction status",
        )
        .unwrap();

        let body =
            render_postgres_iso20022_transaction_status_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"environment\": \"private-devnet\""));
        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_model_warning\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains("\"not_certified\": true"));
        assert!(body.contains("\"mapping_version\": \"xriq-iso20022-preview-v1\""));
        assert!(body.contains("\"message_type\": \"payment_status_preview\""));
        assert!(body.contains("\"message_id\": \"iso-status-22222222\""));
        assert!(body.contains(
            "\"source_tx_hash\": \"2222222222222222222222222222222222222222222222222222222222222222\""
        ));
        assert!(body.contains("\"xriq_status\": \"confirmed\""));
        assert!(body.contains(
            "\"original_end_to_end_id\": \"2222222222222222222222222222222222222222222222222222222222222222\""
        ));
        assert!(body.contains("\"transaction_status\": \"ACSC\""));
        assert!(
            body.contains("\"status_reason\": \"accepted_settlement_completed_on_private_devnet\"")
        );
        assert!(body.contains("\"confirmed_block_height\": 1"));
        assert!(body.contains("\"interbank_settlement_date\""));
        assert!(body.contains("\"clearing_system_reference\""));
    }

    #[test]
    fn postgres_iso20022_transaction_status_json_renders_pending_preview_shape() {
        let config = PostgresRequestConfig::parse(&[
            "--target",
            "/api/v1/iso20022/transactions/3333333333333333333333333333333333333333333333333333333333333333/status",
        ])
        .unwrap();
        let values = parse_key_value_lines(
            "\
found=true
transaction_0_tx_hash=3333333333333333333333333333333333333333333333333333333333333333
transaction_0_confirmed_block_height=none
transaction_0_status=pending
transaction_0_from_address=xriqdev1alice00000000000
transaction_0_to_address=xriqdev1carol00000000000
transaction_0_amount_base_units=5
transaction_0_fee_base_units=2
transaction_0_nonce=1
",
            "test postgres iso20022 pending transaction status",
        )
        .unwrap();

        let body =
            render_postgres_iso20022_transaction_status_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains("\"xriq_status\": \"pending\""));
        assert!(body.contains("\"transaction_status\": \"PDNG\""));
        assert!(body.contains("\"status_reason\": \"pending_private_devnet_confirmation\""));
        assert!(body.contains("\"confirmed_block_height\": null"));
    }

    #[test]
    fn postgres_iso20022_payment_initiation_preview_json_renders_product_shape() {
        let config = PostgresRequestConfig::parse(&[
            "--target",
            "/api/v1/iso20022/payment-initiation/preview?tx_hash=2222222222222222222222222222222222222222222222222222222222222222",
        ])
        .unwrap();
        let values = parse_key_value_lines(
            "\
found=true
transaction_0_tx_hash=2222222222222222222222222222222222222222222222222222222222222222
transaction_0_confirmed_block_height=1
transaction_0_status=confirmed
transaction_0_from_address=xriqdev1alice00000000000
transaction_0_to_address=xriqdev1bobbb00000000000
transaction_0_amount_base_units=25
transaction_0_fee_base_units=2
transaction_0_nonce=0
",
            "test postgres iso20022 payment initiation preview",
        )
        .unwrap();

        let body =
            render_postgres_iso20022_payment_initiation_preview_json(&config.read_model, &values)
                .unwrap();

        assert!(body.contains("\"environment\": \"private-devnet\""));
        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_model_warning\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains("\"not_certified\": true"));
        assert!(body.contains("\"mapping_version\": \"xriq-iso20022-preview-v1\""));
        assert!(body.contains("\"message_type\": \"payment_initiation_preview\""));
        assert!(body.contains("\"message_id\": \"iso-preview-22222222\""));
        assert!(body.contains(
            "\"source_tx_hash\": \"2222222222222222222222222222222222222222222222222222222222222222\""
        ));
        assert!(body.contains("\"from_address\": \"xriqdev1alice00000000000\""));
        assert!(body.contains("\"to_address\": \"xriqdev1bobbb00000000000\""));
        assert!(body.contains("\"amount_base_units\": \"25\""));
        assert!(body.contains("\"fee_base_units\": \"2\""));
        assert!(body.contains("\"nonce\": 0"));
        assert!(body.contains("\"creditor_account\": \"xriqdev1bobbb00000000000\""));
        assert!(body.contains("\"debtor_account\": \"xriqdev1alice00000000000\""));
        assert!(body.contains("\"instructed_amount\": \"25\""));
        assert!(body.contains("\"currency\": \"XRIQ-DEV\""));
        assert!(body.contains(
            "\"end_to_end_id\": \"2222222222222222222222222222222222222222222222222222222222222222\""
        ));
        assert!(body.contains("\"bank_bic\""));
        assert!(body.contains("\"iban\""));
        assert!(body.contains("\"clearing_system_member_id\""));
        assert!(body.contains("\"legal_entity_identifier\""));
    }

    #[test]
    fn postgres_iso20022_account_statement_json_renders_product_shape() {
        let config = PostgresRequestConfig::parse(&[
            "--target",
            "/api/v1/iso20022/accounts/xriqdev1alice00000000000/statement?from=1970-01-01T00:00:00Z&to=1970-01-01T00:00:02Z",
        ])
        .unwrap();
        let values = parse_key_value_lines(
            "\
found=true
address=xriqdev1alice00000000000
from=1970-01-01T00:00:00Z
to=1970-01-01T00:00:02Z
closing_balance_base_units=73
transaction_count=1
transaction_0_tx_hash=2222222222222222222222222222222222222222222222222222222222222222
transaction_0_direction=sent
transaction_0_block_height=1
transaction_0_amount_base_units=25
transaction_0_fee_base_units=2
",
            "test postgres iso20022 account statement",
        )
        .unwrap();

        let body =
            render_postgres_iso20022_account_statement_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"environment\": \"private-devnet\""));
        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_model_warning\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains("\"not_certified\": true"));
        assert!(body.contains("\"mapping_version\": \"xriq-iso20022-preview-v1\""));
        assert!(body.contains("\"message_type\": \"account_statement_preview\""));
        assert!(body.contains("\"message_id\": \"iso-statement-alice-0001\""));
        assert!(body.contains("\"account_address\": \"xriqdev1alice00000000000\""));
        assert!(body.contains("\"from\": \"1970-01-01T00:00:00Z\""));
        assert!(body.contains("\"to\": \"1970-01-01T00:00:02Z\""));
        assert!(body.contains("\"opening_balance_base_units\": \"100\""));
        assert!(body.contains("\"closing_balance_base_units\": \"73\""));
        assert!(body.contains(
            "\"tx_hash\": \"2222222222222222222222222222222222222222222222222222222222222222\""
        ));
        assert!(body.contains("\"direction\": \"debit\""));
        assert!(body.contains("\"amount_base_units\": \"25\""));
        assert!(body.contains("\"fee_base_units\": \"2\""));
        assert!(body.contains("\"status\": \"confirmed\""));
        assert!(body.contains("\"block_height\": 1"));
        assert!(body.contains("\"bank_account_servicer\""));
        assert!(body.contains("\"booking_date_from_bank\""));
        assert!(body.contains("\"fiat_currency\""));
    }

    #[test]
    fn postgres_accounts_json_renders_product_list_shape() {
        let config =
            PostgresRequestConfig::parse(&["--target", "/api/v1/accounts?limit=5"]).unwrap();
        let values = parse_key_value_lines(
            "\
limit=5
account_count=2
next_cursor=none
account_0_address=xriqdev1alice00000000000
account_0_balance_base_units=73
account_0_nonce=1
account_0_height=1
account_0_state_root=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
account_0_first_seen_height=0
account_0_last_seen_height=1
account_1_address=xriqdev1bobbb00000000000
account_1_balance_base_units=25
account_1_nonce=0
account_1_height=1
account_1_state_root=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
account_1_first_seen_height=1
account_1_last_seen_height=1
",
            "test postgres accounts",
        )
        .unwrap();

        let body = render_postgres_accounts_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"limit\": 5"));
        assert!(body.contains("\"next_cursor\": null"));
        assert!(body.contains("\"accounts\": ["));
        assert!(body.contains("\"address\": \"xriqdev1alice00000000000\""));
        assert!(body.contains("\"balance_base_units\": \"73\""));
        assert!(body.contains("\"nonce\": 1"));
        assert!(body.contains("\"first_seen_height\": 0"));
        assert!(body.contains("\"last_seen_height\": 1"));
    }

    #[test]
    fn postgres_snapshots_json_renders_product_list_shape() {
        let config =
            PostgresRequestConfig::parse(&["--target", "/api/v1/snapshots?limit=5"]).unwrap();
        let values = parse_key_value_lines(
            "\
limit=5
snapshot_count=1
next_cursor=none
snapshot_0_snapshot_name=current-indexed-chain
snapshot_0_snapshot_dir=read-model://current-indexed-chain
snapshot_0_current_height=1
snapshot_0_latest_block_hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
snapshot_0_state_root=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
snapshot_0_block_count=1
snapshot_0_transaction_count=1
snapshot_0_audit_event_count=1
snapshot_0_export_status=disabled
snapshot_0_import_status=disabled
",
            "test postgres snapshots",
        )
        .unwrap();

        let body = render_postgres_snapshots_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains(SNAPSHOT_READONLY_WARNING));
        assert!(body.contains(POSTGRES_READ_MODEL_WARNING));
        assert!(body.contains("\"limit\": 5"));
        assert!(body.contains("\"next_cursor\": null"));
        assert!(body.contains("\"snapshots\": ["));
        assert!(body.contains("\"snapshot_name\": \"current-indexed-chain\""));
        assert!(body.contains("\"snapshot_dir\": \"read-model://current-indexed-chain\""));
        assert!(body.contains("\"current_height\": 1"));
        assert!(body.contains("\"block_count\": 1"));
        assert!(body.contains("\"transaction_count\": 1"));
        assert!(body.contains("\"audit_event_count\": 1"));
        assert!(body.contains("\"export_status\": \"disabled\""));
        assert!(body.contains("\"import_status\": \"disabled\""));
    }

    #[test]
    fn postgres_snapshot_detail_json_renders_product_shape() {
        let config =
            PostgresRequestConfig::parse(&["--target", "/api/v1/snapshots/current-indexed-chain"])
                .unwrap();
        let values = parse_key_value_lines(
            "\
found=true
snapshot_0_snapshot_name=current-indexed-chain
snapshot_0_snapshot_dir=read-model://current-indexed-chain
snapshot_0_current_height=1
snapshot_0_latest_block_hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
snapshot_0_state_root=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
snapshot_0_block_count=1
snapshot_0_transaction_count=1
snapshot_0_audit_event_count=1
snapshot_0_export_status=disabled
snapshot_0_import_status=disabled
",
            "test postgres snapshot detail",
        )
        .unwrap();

        let body = render_postgres_snapshot_detail_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains(SNAPSHOT_READONLY_WARNING));
        assert!(body.contains(POSTGRES_READ_MODEL_WARNING));
        assert!(body.contains("\"snapshot_name\": \"current-indexed-chain\""));
        assert!(body.contains("\"snapshot_dir\": \"read-model://current-indexed-chain\""));
        assert!(body.contains("\"current_height\": 1"));
        assert!(body.contains(
            "\"latest_block_hash\": \"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\""
        ));
        assert!(body.contains(
            "\"state_root\": \"abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789\""
        ));
        assert!(body.contains("\"block_count\": 1"));
        assert!(body.contains("\"transaction_count\": 1"));
        assert!(body.contains("\"audit_event_count\": 1"));
        assert!(body.contains("\"export_status\": \"disabled\""));
        assert!(body.contains("\"import_status\": \"disabled\""));
    }

    #[test]
    fn postgres_account_detail_json_renders_product_shape() {
        let config = PostgresRequestConfig::parse(&[
            "--target",
            "/api/v1/accounts/xriqdev1alice00000000000",
        ])
        .unwrap();
        let values = parse_key_value_lines(
            "\
found=true
account_0_address=xriqdev1alice00000000000
account_0_balance_base_units=73
account_0_nonce=1
account_0_height=1
account_0_state_root=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
account_0_first_seen_height=0
account_0_last_seen_height=1
",
            "test postgres account detail",
        )
        .unwrap();

        let body = render_postgres_account_detail_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains("\"address\": \"xriqdev1alice00000000000\""));
        assert!(body.contains("\"balance_base_units\": \"73\""));
        assert!(body.contains("\"nonce\": 1"));
        assert!(body.contains("\"height\": 1"));
        assert!(body.contains("\"first_seen_height\": 0"));
        assert!(body.contains("\"last_seen_height\": 1"));
    }

    #[test]
    fn postgres_wallet_balance_json_renders_product_shape() {
        let config = PostgresRequestConfig::parse(&[
            "--target",
            "/api/v1/wallet/accounts/xriqdev1alice00000000000/balance",
        ])
        .unwrap();
        let values = parse_key_value_lines(
            "\
found=true
account_0_address=xriqdev1alice00000000000
account_0_balance_base_units=73
account_0_nonce=1
account_0_height=1
account_0_state_root=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789
account_0_first_seen_height=0
account_0_last_seen_height=1
",
            "test postgres wallet balance",
        )
        .unwrap();

        let body = render_postgres_wallet_balance_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains("\"address\": \"xriqdev1alice00000000000\""));
        assert!(body.contains("\"balance_base_units\": \"73\""));
        assert!(body.contains("\"nonce\": 1"));
        assert!(body.contains("\"height\": 1"));
        assert!(body.contains(
            "\"state_root\": \"abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789\""
        ));
        assert!(!body.contains("first_seen_height"));
        assert!(!body.contains("last_seen_height"));
    }

    #[test]
    fn postgres_account_history_json_renders_product_shape() {
        let config = PostgresRequestConfig::parse(&[
            "--target",
            "/api/v1/accounts/xriqdev1alice00000000000/transactions?limit=5",
        ])
        .unwrap();
        let values = parse_key_value_lines(
            "\
address=xriqdev1alice00000000000
limit=5
transaction_count=1
next_cursor=none
transaction_0_address=xriqdev1alice00000000000
transaction_0_tx_hash=2222222222222222222222222222222222222222222222222222222222222222
transaction_0_direction=sent
transaction_0_block_height=1
transaction_0_transaction_index=0
transaction_0_amount_base_units=25
transaction_0_fee_base_units=2
",
            "test postgres account history",
        )
        .unwrap();

        let body = render_postgres_account_history_json(&config.read_model, &values).unwrap();

        assert!(body.contains("\"source\": \"postgres-read-model\""));
        assert!(body.contains("\"read_only\": true"));
        assert!(body.contains("\"address\": \"xriqdev1alice00000000000\""));
        assert!(body.contains("\"limit\": 5"));
        assert!(body.contains("\"next_cursor\": null"));
        assert!(body.contains("\"transactions\": ["));
        assert!(body.contains(
            "\"tx_hash\": \"2222222222222222222222222222222222222222222222222222222222222222\""
        ));
        assert!(body.contains("\"direction\": \"sent\""));
        assert!(body.contains("\"amount_base_units\": \"25\""));
        assert!(body.contains("\"fee_base_units\": \"2\""));
    }

    #[test]
    fn postgres_blocks_sql_rejects_invalid_limit_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/blocks?limit=not-a-number",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid limit"));
    }

    #[test]
    fn postgres_block_detail_sql_rejects_invalid_identifier_before_docker() {
        let response = run(["request-postgres", "--target", "/api/v1/blocks/not-a-block"]).unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid block identifier"));
    }

    #[test]
    fn postgres_transactions_sql_rejects_invalid_limit_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/transactions?limit=not-a-number",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid limit"));
    }

    #[test]
    fn postgres_mempool_sql_rejects_invalid_limit_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/mempool?limit=not-a-number",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid limit"));
    }

    #[test]
    fn postgres_audit_events_sql_rejects_invalid_limit_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/admin/audit-events?limit=not-a-number",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid limit"));
    }

    #[test]
    fn postgres_accounts_sql_rejects_invalid_limit_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/accounts?limit=not-a-number",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid limit"));
    }

    #[test]
    fn postgres_wallet_accounts_sql_rejects_invalid_limit_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/wallet/accounts?limit=not-a-number",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid limit"));
    }

    #[test]
    fn postgres_snapshots_sql_rejects_invalid_limit_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/snapshots?limit=not-a-number",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid limit"));
    }

    #[test]
    fn postgres_snapshot_detail_sql_rejects_invalid_name_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/snapshots/bad%20snapshot",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid snapshot_name"));
    }

    #[test]
    fn postgres_account_detail_sql_rejects_invalid_address_before_docker() {
        let response = run(["request-postgres", "--target", "/api/v1/accounts/not-valid"]).unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid address"));
    }

    #[test]
    fn postgres_account_history_sql_rejects_invalid_limit_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/accounts/xriqdev1alice00000000000/transactions?limit=not-a-number",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid limit"));
    }

    #[test]
    fn postgres_account_history_sql_rejects_invalid_address_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/accounts/not-valid/transactions?limit=5",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid address"));
    }

    #[test]
    fn postgres_wallet_account_history_sql_rejects_invalid_limit_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/wallet/accounts/xriqdev1alice00000000000/history?limit=not-a-number",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid limit"));
    }

    #[test]
    fn postgres_wallet_account_history_sql_rejects_invalid_address_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/wallet/accounts/not-valid/history?limit=5",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid address"));
    }

    #[test]
    fn postgres_wallet_balance_sql_rejects_invalid_address_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/wallet/accounts/not-valid/balance",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid address"));
    }

    #[test]
    fn postgres_transaction_detail_sql_rejects_invalid_hash_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/transactions/not-a-valid-hash",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid tx_hash"));
    }

    #[test]
    fn postgres_wallet_transaction_status_sql_rejects_invalid_hash_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/wallet/transactions/not-a-valid-hash/status",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid tx_hash"));
    }

    #[test]
    fn postgres_iso20022_transaction_status_sql_rejects_invalid_hash_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/iso20022/transactions/not-a-valid-hash/status",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid tx_hash"));
    }

    #[test]
    fn postgres_iso20022_payment_initiation_preview_sql_rejects_missing_hash_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/iso20022/payment-initiation/preview",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("missing required query parameter: tx_hash"));
    }

    #[test]
    fn postgres_iso20022_payment_initiation_preview_sql_rejects_invalid_hash_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/iso20022/payment-initiation/preview?tx_hash=not-a-valid-hash",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid tx_hash"));
    }

    #[test]
    fn postgres_iso20022_account_statement_sql_rejects_invalid_address_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/iso20022/accounts/not-valid/statement",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid address"));
    }

    #[test]
    fn postgres_iso20022_account_statement_sql_rejects_invalid_timestamp_before_docker() {
        let response = run([
            "request-postgres",
            "--target",
            "/api/v1/iso20022/accounts/xriqdev1alice00000000000/statement?from=not%27valid&to=1970-01-01T00:00:02Z",
        ])
        .unwrap();

        assert!(response.contains("status_code=400"));
        assert!(response.contains("\"code\": \"bad_request\""));
        assert!(response.contains("invalid from"));
    }

    #[test]
    fn serve_config_defaults_to_localhost_private_devnet_port() {
        let config = ServeConfig::parse(&[
            "--chain-file",
            "target/xriq.bin",
            "--pending-file",
            "target/xriq-pending.tsv",
        ])
        .unwrap();

        assert_eq!(config.chain_file, "target/xriq.bin");
        assert_eq!(config.pending_file, Some("target/xriq-pending.tsv"));
        assert_eq!(config.alice_balance, None);
        assert_eq!(config.bind, DEFAULT_BIND);
        assert_eq!(config.postgres_read_model, None);
        assert!(!config.enable_local_wallet_submit);
        assert!(!config.enable_local_wallet_send);
        assert!(!config.enable_local_wallet_signed_submit);
        assert!(!config.enable_local_block_production);

        let wallet_enabled = ServeConfig::parse(&[
            "--chain-file",
            "target/xriq.bin",
            "--enable-local-wallet-submit",
            "true",
        ])
        .unwrap();
        assert!(wallet_enabled.enable_local_wallet_submit);

        let wallet_send_enabled = ServeConfig::parse(&[
            "--chain-file",
            "target/xriq.bin",
            "--enable-local-wallet-send",
            "true",
        ])
        .unwrap();
        assert!(wallet_send_enabled.enable_local_wallet_send);

        let wallet_signed_submit_enabled = ServeConfig::parse(&[
            "--chain-file",
            "target/xriq.bin",
            "--enable-local-wallet-submit-signed",
            "true",
        ])
        .unwrap();
        assert!(wallet_signed_submit_enabled.enable_local_wallet_signed_submit);

        let enabled = ServeConfig::parse(&[
            "--chain-file",
            "target/xriq.bin",
            "--enable-local-block-production",
            "true",
        ])
        .unwrap();
        assert!(enabled.enable_local_block_production);
    }

    #[test]
    fn serve_config_enables_postgres_read_model_only_with_explicit_pair() {
        let config = ServeConfig::parse(&[
            "--chain-file",
            "target/xriq.bin",
            "--postgres-docker-container",
            "xriq-postgres",
            "--postgres-database",
            "xriq_phase1_1_smoke",
        ])
        .unwrap();

        assert_eq!(
            config.postgres_read_model,
            Some(PostgresReadModelConfig {
                docker_container: "xriq-postgres",
                database: "xriq_phase1_1_smoke",
            })
        );

        let missing_database = ServeConfig::parse(&[
            "--chain-file",
            "target/xriq.bin",
            "--postgres-docker-container",
            "xriq-postgres",
        ])
        .unwrap_err();
        assert!(missing_database.contains("--postgres-database"));

        let missing_container = ServeConfig::parse(&[
            "--chain-file",
            "target/xriq.bin",
            "--postgres-database",
            "xriq_phase1_1_smoke",
        ])
        .unwrap_err();
        assert!(missing_container.contains("--postgres-docker-container"));
    }

    #[test]
    fn postgres_route_stays_disabled_without_server_postgres_config() {
        let response =
            maybe_postgres_read_model_http_response(None, "GET", POSTGRES_READ_MODEL_STATUS_ROUTE)
                .unwrap()
                .unwrap();

        assert_eq!(response.status_code, 404);
        assert_eq!(response.reason, "Not Found");
        assert!(response.body.contains("\"code\": \"not_found\""));
        assert!(response.body.contains("endpoint is disabled"));

        assert!(maybe_postgres_read_model_http_response(None, "GET", "/api/v1/health").is_none());
        assert!(maybe_postgres_read_model_http_response(
            None,
            "GET",
            POSTGRES_EXPLORER_OVERVIEW_ROUTE
        )
        .is_none());
        assert!(
            maybe_postgres_read_model_http_response(None, "GET", POSTGRES_NODE_STATUS_ROUTE)
                .is_none()
        );
        assert!(maybe_postgres_read_model_http_response(
            None,
            "GET",
            POSTGRES_INDEXER_STATUS_ROUTE
        )
        .is_none());
        assert!(maybe_postgres_read_model_http_response(
            None,
            "GET",
            "/api/v1/admin/audit-events?limit=5"
        )
        .is_none());
        assert!(
            maybe_postgres_read_model_http_response(None, "GET", "/api/v1/blocks?limit=5")
                .is_none()
        );
        assert!(maybe_postgres_read_model_http_response(None, "GET", "/api/v1/blocks/1").is_none());
        assert!(maybe_postgres_read_model_http_response(
            None,
            "GET",
            "/api/v1/transactions?limit=5"
        )
        .is_none());
        assert!(
            maybe_postgres_read_model_http_response(None, "GET", "/api/v1/mempool?limit=5")
                .is_none()
        );
        assert!(
            maybe_postgres_read_model_http_response(None, "GET", "/api/v1/wallet/status").is_none()
        );
        assert!(maybe_postgres_read_model_http_response(
            None,
            "GET",
            "/api/v1/wallet/transfers/draft-preview?from_address=xriqdev1alice00000000000&to_address=xriqdev1carol00000000000&amount_base_units=5&fee_base_units=2&nonce=1&expires_at_height=100"
        )
        .is_none());
        assert!(maybe_postgres_read_model_http_response(
            None,
            "GET",
            "/api/v1/transactions/2222222222222222222222222222222222222222222222222222222222222222"
        )
        .is_none());
        assert!(maybe_postgres_read_model_http_response(
            None,
            "GET",
            "/api/v1/wallet/transactions/2222222222222222222222222222222222222222222222222222222222222222/status"
        )
        .is_none());
        assert!(maybe_postgres_read_model_http_response(
            None,
            "GET",
            "/api/v1/iso20022/transactions/2222222222222222222222222222222222222222222222222222222222222222/status"
        )
        .is_none());
        assert!(maybe_postgres_read_model_http_response(
            None,
            "GET",
            "/api/v1/iso20022/payment-initiation/preview?tx_hash=2222222222222222222222222222222222222222222222222222222222222222"
        )
        .is_none());
        assert!(maybe_postgres_read_model_http_response(
            None,
            "GET",
            "/api/v1/iso20022/accounts/xriqdev1alice00000000000/statement?from=1970-01-01T00:00:00Z&to=1970-01-01T00:00:02Z"
        )
        .is_none());
        assert!(
            maybe_postgres_read_model_http_response(None, "GET", "/api/v1/accounts?limit=5")
                .is_none()
        );
        assert!(
            maybe_postgres_read_model_http_response(None, "GET", "/api/v1/snapshots?limit=5")
                .is_none()
        );
        assert!(maybe_postgres_read_model_http_response(
            None,
            "GET",
            "/api/v1/snapshots/current-indexed-chain"
        )
        .is_none());
        assert!(maybe_postgres_read_model_http_response(
            None,
            "GET",
            "/api/v1/wallet/accounts?limit=5"
        )
        .is_none());
        assert!(maybe_postgres_read_model_http_response(
            None,
            "GET",
            "/api/v1/wallet/accounts/xriqdev1alice00000000000/balance"
        )
        .is_none());
        assert!(maybe_postgres_read_model_http_response(
            None,
            "GET",
            "/api/v1/accounts/xriqdev1alice00000000000"
        )
        .is_none());
        assert!(maybe_postgres_read_model_http_response(
            None,
            "GET",
            "/api/v1/accounts/xriqdev1alice00000000000/transactions?limit=5"
        )
        .is_none());
        assert!(maybe_postgres_read_model_http_response(
            None,
            "GET",
            "/api/v1/wallet/accounts/xriqdev1alice00000000000/history?limit=5"
        )
        .is_none());
    }

    #[test]
    fn parser_rejects_unknown_or_duplicate_flags() {
        let unknown =
            RequestConfig::parse(&["--chain-file", "target/xriq.bin", "--format", "json"])
                .unwrap_err();
        assert!(unknown.contains("unknown flag: --format"));

        let duplicate = ServeConfig::parse(&[
            "--chain-file",
            "target/a.bin",
            "--chain-file",
            "target/b.bin",
        ])
        .unwrap_err();
        assert!(duplicate.contains("duplicate flag: --chain-file"));
    }

    #[test]
    fn request_line_parser_requires_method_target_and_http_version() {
        assert_eq!(
            parse_http_request_line("GET /api/v1/health HTTP/1.1").unwrap(),
            ("GET", "/api/v1/health")
        );
        assert!(parse_http_request_line("GET /api/v1/health").is_err());
        assert!(parse_http_request_line("GET /api/v1/health NOTHTTP").is_err());
    }

    #[test]
    fn bad_request_response_is_http_json() {
        let response = bad_request_response("missing HTTP target");

        assert_eq!(response.status_code, 400);
        assert_eq!(response.reason, "Bad Request");
        assert!(response.body.contains("\"code\": \"bad_request\""));
        assert!(response.body.contains("missing HTTP target"));
        assert!(response
            .to_http_response()
            .starts_with("HTTP/1.1 400 Bad Request\r\n"));
    }
}
