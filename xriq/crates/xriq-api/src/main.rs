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
};
use xriq_core::XriqAmount;
use xriq_indexer::index_private_devnet_store;
use xriq_storage::FileChainStore;

const DEFAULT_BIND: &str = "127.0.0.1:8090";
const POSTGRES_READ_MODEL_STATUS_ROUTE: &str = "/api/v1/admin/postgres/read-model-status";
const POSTGRES_READ_MODEL_WARNING: &str =
    "local-private-devnet-postgres-read-only-preview-no-mutation";

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

fn maybe_postgres_read_model_http_response(
    config: Option<&PostgresReadModelConfig<'_>>,
    method: &str,
    target: &str,
) -> Option<Result<ApiHttpResponse, String>> {
    let path = target.split('?').next().unwrap_or(target);
    if path != POSTGRES_READ_MODEL_STATUS_ROUTE {
        return None;
    }

    let Some(config) = config else {
        return Some(Ok(postgres_read_model_disabled_response()));
    };

    Some(postgres_read_model_http_response(config, method, target))
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
    if path != POSTGRES_READ_MODEL_STATUS_ROUTE {
        return Ok(local_api_error_response(
            404,
            "not_found",
            "XRIQ Postgres read-model endpoint not found",
        ));
    }

    let output = docker_psql_query(
        config.docker_container,
        config.database,
        postgres_read_model_status_sql(),
        "postgres read-model status",
    )?;
    let values = parse_key_value_lines(&output, "postgres read-model status")?;
    let body = render_postgres_read_model_status_json(config, &values)?;
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
SELECT 'audit_events=' || count(*) FROM xriq_audit_events;\n\
SELECT 'indexer_runs=' || count(*) FROM xriq_indexer_runs;\n\
SELECT 'latest_height=' || COALESCE(MAX(height)::text, 'none') FROM xriq_blocks;\n\
SELECT 'latest_block_hash=' || COALESCE((SELECT block_hash FROM xriq_blocks ORDER BY height DESC LIMIT 1), 'none');\n\
SELECT 'indexer_status=' || COALESCE((SELECT status FROM xriq_indexer_runs ORDER BY completed_at DESC NULLS LAST, started_at DESC LIMIT 1), 'unknown');\n"
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
        audit_events,
        indexer_runs
    ))
}

fn required_u64(values: &BTreeMap<String, String>, key: &str) -> Result<u64, String> {
    values
        .get(key)
        .ok_or_else(|| format!("postgres read-model status: missing {key}"))?
        .parse::<u64>()
        .map_err(|_| format!("postgres read-model status: invalid integer for {key}"))
}

fn optional_u64_json(values: &BTreeMap<String, String>, key: &str) -> Result<String, String> {
    match values.get(key).map(String::as_str) {
        Some("none") | None => Ok("null".to_string()),
        Some(value) => value
            .parse::<u64>()
            .map(|number| number.to_string())
            .map_err(|_| format!("postgres read-model status: invalid integer for {key}")),
    }
}

fn optional_string_json(values: &BTreeMap<String, String>, key: &str) -> Result<String, String> {
    match values.get(key).map(String::as_str) {
        Some("none") | None => Ok("null".to_string()),
        Some(value) => Ok(json_string(value)),
    }
}

fn help_text() -> String {
    [
        "xriq-api private-devnet commands:",
        "  xriq-api request --chain-file <path> [--pending-file <path>] [--alice-balance <base-units>] [--method GET] --target <api-path>",
        "  xriq-api request-postgres [--docker-container xriq-postgres] [--database xriq_phase1_1_smoke] [--method GET] --target /api/v1/admin/postgres/read-model-status",
        "  xriq-api serve-readonly --chain-file <path> [--pending-file <path>] [--alice-balance <base-units>] [--bind 127.0.0.1:8090] [--postgres-docker-container <container> --postgres-database <database>]",
        "",
        "Examples:",
        "  xriq-api request --chain-file target/xriq-devnet.bin --alice-balance 100 --target /api/v1/health",
        "  xriq-api request-postgres --target /api/v1/admin/postgres/read-model-status",
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
        assert!(body.contains("\"indexer_status\": \"completed\""));
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
