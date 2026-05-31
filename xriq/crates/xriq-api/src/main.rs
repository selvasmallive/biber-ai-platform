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
    pending_mempool_entries_from_tsv, product_api_http_response, ApiHttpResponse, XriqApiService,
    MEMPOOL_READONLY_WARNING, SNAPSHOT_READONLY_WARNING,
};
use xriq_core::{Address, XriqAmount};
use xriq_indexer::index_private_devnet_store;
use xriq_storage::FileChainStore;

const DEFAULT_BIND: &str = "127.0.0.1:8090";
const POSTGRES_READ_MODEL_STATUS_ROUTE: &str = "/api/v1/admin/postgres/read-model-status";
const POSTGRES_NODE_STATUS_ROUTE: &str = "/api/v1/admin/node/status";
const POSTGRES_INDEXER_STATUS_ROUTE: &str = "/api/v1/admin/indexer/status";
const POSTGRES_AUDIT_EVENTS_ROUTE: &str = "/api/v1/admin/audit-events";
const POSTGRES_EXPLORER_OVERVIEW_ROUTE: &str = "/api/v1/explorer/overview";
const POSTGRES_BLOCKS_ROUTE: &str = "/api/v1/blocks";
const POSTGRES_TRANSACTIONS_ROUTE: &str = "/api/v1/transactions";
const POSTGRES_MEMPOOL_ROUTE: &str = "/api/v1/mempool";
const POSTGRES_TRANSACTION_DETAIL_PREFIX: &str = "/api/v1/transactions/";
const POSTGRES_WALLET_TRANSACTION_PREFIX: &str = "/api/v1/wallet/transactions/";
const POSTGRES_WALLET_TRANSACTION_STATUS_SUFFIX: &str = "/status";
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
    let response = product_api_http_response(&service, config.method, config.target);

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
    };
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
                if let Err(error) = handle_connection(&runtime, stream) {
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
}

fn handle_connection(runtime: &LocalApiRuntime<'_>, mut stream: TcpStream) -> Result<(), String> {
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
    runtime: &LocalApiRuntime<'_>,
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

    product_api_http_response(&runtime.service, method, target)
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

fn postgres_snapshot_name_from_path(path: &str) -> Option<&str> {
    let snapshot_name = path.strip_prefix(POSTGRES_SNAPSHOT_DETAIL_PREFIX)?;
    (!snapshot_name.is_empty() && !snapshot_name.contains('/')).then_some(snapshot_name)
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
    let is_account_detail = path
        .strip_prefix(POSTGRES_ACCOUNT_DETAIL_PREFIX)
        .is_some_and(|address| !address.is_empty() && !address.contains('/'));
    let is_account_history = postgres_account_history_address_from_path(path).is_some();
    let is_wallet_account_balance =
        postgres_wallet_account_balance_address_from_path(path).is_some();
    let is_wallet_account_history =
        postgres_wallet_account_history_address_from_path(path).is_some();
    let is_snapshot_detail = postgres_snapshot_name_from_path(path).is_some();
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
            | POSTGRES_ACCOUNTS_ROUTE
            | POSTGRES_WALLET_ACCOUNTS_ROUTE
            | POSTGRES_SNAPSHOTS_ROUTE,
            None,
        ) => return None,
        (_, None) if is_transaction_detail => return None,
        (_, None) if is_wallet_transaction_status => return None,
        (_, None) if is_account_history => return None,
        (_, None) if is_wallet_account_balance => return None,
        (_, None) if is_wallet_account_history => return None,
        (_, None) if is_account_detail => return None,
        (_, None) if is_snapshot_detail => return None,
        (
            POSTGRES_READ_MODEL_STATUS_ROUTE
            | POSTGRES_NODE_STATUS_ROUTE
            | POSTGRES_INDEXER_STATUS_ROUTE
            | POSTGRES_AUDIT_EVENTS_ROUTE
            | POSTGRES_EXPLORER_OVERVIEW_ROUTE
            | POSTGRES_BLOCKS_ROUTE
            | POSTGRES_TRANSACTIONS_ROUTE
            | POSTGRES_MEMPOOL_ROUTE
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
    let account_detail_address = path
        .strip_prefix(POSTGRES_ACCOUNT_DETAIL_PREFIX)
        .filter(|address| !address.is_empty() && !address.contains('/'));
    let account_history_address = postgres_account_history_address_from_path(path);
    let wallet_account_balance_address = postgres_wallet_account_balance_address_from_path(path);
    let wallet_account_history_address = postgres_wallet_account_history_address_from_path(path);
    let snapshot_detail_name = postgres_snapshot_name_from_path(path);
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
        "postgres transaction detail" | "postgres wallet transaction status"
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

fn help_text() -> String {
    [
        "xriq-api private-devnet commands:",
        "  xriq-api request --chain-file <path> [--pending-file <path>] [--alice-balance <base-units>] [--method GET] --target <api-path>",
        "  xriq-api request-postgres [--docker-container xriq-postgres] [--database xriq_phase1_1_smoke] [--method GET] --target /api/v1/admin/postgres/read-model-status|/api/v1/admin/node/status|/api/v1/admin/indexer/status|/api/v1/admin/audit-events?limit=5|/api/v1/explorer/overview|/api/v1/blocks?limit=5|/api/v1/transactions?limit=5|/api/v1/mempool?limit=5|/api/v1/transactions/<tx_hash>|/api/v1/wallet/transactions/<tx_hash>/status|/api/v1/accounts?limit=5|/api/v1/accounts/<address>|/api/v1/accounts/<address>/transactions?limit=5|/api/v1/wallet/accounts?limit=5|/api/v1/wallet/accounts/<address>/balance|/api/v1/wallet/accounts/<address>/history?limit=5|/api/v1/snapshots?limit=5|/api/v1/snapshots/<snapshot_name>",
        "  xriq-api serve-readonly --chain-file <path> [--pending-file <path>] [--alice-balance <base-units>] [--bind 127.0.0.1:8090] [--postgres-docker-container <container> --postgres-database <database>]",
        "",
        "Examples:",
        "  xriq-api request --chain-file target/xriq-devnet.bin --alice-balance 100 --target /api/v1/health",
        "  xriq-api request-postgres --target /api/v1/admin/postgres/read-model-status",
        "  xriq-api request-postgres --target /api/v1/admin/node/status",
        "  xriq-api request-postgres --target /api/v1/admin/indexer/status",
        "  xriq-api request-postgres --target /api/v1/admin/audit-events?limit=5",
        "  xriq-api request-postgres --target /api/v1/explorer/overview",
        "  xriq-api request-postgres --target /api/v1/blocks?limit=5",
        "  xriq-api request-postgres --target /api/v1/transactions?limit=5",
        "  xriq-api request-postgres --target /api/v1/mempool?limit=5",
        "  xriq-api request-postgres --target /api/v1/transactions/<tx_hash>",
        "  xriq-api request-postgres --target /api/v1/wallet/transactions/<tx_hash>/status",
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
struct ServeConfig<'a> {
    chain_file: &'a str,
    pending_file: Option<&'a str>,
    alice_balance: Option<XriqAmount>,
    bind: &'a str,
    postgres_read_model: Option<PostgresReadModelConfig<'a>>,
}

impl<'a> ServeConfig<'a> {
    fn parse(args: &'a [&'a str]) -> Result<Self, String> {
        let flags = FlagParser::parse(args)?;
        flags.reject_unknown(&[
            "--chain-file",
            "--pending-file",
            "--alice-balance",
            "--bind",
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
        })
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

        let error = RequestConfig::parse(&["--chain-file", "target/xriq.bin"]).unwrap_err();
        assert!(error.contains("missing required flag: --target"));
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
