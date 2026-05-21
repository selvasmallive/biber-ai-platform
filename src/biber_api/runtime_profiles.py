from __future__ import annotations

from dataclasses import dataclass


API_ERROR_RESPONSE_PROFILE_ID = "api-error-response"
RUST_XRIQ_CODEGEN_PROFILE_ID = "rust-xriq-codegen"


@dataclass(frozen=True)
class RuntimeProfile:
    id: str
    label: str
    description: str
    instructions: str


_API_ERROR_RESPONSE_INSTRUCTIONS = """For API error-shape answers, include a top-level numeric `status` field and a
structured `detail` object.
Use machine-readable `detail.code` values.
For missing API keys, use a code that contains `api_key`, such as
`api_key_missing`, and do not echo secrets, token prefixes, headers, or raw
credential values.
For rate limits, use a code that contains `rate_limit` and include
`retry_after` timing.
Keep the answer concise and prefer a JSON example."""


_RUST_XRIQ_CODEGEN_INSTRUCTIONS = """Return only Rust code.
Format the answer so `cargo fmt --check` passes without changes.
Do not include prose, explanations, Markdown fences, or text after the Rust code.
Use only the Rust standard library and code visible in the prompt; do not use external crates such as `thiserror`.
Do not write `#[derive(thiserror::Error)]` or `#[error(...)]` attributes.
Prefer explicit structs, enums, and Result errors over derive macros from external crates.
If the prompt asks for a `pub fn ...`, define that function as a free public function, not only as an associated method inside an `impl`.
For `next_height(parent: &BlockHeader)`, write the body exactly in the compact rustfmt-stable shape:
`parent.height.checked_add(1)`
For `calculate_fee(byte_len: usize, fee_per_byte: u64)`, avoid type inference failures by writing:
`let byte_len_u64 = u64::try_from(byte_len).ok()?;`
`byte_len_u64.checked_mul(fee_per_byte)`
For simple validation helpers, keep error strings short and split long return expressions across lines so rustfmt does not change the output.
For ledger/account updates, compute all checked values first, avoid long single-line method chains, and commit mutations only after every check passes.
Never keep a mutable sender borrow alive while calling `accounts.entry(...)`; finish the sender update inside a short block, then update the recipient after that block ends.
Do not clone, shadow, replace, or reassign the `accounts: &mut HashMap<...>` parameter; mutate the provided map in place and never write `let mut accounts = accounts.clone()` or `*accounts = accounts`.
Debit the sender by `tx.amount + tx.fee`, credit the recipient with `tx.amount` only, and add only `tx.fee` to the fee sink."""


RUNTIME_PROFILES: tuple[RuntimeProfile, ...] = (
    RuntimeProfile(
        id=API_ERROR_RESPONSE_PROFILE_ID,
        label="API error response shape",
        description="Concise JSON-style API error answers with stable status/detail fields.",
        instructions=_API_ERROR_RESPONSE_INSTRUCTIONS,
    ),
    RuntimeProfile(
        id=RUST_XRIQ_CODEGEN_PROFILE_ID,
        label="Rust/XRIQ code generation",
        description="Rust-only XRIQ helper output shaped for rustfmt and borrow-checker safety.",
        instructions=_RUST_XRIQ_CODEGEN_INSTRUCTIONS,
    ),
)

RUNTIME_PROFILES_BY_ID = {profile.id: profile for profile in RUNTIME_PROFILES}


def available_runtime_profiles() -> list[dict[str, str]]:
    return [
        {
            "id": profile.id,
            "label": profile.label,
            "description": profile.description,
        }
        for profile in RUNTIME_PROFILES
    ]


def build_runtime_profiles_prompt(profile_ids: list[str]) -> str | None:
    selected: list[RuntimeProfile] = []
    seen: set[str] = set()
    for profile_id in profile_ids:
        if profile_id in seen:
            continue
        seen.add(profile_id)
        profile = RUNTIME_PROFILES_BY_ID.get(profile_id)
        if profile is not None:
            selected.append(profile)

    if not selected:
        return None

    parts = ["Runtime profiles requested by the client:"]
    for profile in selected:
        parts.append(f"[{profile.id}] {profile.instructions}")
    return "\n\n".join(parts)
