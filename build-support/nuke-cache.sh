#!/usr/bin/env bash
 function nuke_if_too_big() {
   path=$1
   limit_mb=$2
   size_mb=$(du -m -d0 "${path}" | cut -f 1)
   if (( size_mb > limit_mb )); then
     echo "${path} is too large (${size_mb}mb), nuking it."
     nuke_prefix="$(dirname "${path}")/$(basename "${path}").nuke"
     nuke_path=$(mktemp -d "${nuke_prefix}.XXXXXX")
     mv "${path}" "${nuke_path}/"
     rm -rf "${nuke_prefix}.*"
   fi
  }

nuke_if_too_big ~/.cache/nce 512
nuke_if_too_big ~/.cache/pants/named_caches 1024