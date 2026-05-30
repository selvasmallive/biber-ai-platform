use std::{
    env,
    fmt::Write as _,
    io::{Read, Write},
    net::{TcpListener, TcpStream},
    path::Path,
    process,
};

use xriq_api::{product_api_http_response, ApiHttpResponse, XriqApiService};
use xriq_core::XriqAmount;
use xriq_indexer::index_private_devnet_store;
use xriq_storage::FileChainStore;

const DEFAULT_BIND: &str = "127.0.0.1:8090";

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
        Some("serve-readonly") => run_serve_readonly(&args[1..]),
        Some(command) => Err(format!("unknown command: {command}")),
        None => Err("missing command".to_string()),
    }
}

fn run_request(args: &[&str]) -> Result<String, String> {
    let config = RequestConfig::parse(args)?;
    let service = build_service(config.chain_file, config.alice_balance)?;
    let response = product_api_http_response(&service, config.method, config.target);

    Ok(format!(
        "status_code={}\nreason={}\nbody={}",
        response.status_code, response.reason, response.body
    ))
}

fn run_serve_readonly(args: &[&str]) -> Result<String, String> {
    let config = ServeConfig::parse(args)?;
    let service = build_service(config.chain_file, config.alice_balance)?;
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
                if let Err(error) = handle_connection(&service, stream) {
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
    Ok(XriqApiService::new(snapshot))
}

fn handle_connection(service: &XriqApiService, mut stream: TcpStream) -> Result<(), String> {
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
        Ok((method, target)) => product_api_http_response(service, method, target),
        Err(message) => bad_request_response(&message),
    };

    stream
        .write_all(response.to_http_response().as_bytes())
        .map_err(|error| format!("could not write response: {error}"))?;
    stream
        .flush()
        .map_err(|error| format!("could not flush response: {error}"))
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

fn help_text() -> String {
    [
        "xriq-api private-devnet commands:",
        "  xriq-api request --chain-file <path> [--alice-balance <base-units>] [--method GET] --target <api-path>",
        "  xriq-api serve-readonly --chain-file <path> [--alice-balance <base-units>] [--bind 127.0.0.1:8090]",
        "",
        "Examples:",
        "  xriq-api request --chain-file target/xriq-devnet.bin --alice-balance 100 --target /api/v1/health",
        "  xriq-api serve-readonly --chain-file target/xriq-devnet.bin --alice-balance 100",
    ]
    .join("\n")
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct RequestConfig<'a> {
    chain_file: &'a str,
    alice_balance: Option<XriqAmount>,
    method: &'a str,
    target: &'a str,
}

impl<'a> RequestConfig<'a> {
    fn parse(args: &'a [&'a str]) -> Result<Self, String> {
        let flags = FlagParser::parse(args)?;
        flags.reject_unknown(&["--chain-file", "--alice-balance", "--method", "--target"])?;
        Ok(Self {
            chain_file: flags.required("--chain-file")?,
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
struct ServeConfig<'a> {
    chain_file: &'a str,
    alice_balance: Option<XriqAmount>,
    bind: &'a str,
}

impl<'a> ServeConfig<'a> {
    fn parse(args: &'a [&'a str]) -> Result<Self, String> {
        let flags = FlagParser::parse(args)?;
        flags.reject_unknown(&["--chain-file", "--alice-balance", "--bind"])?;
        Ok(Self {
            chain_file: flags.required("--chain-file")?,
            alice_balance: flags
                .optional("--alice-balance")
                .map(parse_amount)
                .transpose()?,
            bind: flags.optional("--bind").unwrap_or(DEFAULT_BIND),
        })
    }
}

fn parse_amount(value: &str) -> Result<XriqAmount, String> {
    let base_units = value
        .parse::<u128>()
        .map_err(|_| format!("invalid amount: {value}"))?;
    Ok(XriqAmount::from_base_units(base_units))
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
        assert_eq!(config.alice_balance.unwrap().base_units(), 100);
        assert_eq!(config.method, "GET");
        assert_eq!(config.target, "/api/v1/health");

        let error = RequestConfig::parse(&["--chain-file", "target/xriq.bin"]).unwrap_err();
        assert!(error.contains("missing required flag: --target"));
    }

    #[test]
    fn serve_config_defaults_to_localhost_private_devnet_port() {
        let config = ServeConfig::parse(&["--chain-file", "target/xriq.bin"]).unwrap();

        assert_eq!(config.chain_file, "target/xriq.bin");
        assert_eq!(config.alice_balance, None);
        assert_eq!(config.bind, DEFAULT_BIND);
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
