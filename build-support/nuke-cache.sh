#!/usr/bin/env bash

set -euo pipefail


function nuke_if_too_big() {
  local path=$1
  local limit_mb=$2
  local size_mb
  local nuke_path
  local nuke_prefix

  if [[ ! -d "${path}" ]]; then
    return 0
  fi

  size_mb=$(du -sm "${path}" | cut -f1)

  if (( size_mb > limit_mb )); then
    echo "${path} is too large (${size_mb}mb), nuking it."
    nuke_prefix="$(dirname "${path}")/$(basename "${path}").nuke"
    nuke_path=$(mktemp -d "${nuke_prefix}.XXXXXX")
    mv "${path}" "${nuke_path}/"
    rm -rf "${nuke_prefix}.*"
  fi
}


nuke_if_too_big "${HOME}/.cache/nce" 512
nuke_if_too_big "${PANTS_NAMED_CACHES_DIR:-${HOME}/.cache/pants/named_caches}" 1024
