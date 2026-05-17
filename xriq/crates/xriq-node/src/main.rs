use std::{env, process};

fn main() {
    match xriq_node::run_node_command(env::args().skip(1)) {
        Ok(output) => println!("{output}"),
        Err(error) => {
            eprintln!("error={error}");
            eprintln!("{}", xriq_node::node_help_text());
            process::exit(1);
        }
    }
}
