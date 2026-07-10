# Multi-stage build for the XRIQ staging-devnet services.
# Build context is the xriq/ workspace directory.
# Produces a small runtime image containing the node, API, and indexer binaries
# plus the psql client (used by the indexer to populate Cloud SQL).

FROM rust:1-slim-bookworm AS builder
WORKDIR /build
COPY . .
RUN cargo build --release --locked -p xriq-node -p xriq-api -p xriq-indexer

FROM debian:bookworm-slim AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# Non-root runtime user (uid 10001 must own the mounted /data on the host).
RUN useradd --system --uid 10001 --create-home xriq
COPY --from=builder /build/target/release/xriq-node /usr/local/bin/xriq-node
COPY --from=builder /build/target/release/xriq-api /usr/local/bin/xriq-api
COPY --from=builder /build/target/release/xriq-indexer /usr/local/bin/xriq-indexer
USER xriq
WORKDIR /data
EXPOSE 8090
# Command is provided by the run wrappers (xriq-api / xriq-indexer / xriq-node).
CMD ["xriq-api", "help"]
