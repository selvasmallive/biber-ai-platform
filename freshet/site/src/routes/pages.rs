//! The public pages.
//!
//! Deliberately server-rendered with no JavaScript and no third-party anything.
//! A site selling privacy-preserving tax software that loads an analytics script
//! is making a claim its own homepage contradicts, and people in this market
//! check.

use axum::response::Html;

fn shell(title: &str, body: &str) -> Html<String> {
    Html(format!(
        "<!doctype html><html lang=en><meta charset=utf-8>
<meta name=viewport content=\"width=device-width,initial-scale=1\">
<title>{title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 16px/1.6 system-ui, sans-serif; margin: 0 auto; padding: 2rem 1.25rem;
          max-width: 42rem; }}
  h1 {{ font-size: 2rem; line-height: 1.2; }}
  h2 {{ margin-top: 2.5rem; }}
  code {{ font-size: 0.9em; }}
  .lede {{ font-size: 1.15rem; }}
  .box {{ border: 1px solid currentColor; border-radius: 6px; padding: 1rem 1.25rem;
          margin: 1.5rem 0; opacity: .95; }}
  button, input {{ font: inherit; padding: .5rem .75rem; }}
  footer {{ margin-top: 4rem; font-size: .9rem; opacity: .75; }}
</style>
{body}
<footer>
  <p>Freshet &middot; <a href=\"/\">Home</a> &middot; <a href=\"/recover\">Find my licence</a>
     &middot; <a href=\"/privacy\">Privacy</a></p>
</footer>"
    ))
}

pub async fn home() -> Html<String> {
    shell(
        "Freshet — Canadian tax software that stays on your computer",
        r#"<h1>Your tax return never leaves your computer.</h1>

<p class=lede>Freshet prepares your Canadian T1 return on your own machine.
Not in our cloud, because there isn't one.</p>

<div class=box>
  <strong>Freshet is not yet certified by CRA and cannot file a return.</strong>
  <p>Certification for the 2026 tax year is in progress. Until CRA issues a
  confirmation letter, the software will refuse to transmit anything — that
  refusal is built in, not a policy we ask you to trust.</p>
</div>

<h2>Preparing is free. Filing needs a licence.</h2>

<p>You can install Freshet, enter a whole return, see every line and every
number, and compare scenarios, without paying anything. A licence is what lets
you file the finished return.</p>

<p>One licence covers <strong>five returns</strong>, so a household — you, a
spouse, adult children, a parent — is one purchase, not five.</p>

<h2>The licence works whether or not we do</h2>

<p>When you buy, we email you the licence itself. You paste it into Freshet and
it is checked on your own machine. There is no activation step you have to get
through, no account to sign in to, and nothing to phone home to.</p>

<p>This matters most in the week it would matter most: if our servers were down
on 29 April, your copy of Freshet would not notice.</p>

<h2>What we hold about you</h2>

<p>Your email address, your licence, and the payment processor's order
reference. Not your return, not your SIN, not your income — none of that is
ever sent to us, because the software has nowhere to send it.</p>

<p><a href="/recover">Lost your licence?</a></p>"#,
    )
}

pub async fn recover_form() -> Html<String> {
    shell(
        "Find my Freshet licence",
        r#"<h1>Find my licence</h1>

<p>Enter the email address you bought with and we will send your licence to
that address.</p>

<form method=post action=/api/recover-form>
  <input name=email type=email required placeholder="you@example.ca" size=30>
  <button>Send it again</button>
</form>

<div class=box>
  <p>We can only send it to the address that bought it. We will never show a
  licence on this page — otherwise anyone who guessed your email could collect
  it.</p>
</div>"#,
    )
}

pub async fn privacy() -> Html<String> {
    shell(
        "Freshet privacy",
        r#"<h1>Privacy</h1>

<h2>What the software holds</h2>
<p>Your return stays on your computer, in an encrypted file only your machine
can open. We cannot read it, recover it, or be compelled to produce it, because
we never receive it.</p>

<p>If you switch on the AI advisor, the line numbers and amounts of your return
are sent to the AI provider <em>you</em> chose and gave a key for. Identifying
details — name, SIN, address, employer, date of birth — are stripped before
anything is sent, and the software refuses to send at all if that stripping
fails. Nothing is proxied through us.</p>

<h2>What this website holds</h2>
<ul>
  <li>Your email address</li>
  <li>The licence issued to it</li>
  <li>Which installations activated it, if you chose to activate online</li>
  <li>The payment processor's order reference</li>
</ul>

<p>Card details go to the payment processor and never reach us. We keep no
name, no address, and no analytics.</p>

<h2>Getting it deleted</h2>
<p>Write to <a href="mailto:privacy@freshettax.ca">privacy@freshettax.ca</a> and
we will erase everything above. Your installed copy keeps working, because it
does not depend on us.</p>

<p>Freshet operates in Canada and is subject to PIPEDA.</p>"#,
    )
}

pub async fn health() -> &'static str {
    "ok"
}
