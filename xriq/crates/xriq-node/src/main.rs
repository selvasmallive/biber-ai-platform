use std::{env, process};

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
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
