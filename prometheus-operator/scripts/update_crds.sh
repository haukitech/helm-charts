#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

FILES=(
  'monitoring.coreos.com_alertmanagerconfigs.yaml'
  'monitoring.coreos.com_alertmanagers.yaml'
  'monitoring.coreos.com_podmonitors.yaml'
  'monitoring.coreos.com_probes.yaml'
  'monitoring.coreos.com_prometheusagents.yaml'
  'monitoring.coreos.com_prometheuses.yaml'
  'monitoring.coreos.com_prometheusrules.yaml'
  'monitoring.coreos.com_scrapeconfigs.yaml'
  'monitoring.coreos.com_servicemonitors.yaml'
  'monitoring.coreos.com_thanosrulers.yaml'
)

version=$(grep '^appVersion' "${SCRIPT_DIR}/../Chart.yaml" | sed 's/^appVersion: //g' | tr -d \")

for filename in "${FILES[@]}"; do
  source_url="https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/v${version}/example/prometheus-operator-crd/${filename}"
  dest="${SCRIPT_DIR}/../crds/${filename}"

  echo "Downloading ${source_url}" >&2
  if ! curl --silent --show-error --fail --output "$dest" "$source_url"; then
    echo "Failed to download ${source_url}" >&2
    exit 1
  fi
done
