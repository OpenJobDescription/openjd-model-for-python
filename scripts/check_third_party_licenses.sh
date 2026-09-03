#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Copyright by contributors to this project.
# SPDX-License-Identifier: Apache-2.0
#
# Regenerates THIRD-PARTY-LICENSES.txt by combining:
#
#   * Python runtime dependencies (resolved by installing the wheel
#     into a temporary venv and running `pip-licenses --format=json`)
#   * Rust runtime dependencies (rendered by `cargo about generate
#     about.hbs` against the workspace's Cargo.lock)
#
# Both sources emit the same `**name; version -- url` format used by
# the pre-existing committed file. The Python section comes first
# (matching the historical layout) followed by the Rust section.
#
# Fails (in CI mode) if the regenerated file differs from the committed
# THIRD-PARTY-LICENSES.txt. Use --update to overwrite in place.
#
# Usage:
#   scripts/check_third_party_licenses.sh          # verify (CI mode)
#   scripts/check_third_party_licenses.sh --update # regenerate in place
#
# Requires:
#   * cargo-about (install with `cargo install cargo-about --locked --features cli`)
#   * jq
#   * Python 3.9+ on PATH (creates an ephemeral venv for pip-licenses)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

if ! command -v cargo-about >/dev/null 2>&1; then
    echo "error: cargo-about not found on PATH." >&2
    echo "Install it with: cargo install cargo-about --locked --features cli" >&2
    exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
    echo "error: jq not found on PATH." >&2
    exit 2
fi

mode="verify"
if [[ $# -ge 1 ]]; then
    case "$1" in
        --update|-u)
            mode="update"
            ;;
        -h|--help)
            sed -n '2,28p' "$0"
            exit 0
            ;;
        *)
            echo "error: unknown argument: $1" >&2
            exit 2
            ;;
    esac
fi

OUTPUT_FILE="THIRD-PARTY-LICENSES.txt"

# Workspace files used in regeneration.
python_section="$(mktemp)"
rust_section_raw="$(mktemp)"
rust_section="$(mktemp)"
generated="$(mktemp)"
venv_dir="$(mktemp -d)"
wheel_dir="$(mktemp -d)"
trap 'rm -rf "$python_section" "$rust_section_raw" "$rust_section" "$generated" "$venv_dir" "$wheel_dir"' EXIT

# ── Python deps ───────────────────────────────────────────────────────
#
# Build the wheel into an ephemeral location, install it (which pulls in
# the runtime dep closure declared in pyproject.toml's
# `[project.dependencies]`), then run pip-licenses against the venv.
# This avoids depending on the developer's global environment and
# guarantees the section reflects the actual shipped dep set.

echo "Building wheel for Python dep resolution..."
python -m pip wheel --no-deps --quiet -w "$wheel_dir" . >/dev/null

echo "Creating ephemeral venv..."
python -m venv "$venv_dir"
"$venv_dir/bin/pip" install --quiet --upgrade pip >/dev/null
"$venv_dir/bin/pip" install --quiet "$wheel_dir"/openjd_model-*.whl pip-licenses >/dev/null

# Render Python deps in the same format cargo-about's about.hbs emits:
#
#   ** {name}; version {version} -- https://pypi.org/project/{name}/
#   {license_text}
#
#   ------
#
# Skip the wheel under test plus the tooling deps that pip-licenses
# pulls in for itself.
"$venv_dir/bin/pip-licenses" \
    --format=json \
    --with-license-file --no-license-path --with-notice-file \
    --ignore-packages \
        openjd-model openjd_model \
        pip pip-licenses prettytable wcwidth tomli \
    | jq -r '
        sort_by(.Name | ascii_downcase) | .[] |
        "** \(.Name); version \(.Version) -- https://pypi.org/project/\(.Name)/\n\(.LicenseText)\n------"
    ' > "$python_section"

# ── Rust deps ─────────────────────────────────────────────────────────
#
# `cargo about` reads the workspace's Cargo.lock, the `about.toml`
# config (which excludes build- and dev-dependencies), and renders
# every unique (crate, license) pair through `about.hbs`.

echo "Generating Rust section via cargo about..."
cargo about generate \
    --config about.toml \
    --manifest-path rust-bindings/Cargo.toml \
    about.hbs > "$rust_section_raw"

# cargo-about's `private.ignore` flag only excludes workspace members
# marked `publish = false`. The bindings crate `openjd-python` is
# `publish = false` and so already filtered out, but if upstream
# crates ever appear as workspace members we strip them by name as a
# safety net (matches the openjd-rs pattern).
workspace_pattern="$(
    cargo metadata --no-deps --format-version=1 \
        --manifest-path rust-bindings/Cargo.toml \
        | jq -r '.packages[].name' \
        | tr -d '\r' \
        | paste -sd'|' -
)"
if [[ -z "$workspace_pattern" ]]; then
    echo "error: cargo metadata returned no workspace members." >&2
    exit 2
fi
awk -v re="^[*][*] ($workspace_pattern); version " '
    /^------$/ {
        if (kept > 0) { printf "%s", block; print "------" }
        block = ""; kept = 0; next
    }
    /^[*][*] / && $0 ~ re { next }
    /^[*][*] /            { block = block $0 "\n"; kept++; next }
                          { block = block $0 "\n" }
    END {
        if (kept > 0) printf "%s", block
    }
' "$rust_section_raw" > "$rust_section"

# ── Combine ───────────────────────────────────────────────────────────

{
    echo ""
    echo ""
    cat "$python_section"
    echo ""
    cat "$rust_section"
} > "$generated"

# Ensure consistent EOL. Rewritten through a temp file rather than `sed -i`,
# which needs a backup suffix on BSD sed and rejects one on GNU sed.
sed 's/\r//' "$generated" > "$generated.eol" && mv "$generated.eol" "$generated"

if [[ "$mode" == "update" ]]; then
    cp "$generated" "$OUTPUT_FILE"
    echo "Updated $OUTPUT_FILE."
    exit 0
fi

if ! diff -u "$OUTPUT_FILE" "$generated"; then
    echo >&2
    echo "$OUTPUT_FILE is out of date with respect to:" >&2
    echo "  * pyproject.toml [project.dependencies]" >&2
    echo "  * Cargo.lock (workspace)" >&2
    echo "Regenerate it with:" >&2
    echo "  scripts/check_third_party_licenses.sh --update" >&2
    exit 1
fi

echo "$OUTPUT_FILE is up to date."
