use std::{env, fmt::Write as _, process};

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

fn help_text() -> String {
    [
        "xriq-indexer private-devnet commands:",
        "  xriq-indexer replay --chain-file <path> [--alice-balance <base-units>] [--format text|json|sql]",
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
