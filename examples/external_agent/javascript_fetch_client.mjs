#!/usr/bin/env node

const baseUrl = (process.env.BIBER_OPENAI_BASE_URL || "http://127.0.0.1:8000/v1").replace(/\/+$/, "");
const model = process.env.BIBER_MODEL || "biber-dev-core-v1";
const apiKey = process.env.BIBER_API_KEY || "";
const message = process.argv.slice(2).join(" ") || "Reply with one concise sentence confirming BIBER access.";

if (!apiKey) {
  console.error("Missing API key environment variable: BIBER_API_KEY");
  process.exit(2);
}

const chatCompletionsUrl = baseUrl.endsWith("/chat/completions")
  ? baseUrl
  : baseUrl.endsWith("/v1")
    ? `${baseUrl}/chat/completions`
    : `${baseUrl}/v1/chat/completions`;

const response = await fetch(chatCompletionsUrl, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${apiKey}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model,
    messages: [{ role: "user", content: message }],
    max_tokens: 120,
    temperature: 0,
    stream: false,
    use_mentor: false,
  }),
});

const text = await response.text();
if (!response.ok) {
  console.error(`BIBER request failed with HTTP ${response.status}: ${text}`);
  process.exit(1);
}

const payload = JSON.parse(text);
const content = payload.choices?.[0]?.message?.content || "";
console.log(content);
