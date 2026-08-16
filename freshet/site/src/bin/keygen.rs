//! Generate the production signing keypair.
//!
//! Run once, ever. The public half is compiled into every copy of Freshet, so
//! replacing it later invalidates every licence already in customers' hands —
//! this is not a key you rotate casually.
//!
//! ```text
//! cargo run --bin keygen -- ~/freshet-signing-key.hex
//! ```
//!
//! The private half is written to the path you name, with a deliberate refusal
//! to write anywhere inside the repository. Losing it means never being able to
//! issue another licence; leaking it means anyone can. Put it in Secret Manager
//! and delete the local copy.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use freshet_license::sign::SigningKey;
use rand::RngCore;

fn main() -> ExitCode {
    let Some(out) = std::env::args().nth(1).map(PathBuf::from) else {
        eprintln!("usage: keygen <path-for-private-key>");
        return ExitCode::FAILURE;
    };

    if let Err(why) = refuse_unsafe_destination(&out) {
        eprintln!("refusing to write there: {why}");
        return ExitCode::FAILURE;
    }

    // OS entropy. Not seeded, not derived from anything, not reproducible —
    // every property that makes the rest of the test suite deterministic is
    // exactly wrong here.
    let mut seed = [0u8; 32];
    rand::rngs::OsRng.fill_bytes(&mut seed);

    let signing = SigningKey::from_bytes(&seed);
    let public = signing.verifying_key().to_bytes();

    if let Err(e) = fs::write(&out, format!("{}\n", hex::encode(seed))) {
        eprintln!("could not write {}: {e}", out.display());
        return ExitCode::FAILURE;
    }
    restrict_permissions(&out);

    println!("Private key written to {}", out.display());
    println!();
    println!("1. Load it into Secret Manager, then delete the local copy:");
    println!();
    println!("   gcloud secrets create freshet-signing-key --data-file={}", out.display());
    println!("   rm {}", out.display());
    println!();
    println!("2. Paste this into crates/freshet-license/src/sign.rs, replacing");
    println!("   PRODUCTION_PUBLIC_KEY. Until you do, every licence is rejected.");
    println!();
    println!("pub const PRODUCTION_PUBLIC_KEY: [u8; 32] = [");
    for row in public.chunks(8) {
        let cells: Vec<String> = row.iter().map(|b| format!("0x{b:02x}")).collect();
        println!("    {},", cells.join(", "));
    }
    println!("];");
    println!();
    println!("Rebuild and reship the app after changing it. Licences signed by");
    println!("this key are worthless to a build that has the old one.");

    ExitCode::SUCCESS
}

/// Stop the obvious catastrophe: a private key committed to git.
///
/// Checked by walking up for a `.git` directory rather than by pattern-matching
/// the path, because the mistake people actually make is a relative path that
/// happens to land in the repo, not a path with "repo" in the name.
fn refuse_unsafe_destination(out: &Path) -> Result<(), String> {
    if out.exists() {
        return Err(format!(
            "{} already exists. Refusing to overwrite what may be the key \
             every issued licence depends on.",
            out.display()
        ));
    }

    let absolute = if out.is_absolute() {
        out.to_path_buf()
    } else {
        std::env::current_dir()
            .map_err(|e| e.to_string())?
            .join(out)
    };

    let mut dir = absolute.parent().map(Path::to_path_buf);
    while let Some(d) = dir {
        if d.join(".git").exists() {
            return Err(format!(
                "{} is inside a git repository ({}). A signing key must never \
                 be committable. Write it outside the repo.",
                absolute.display(),
                d.display()
            ));
        }
        dir = d.parent().map(Path::to_path_buf);
    }

    Ok(())
}

#[cfg(unix)]
fn restrict_permissions(path: &Path) {
    use std::os::unix::fs::PermissionsExt;
    let _ = fs::set_permissions(path, fs::Permissions::from_mode(0o600));
}

#[cfg(not(unix))]
fn restrict_permissions(_path: &Path) {
    // Windows inherits the user profile's ACL, which is already user-only for
    // paths under the home directory. Saying nothing is better than pretending
    // to have tightened something.
}
