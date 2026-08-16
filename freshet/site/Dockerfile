# Build context is the repository root (`freshet/`), not `site/`, because the
# service depends on `crates/freshet-license` by path — the same crate the
# desktop app verifies with. Building it from a copy would let the two drift.
#
#   docker build -f site/Dockerfile -t freshet-site .

FROM rust:1.83-slim-bookworm AS build

RUN apt-get update \
 && apt-get install -y --no-install-recommends pkg-config \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src

COPY crates/freshet-license crates/freshet-license
COPY site site

WORKDIR /src/site
RUN cargo build --release --bin freshet-site

# Distroless: no shell, no package manager, nothing for a compromised process
# to pivot with. This container holds the licence signing key in memory, so its
# attack surface is worth minimising more than most.
FROM gcr.io/distroless/cc-debian12

COPY --from=build /src/site/target/release/freshet-site /freshet-site

# Cloud Run overrides this; declaring it keeps local runs honest.
ENV PORT=8080
EXPOSE 8080

USER nonroot
ENTRYPOINT ["/freshet-site"]
