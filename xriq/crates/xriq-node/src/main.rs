use std::{env, process};

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.first().map(String::as_str) == Some("serve-readonly") {
        match xriq_node::parse_private_devnet_http_server_config(&args[1..]) {
            Ok(config) => {
                if let Err(error) = xriq_node::run_private_devnet_readonly_http_server(config) {
                    eprintln!("error=http server failed: {error}");
                    process::exit(1);
                }
            }
            Err(error) => {
                eprintln!("error={error}");
                eprintln!("{}", xriq_node::node_help_text());
                process::exit(1);
            }
        }
        return;
    }

    match xriq_node::run_node_command(args.iter().map(String::as_str)) {
        Ok(output) => println!("{output}"),
        Err(error) => {
            if xriq_node::node_runner_args_request_json(&args) {
                eprintln!(
                    "{}",
                    xriq_node::render_node_runner_error_json(&args, &error)
                );
            } else {
                eprintln!("error={error}");
                eprintln!("{}", xriq_node::node_help_text());
            }
            process::exit(1);
        }
    }
}
