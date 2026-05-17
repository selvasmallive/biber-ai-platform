use std::{env, process};

fn main() {
    match xriq_wallet::run_wallet_command(env::args().skip(1)) {
        Ok(output) => println!("{output}"),
        Err(error) => {
            eprintln!("error={error}");
            eprintln!("{}", xriq_wallet::help_text());
            process::exit(1);
        }
    }
}
