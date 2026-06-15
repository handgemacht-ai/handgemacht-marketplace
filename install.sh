#!/usr/bin/env sh
# havi installer — downloads the latest public server binary into ~/.local/bin/havi.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/handgemacht-ai/handgemacht-marketplace/main/install.sh | sh
set -eu

REPO=${HAVI_REPO:-handgemacht-ai/handgemacht-marketplace}
INSTALL_DIR=${HAVI_INSTALL_DIR:-$HOME/.local/bin}

err() {
  printf 'havi-install: %s\n' "$*" >&2
  exit 1
}

info() {
  printf 'havi-install: %s\n' "$*"
}

uname_s=$(uname -s)
uname_m=$(uname -m)

case "$uname_s" in
  Darwin) os=darwin ;;
  Linux)  os=linux ;;
  *) err "unsupported OS: $uname_s (only macOS and Linux are supported)" ;;
esac

case "$uname_m" in
  x86_64 | amd64)        arch=amd64 ;;
  aarch64 | arm64)       arch=arm64 ;;
  *) err "unsupported architecture: $uname_m" ;;
esac

archive="havi-${os}-${arch}.tar.gz"
base="https://github.com/${REPO}/releases/latest/download"
download_url="${base}/${archive}"
checksum_url="${base}/checksums.txt"

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT

info "downloading ${archive}"
if ! curl -fsSL -o "${tmpdir}/${archive}" "${download_url}"; then
  err "download failed: ${download_url}"
fi

info "downloading checksums.txt"
if ! curl -fsSL -o "${tmpdir}/checksums.txt" "${checksum_url}"; then
  err "checksum download failed: ${checksum_url}"
fi

info "verifying checksum"
expected=$(grep " ${archive}\$" "${tmpdir}/checksums.txt" | awk '{print $1}')
if [ -z "${expected}" ]; then
  err "checksum for ${archive} not found in checksums.txt"
fi

if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "${tmpdir}/${archive}" | awk '{print $1}')
elif command -v shasum >/dev/null 2>&1; then
  actual=$(shasum -a 256 "${tmpdir}/${archive}" | awk '{print $1}')
else
  err "no sha256 tool found (need sha256sum or shasum)"
fi

if [ "${expected}" != "${actual}" ]; then
  err "checksum mismatch (expected ${expected}, got ${actual})"
fi

info "extracting"
tar -C "${tmpdir}" -xzf "${tmpdir}/${archive}"
if [ ! -f "${tmpdir}/havi" ]; then
  err "binary 'havi' not found in archive"
fi

target_dir="${INSTALL_DIR}"
if [ ! -d "${target_dir}" ]; then
  mkdir -p "${target_dir}"
fi

if [ ! -w "${target_dir}" ]; then
  if [ -w /usr/local/bin ]; then
    info "${target_dir} not writable; falling back to /usr/local/bin"
    target_dir=/usr/local/bin
  else
    err "${target_dir} is not writable and /usr/local/bin requires sudo. Set HAVI_INSTALL_DIR or run with appropriate permissions."
  fi
fi

mv "${tmpdir}/havi" "${target_dir}/havi"
chmod +x "${target_dir}/havi"

installed_version=$("${target_dir}/havi" --version 2>/dev/null || echo unknown)
info "installed havi (${installed_version}) to ${target_dir}/havi"

case ":${PATH}:" in
  *":${target_dir}:"*) ;;
  *)
    info "note: ${target_dir} is not on your PATH. Add this to your shell rc:"
    info "  export PATH=\"${target_dir}:\$PATH\""
    ;;
esac

info "next steps:"
info "  havi serve --daemon            # start in background (data dir: \${HAVI_DATA_DIR:-~/.havi})"
info "  curl http://localhost:8090/health"
