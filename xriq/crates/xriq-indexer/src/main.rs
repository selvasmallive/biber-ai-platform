use std::{
    env,
    fmt::Write as _,
    fs,
    io::Write as _,
    process::{self, Command, Stdio},
};

use xriq_core::XriqAmount;
use xriq_indexer::{index_private_devnet_store, postgres_write_plan, IndexedChainSnapshot};
use xriq_storage::FileChainStore;

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    match run(args.iter().map(String::as_str)) {
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
        Some("replay") => run_replay(&args[1..]),
        Some("apply-postgres") => run_apply_postgres(&args[1..]),
        Some(command) => Err(format!("unknown command: {command}")),
        None => Err("missing command".to_string()),
    }
}

fn run_replay(args: &[&str]) -> Result<String, String> {
    let flags = FlagParser::parse(args)?;
    flags.reject_unknown(&["--chain-file", "--alice-balance", "--format"])?;
    let chain_file = flags.required("--chain-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(parse_amount)
        .transpose()?;
    let format = OutputFormat::parse(flags.optional("--format"))?;
    let store = FileChainStore::open(chain_file)
        .map_err(|error| format!("could not open chain file {chain_file}: {error:?}"))?;
    let snapshot = index_private_devnet_store(&store, alice_balance)
        .map_err(|error| format!("index replay failed: {error}"))?;

    Ok(match format {
        OutputFormat::Text => render_snapshot_text(&snapshot),
        OutputFormat::Json => render_snapshot_json(&snapshot),
        OutputFormat::Sql => postgres_write_plan(&snapshot)
            .map_err(|error| format!("could not build postgres write plan: {error}"))?
            .to_sql(),
    })
}

fn run_apply_postgres(args: &[&str]) -> Result<String, String> {
    let flags = FlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--alice-balance",
        "--schema-file",
        "--database-url",
        "--database-url-env",
        "--dry-run",
    ])?;
    let chain_file = flags.required("--chain-file")?;
    let schema_file = flags.optional("--schema-file").unwrap_or("db/schema.sql");
    let dry_run = parse_bool(flags.optional("--dry-run").unwrap_or("true"))?;
    let database_url = database_url_from_flags(&flags)?;
    let schema_sql = fs::read_to_string(schema_file)
        .map_err(|error| format!("could not read schema file {schema_file}: {error}"))?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(parse_amount)
        .transpose()?;
    let store = FileChainStore::open(chain_file)
        .map_err(|error| format!("could not open chain file {chain_file}: {error:?}"))?;
    let snapshot = index_private_devnet_store(&store, alice_balance)
        .map_err(|error| format!("index replay failed: {error}"))?;
    let plan = postgres_write_plan(&snapshot)
        .map_err(|error| format!("could not build postgres write plan: {error}"))?;

    if !dry_run {
        let database_url = database_url
            .value
            .as_ref()
            .ok_or_else(|| "database url is required when --dry-run false".to_string())?;
        run_psql_sql(database_url, &schema_sql, "schema")?;
        run_psql_sql(database_url, &plan.to_sql(), "indexer write plan")?;
    }

    Ok(render_apply_postgres_summary(&ApplyPostgresSummary {
        dry_run,
        schema_file,
        database_url_configured: database_url.value.is_some(),
        database_url_source: database_url.source.as_str(),
        current_height: snapshot.current_height,
        latest_block_hash: snapshot.latest_block_hash.as_str(),
        blocks_indexed: snapshot.summary.blocks_indexed,
        transactions_indexed: snapshot.summary.transactions_indexed,
        write_plan_statements: plan.statements.len(),
    }))
}

fn help_text() -> String {
    [
        "xriq-indexer private-devnet commands:",
        "  xriq-indexer replay --chain-file <path> [--alice-balance <base-units>] [--format text|json|sql]",
        "  xriq-indexer apply-postgres --chain-file <path> [--alice-balance <base-units>] [--schema-file db/schema.sql] [--database-url-env XRIQ_POSTGRES_URL|--database-url <url>] [--dry-run true|false]",
    ]
    .join("\n")
}

fn render_snapshot_text(snapshot: &IndexedChainSnapshot) -> String {
    let mut output = String::new();
    writeln!(&mut output, "warning={}", snapshot.warning).expect("write to String");
    writeln!(&mut output, "environment={}", snapshot.environment).expect("write to String");
    writeln!(&mut output, "chain_id={}", snapshot.chain_id).expect("write to String");
    writeln!(&mut output, "current_height={}", snapshot.current_height).expect("write to String");
    writeln!(
        &mut output,
        "latest_block_hash={}",
        snapshot.latest_block_hash
    )
    .expect("write to String");
    writeln!(&mut output, "state_root={}", snapshot.state_root).expect("write to String");
    writeln!(&mut output, "blocks_seen={}", snapshot.summary.blocks_seen).expect("write to String");
    writeln!(
        &mut output,
        "blocks_indexed={}",
        snapshot.summary.blocks_indexed
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "transactions_seen={}",
        snapshot.summary.transactions_seen
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "transactions_indexed={}",
        snapshot.summary.transactions_indexed
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "account_transactions_indexed={}",
        snapshot.summary.account_transactions_indexed
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "account_balances_indexed={}",
        snapshot.summary.account_balances_indexed
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "audit_events_indexed={}",
        snapshot.summary.audit_events_indexed
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "read_model_blocks={}",
        snapshot.read_model.blocks.len()
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "read_model_transactions={}",
        snapshot.read_model.transactions.len()
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "read_model_accounts={}",
        snapshot.read_model.accounts.len()
    )
    .expect("write to String");
    write!(
        &mut output,
        "read_model_account_balances={}",
        snapshot.read_model.account_balances.len()
    )
    .expect("write to String");
    output
}

fn render_snapshot_json(snapshot: &IndexedChainSnapshot) -> String {
    let mut output = String::new();
    output.push_str("{\n");
    output.push_str("  \"format_version\": \"xriq-indexer-replay-json-v1\",\n");
    output.push_str("  \"command\": \"replay\",\n");
    output.push_str("  \"warning\": ");
    output.push_str(&json_string(snapshot.warning));
    output.push_str(",\n");
    output.push_str("  \"environment\": ");
    output.push_str(&json_string(snapshot.environment));
    output.push_str(",\n");
    output.push_str("  \"chain_id\": ");
    output.push_str(&json_string(&snapshot.chain_id));
    output.push_str(",\n");
    output.push_str("  \"current_height\": ");
    output.push_str(&snapshot.current_height.to_string());
    output.push_str(",\n");
    output.push_str("  \"latest_block_hash\": ");
    output.push_str(&json_string(&snapshot.latest_block_hash));
    output.push_str(",\n");
    output.push_str("  \"state_root\": ");
    output.push_str(&json_string(&snapshot.state_root));
    output.push_str(",\n");
    output.push_str("  \"summary\": {\n");
    push_summary_json(snapshot, &mut output);
    output.push_str("  },\n");
    output.push_str("  \"read_model_counts\": {\n");
    writeln!(
        &mut output,
        "    \"blocks\": {},",
        snapshot.read_model.blocks.len()
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"transactions\": {},",
        snapshot.read_model.transactions.len()
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"accounts\": {},",
        snapshot.read_model.accounts.len()
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"account_balances\": {},",
        snapshot.read_model.account_balances.len()
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"account_transactions\": {},",
        snapshot.read_model.account_transactions.len()
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"audit_events\": {}",
        snapshot.read_model.audit_events.len()
    )
    .expect("write to String");
    output.push_str("  }\n}");
    output
}

fn push_summary_json(snapshot: &IndexedChainSnapshot, output: &mut String) {
    writeln!(
        output,
        "    \"blocks_seen\": {},",
        snapshot.summary.blocks_seen
    )
    .expect("write to String");
    writeln!(
        output,
        "    \"blocks_indexed\": {},",
        snapshot.summary.blocks_indexed
    )
    .expect("write to String");
    writeln!(
        output,
        "    \"transactions_seen\": {},",
        snapshot.summary.transactions_seen
    )
    .expect("write to String");
    writeln!(
        output,
        "    \"transactions_indexed\": {},",
        snapshot.summary.transactions_indexed
    )
    .expect("write to String");
    writeln!(
        output,
        "    \"account_transactions_indexed\": {},",
        snapshot.summary.account_transactions_indexed
    )
    .expect("write to String");
    writeln!(
        output,
        "    \"account_balances_seen\": {},",
        snapshot.summary.account_balances_seen
    )
    .expect("write to String");
    writeln!(
        output,
        "    \"account_balances_indexed\": {},",
        snapshot.summary.account_balances_indexed
    )
    .expect("write to String");
    writeln!(
        output,
        "    \"audit_events_indexed\": {},",
        snapshot.summary.audit_events_indexed
    )
    .expect("write to String");
    writeln!(
        output,
        "    \"from_height\": {},",
        json_optional_u64(snapshot.summary.from_height)
    )
    .expect("write to String");
    writeln!(
        output,
        "    \"to_height\": {}",
        json_optional_u64(snapshot.summary.to_height)
    )
    .expect("write to String");
}

fn parse_amount(value: &str) -> Result<XriqAmount, String> {
    let base_units = value
        .parse::<u128>()
        .map_err(|_| format!("invalid amount: {value}"))?;
    Ok(XriqAmount::from_base_units(base_units))
}

fn parse_bool(value: &str) -> Result<bool, String> {
    match value {
        "true" => Ok(true),
        "false" => Ok(false),
        value => Err(format!("invalid boolean: {value}; expected true or false")),
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct DatabaseUrl {
    value: Option<String>,
    source: String,
}

fn database_url_from_flags(flags: &FlagParser<'_>) -> Result<DatabaseUrl, String> {
    let explicit = flags.optional("--database-url");
    let env_name = flags
        .optional("--database-url-env")
        .unwrap_or("XRIQ_POSTGRES_URL");
    if explicit.is_some() && flags.optional("--database-url-env").is_some() {
        return Err("use either --database-url or --database-url-env, not both".to_string());
    }

    if let Some(value) = explicit {
        return Ok(DatabaseUrl {
            value: Some(value.to_string()),
            source: "--database-url".to_string(),
        });
    }

    Ok(DatabaseUrl {
        value: env::var(env_name)
            .ok()
            .filter(|value| !value.trim().is_empty()),
        source: env_name.to_string(),
    })
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ApplyPostgresSummary<'a> {
    dry_run: bool,
    schema_file: &'a str,
    database_url_configured: bool,
    database_url_source: &'a str,
    current_height: u64,
    latest_block_hash: &'a str,
    blocks_indexed: usize,
    transactions_indexed: usize,
    write_plan_statements: usize,
}

fn render_apply_postgres_summary(summary: &ApplyPostgresSummary<'_>) -> String {
    let mut output = String::new();
    writeln!(&mut output, "warning=private-devnet-only-no-public-token").expect("write to String");
    writeln!(&mut output, "environment=private-devnet").expect("write to String");
    writeln!(
        &mut output,
        "mode={}",
        if summary.dry_run { "dry-run" } else { "apply" }
    )
    .expect("write to String");
    writeln!(&mut output, "schema_file={}", summary.schema_file).expect("write to String");
    writeln!(
        &mut output,
        "database_url_source={}",
        summary.database_url_source
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "database_url_configured={}",
        summary.database_url_configured
    )
    .expect("write to String");
    writeln!(&mut output, "current_height={}", summary.current_height).expect("write to String");
    writeln!(
        &mut output,
        "latest_block_hash={}",
        summary.latest_block_hash
    )
    .expect("write to String");
    writeln!(&mut output, "blocks_indexed={}", summary.blocks_indexed).expect("write to String");
    writeln!(
        &mut output,
        "transactions_indexed={}",
        summary.transactions_indexed
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "write_plan_statements={}",
        summary.write_plan_statements
    )
    .expect("write to String");
    writeln!(&mut output, "schema_applied={}", !summary.dry_run).expect("write to String");
    write!(&mut output, "write_plan_applied={}", !summary.dry_run).expect("write to String");
    output
}

fn run_psql_sql(database_url: &str, sql: &str, label: &str) -> Result<(), String> {
    let mut child = Command::new("psql")
        .arg(database_url)
        .arg("-v")
        .arg("ON_ERROR_STOP=1")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| format!("could not start psql for {label}: {error}"))?;
    child
        .stdin
        .take()
        .ok_or_else(|| format!("could not open psql stdin for {label}"))?
        .write_all(sql.as_bytes())
        .map_err(|error| format!("could not send {label} SQL to psql: {error}"))?;
    let output = child
        .wait_with_output()
        .map_err(|error| format!("could not wait for psql {label}: {error}"))?;
    if output.status.success() {
        return Ok(());
    }

    let stderr = String::from_utf8_lossy(&output.stderr).replace(database_url, "<database-url>");
    Err(format!("psql failed while applying {label}: {stderr}"))
}

fn json_optional_u64(value: Option<u64>) -> String {
    value
        .map(|number| number.to_string())
        .unwrap_or_else(|| "null".to_string())
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

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum OutputFormat {
    Text,
    Json,
    Sql,
}

impl OutputFormat {
    fn parse(value: Option<&str>) -> Result<Self, String> {
        match value.unwrap_or("text") {
            "text" => Ok(Self::Text),
            "json" => Ok(Self::Json),
            "sql" => Ok(Self::Sql),
            value => Err(format!(
                "invalid format: {value}; expected text, json, or sql"
            )),
        }
    }
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
