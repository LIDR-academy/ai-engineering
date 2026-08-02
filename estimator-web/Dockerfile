# syntax=docker/dockerfile:1
# check=error=true

# Development-only Dockerfile. Production deployment is out of scope for this
# project; if it ever comes back, regenerate via `bin/rails app:update:bin`
# or `rails new --dockerfile` and adapt to Kamal/Thruster.

ARG RUBY_VERSION=3.4.4
FROM docker.io/library/ruby:$RUBY_VERSION-slim

WORKDIR /rails

# Toolchain + runtime libraries (single layer, no recommends).
# - build-essential / git / pkg-config / libyaml-dev: native gem compilation
#   (bootsnap, debug, nokogiri).
# - libpq-dev / postgresql-client: pg driver + psql/pg_isready for debugging.
# - libvips / libjemalloc2: parity with what Rails-generated prod image carried.
# - curl: HEALTHCHECK and ad-hoc debugging.
RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y \
        build-essential \
        curl \
        git \
        libjemalloc2 \
        libpq-dev \
        libvips \
        libyaml-dev \
        pkg-config \
        postgresql-client && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

ENV BUNDLE_PATH=/usr/local/bundle \
    BUNDLE_JOBS=4 \
    BUNDLE_RETRY=3 \
    RAILS_ENV=development \
    RAILS_LOG_TO_STDOUT=1

# Install all bundle groups (development + test included).
# Source code is NOT copied — it enters via bind mount from compose. The image
# only carries gems + foreman + toolchain (mirrors the estimator/ pattern that
# only ships .venv).
#
# BuildKit cache mount keeps downloaded gem archives across rebuilds so an
# unchanged Gemfile.lock is near-instant even from another worktree.
COPY Gemfile Gemfile.lock ./
RUN --mount=type=cache,target=/usr/local/bundle/cache \
    bundle install

# foreman is intentionally outside bundle (bin/dev convention).
RUN gem install foreman

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:3000/up || exit 1

CMD ["bin/dev"]
