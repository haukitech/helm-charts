#!/usr/bin/env python
# Copyright 2024 Hauki Tech sp. z o.o.
# SPDX-License-Identifier: Apache-2.0

import re
import string
import textwrap
from pathlib import Path

import httpx
import yaml
from yaml.representer import SafeRepresenter


class LiteralStr(str):
    pass


def literal_str_representer(dumper: SafeRepresenter, data):
    node = dumper.represent_str(data)
    if "\n" in data:
        node.style = "|"
    return node


SCRIPT_DIR = Path(__file__).parent
SOURCE_DIR = SCRIPT_DIR / ".temp"
CHARTS_DIR = SCRIPT_DIR.parent / "charts"

VERSION = "v0.14.0"
BASE_URL = f"https://raw.githubusercontent.com/prometheus-operator/kube-prometheus/{VERSION}/manifests"

RULES = [
    ("alertmanager", "alertmanager-prometheusRule.yaml"),
    ("prometheus", "prometheus-prometheusRule.yaml"),
    ("prometheus-operator", "prometheusOperator-prometheusRule.yaml"),
]

COPYRIGHT = """\
# Copyright 2024 Hauki Tech sp. z o.o.
# SPDX-License-Identifier: Apache-2.0
# This file is generated based on the source code of the https://github.com/prometheus-operator/kube-prometheus/
# project, that is licensed under terms of the Apache License 2.0
"""

HEADER = string.Template("""\
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: {{ include "$chart.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "$chart.labels" . | nindent 4 }}
spec:
  groups:
""")


def escape_helm(value: str):
    return re.sub(r"(\{\{|\}\})", r"{{`\1`}}", value)


def fixup_rule_labels(rule: str):
    rule = re.sub(r'job="[a-zA-Z0-9-_]+"', 'job="{{ $job }}"', rule)
    rule = re.sub(r'namespace="[a-zA-Z0-9-_]+"', 'namespace="{{ $namespace }}"', rule)
    return rule


def main():
    yaml.add_representer(LiteralStr, literal_str_representer, Dumper=yaml.SafeDumper)

    SOURCE_DIR.mkdir(exist_ok=True)

    for chart, filename in RULES:
        src_path = SOURCE_DIR / filename

        # Download file
        if not src_path.exists():
            url = f"{BASE_URL}/{filename}"
            print("Downloading", url)
            responce = httpx.get(url)
            responce.raise_for_status()
            with src_path.open('wb') as file:
                for chunk in responce.iter_bytes():
                    file.write(chunk)

        # Process file
        with src_path.open() as file:
            manifest = yaml.safe_load(file)

        out_path = CHARTS_DIR / chart / "templates" / "prometheus_rule.yaml"
        with out_path.open("w") as out:
            out.write(COPYRIGHT)

            out.write('{{ $job := include "' + chart + '.fullname" . }}\n')
            out.write('{{ $namespace := .Release.Namespace }}\n')

            header = HEADER.substitute(chart=chart)
            out.write(header)

            for group in manifest["spec"]["groups"]:
                out.write(f"  - name: {group['name']}\n")
                out.write(f"    rules:\n")

                for rule in group["rules"]:
                    out.write("    {{- if not (.Values.rules.disabled." + rule['alert'] + " | default false) }}\n")

                    rule["annotations"]["description"] = escape_helm(rule["annotations"]["description"])

                    rule["expr"] = LiteralStr(rule["expr"])

                    rule_text = yaml.safe_dump([rule])
                    rule_text = fixup_rule_labels(rule_text)
                    rule_text = textwrap.indent(rule_text, ' ' * 4)
                    out.write(rule_text)

                    out.write('    {{- end }}\n')


if __name__ == '__main__':
    main()
