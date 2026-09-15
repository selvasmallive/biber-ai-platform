//! The T2 interview against the forms it is meant to fill in.
//!
//! The questions live in `shared/t2-interview.ts`, shared by the desktop app
//! and the browser build, because that is where the labels and hints belong. The fact keys in that file are not
//! presentation, though — they are the join between a text box and a line on
//! the return, and nothing at runtime checks them.
//!
//! A wrong key is the worst kind of defect this product can have. Nothing
//! errors: the engine finds no fact under `gifi.800`, reads zero, and computes
//! a return that is internally consistent, professionally formatted, and
//! wrong. The user has no way to see it. So the join is checked here, from the
//! side that knows the truth.
//!
//! Reading a TypeScript file from a Rust test is unusual. The alternative was
//! to duplicate the list in Rust and keep the two in step by hand, which is
//! the same bug with an extra step.

use std::collections::BTreeSet;

fn interview_facts() -> BTreeSet<String> {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../../shared/t2-interview.ts");
    let source = std::fs::read_to_string(path)
        .unwrap_or_else(|e| panic!("cannot read the T2 interview at {path}: {e}"));

    let mut out = BTreeSet::new();
    for (index, _) in source.match_indices("fact: \"") {
        let rest = &source[index + "fact: \"".len()..];
        let end = rest.find('"').expect("unterminated fact key");
        out.insert(rest[..end].to_string());
    }

    assert!(
        !out.is_empty(),
        "no fact keys found; the interview file's shape must have changed, \
         and this test would otherwise pass by finding nothing"
    );

    out
}

fn form_facts() -> BTreeSet<String> {
    freshet_taxdata::t2_forms("on")
        .expect("Ontario T2 forms")
        .input_facts()
}

/// Every question the browser asks corresponds to something the form reads.
#[test]
fn the_interview_does_not_ask_for_facts_the_form_never_reads() {
    let asked = interview_facts();
    let read = form_facts();

    let stray: Vec<&String> = asked.difference(&read).collect();

    assert!(
        stray.is_empty(),
        "the T2 interview asks for facts no line reads, so whatever is \
         typed into them is silently discarded: {stray:?}"
    );
}

/// And every figure the form needs is asked for somewhere.
///
/// The other direction, and the one that costs a customer money: a fact the
/// form reads but the interview never collects is read as zero, and a return
/// missing an amount still looks complete.
#[test]
fn the_interview_asks_for_every_fact_the_form_reads() {
    let asked = interview_facts();
    let read = form_facts();

    let missing: Vec<&String> = read.difference(&asked).collect();

    assert!(
        missing.is_empty(),
        "the T2 reads facts the interview never asks for, so they are \
         always zero: {missing:?}"
    );
}
