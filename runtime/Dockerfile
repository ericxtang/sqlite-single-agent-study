FROM rust:1.95.0-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends python3 ripgrep git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && find /usr -iname '*sqlite*' -type f -delete \
    && useradd --create-home --uid 1000 agent \
    && mkdir -p /work /docs /opt/utility-vendor
WORKDIR /opt/utility-vendor
COPY utility-Cargo.toml Cargo.toml
COPY Cargo.lock Cargo.lock
RUN mkdir src && printf 'fn main() {}\n' > src/main.rs && cargo vendor --locked /opt/vendor > vendor-config.toml
RUN mkdir -p /home/agent/.cargo && cp vendor-config.toml /home/agent/.cargo/config.toml \
    && printf '\n[net]\noffline = true\n' >> /home/agent/.cargo/config.toml \
    && chown -R agent:agent /home/agent /work
ENV CARGO_HOME=/home/agent/.cargo
ENV RUSTUP_HOME=/usr/local/rustup
ENV PATH=/usr/local/cargo/bin:/usr/local/bin:/usr/bin:/bin
USER agent
WORKDIR /work
CMD ["sleep", "infinity"]
