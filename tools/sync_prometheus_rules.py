#!/usr/bin/env python
# Copyright 2024 Hauki Tech sp. z o.o.
# SPDX-License-Identifier: Apache-2.0
import dataclasses
import logging
import re
from typing import Any, TextIO
from dataclasses import dataclass
from pathlib import Path

import httpx
import yaml
import jinja2
from yaml.representer import SafeRepresenter

logger = logging.getLogger("main")

VERSION = "v0.14.0"
BASE_URL = (
    f"https://raw.githubusercontent.com/prometheus-operator/kube-prometheus/{VERSION}/manifests"
)

SCRIPT_DIR = Path(__file__).parent
CACHE_DIR = SCRIPT_DIR / ".cache"
CHARTS_DIR = SCRIPT_DIR.parent / "charts"
RULE_INDENT = 4


@dataclass
class RuleLabel:
    var_name: str
    var_value: str
    label_name: str = ""
    label_value: str | None = None

    def __post_init__(self):
        if not self.label_name:
            self.label_name = self.var_name


@dataclass
class ManifestSpec:
    filename: str
    chart: str
    values_prefix: str = ".Values"
    chart_subdir: str | None = None
    rule_labels: list[RuleLabel] = dataclasses.field(default_factory=list)

    def macros_prefix(self):
        if self.chart_subdir:
            return f"{self.chart}.{self.chart_subdir}"
        else:
            return self.chart


MANIFEST_SPECS = [
    ManifestSpec(
        "alertmanager-prometheusRule.yaml",
        "alertmanager",
        rule_labels=[
            RuleLabel("job", 'include "alertmanager.fullname" .'),
            RuleLabel("namespace", ".Release.Namespace"),
        ],
    ),
    ManifestSpec(
        "prometheus-prometheusRule.yaml",
        "prometheus",
        rule_labels=[
            RuleLabel("job", 'include "prometheus.fullname" .'),
            RuleLabel("namespace", ".Release.Namespace"),
        ],
    ),
    ManifestSpec(
        "prometheusOperator-prometheusRule.yaml",
        "prometheus-operator",
        rule_labels=[
            RuleLabel("job", 'include "prometheus-operator.fullname" .'),
            RuleLabel("namespace", ".Release.Namespace"),
        ],
    ),
    ManifestSpec(
        "nodeExporter-prometheusRule.yaml",
        "monitoring-stack",
        chart_subdir="node-exporter",
        values_prefix=".Values.nodeExporter",
        rule_labels=[
            RuleLabel("job", 'include "monitoring-stack.node-exporter.fullname" .'),
            RuleLabel("namespace", ".Release.Namespace"),
        ],
    ),
    ManifestSpec(
        "kubeStateMetrics-prometheusRule.yaml",
        "monitoring-stack",
        chart_subdir="kube-state-metrics",
        values_prefix=".Values.kubeStateMetrics",
        rule_labels=[
            RuleLabel("job", 'include "monitoring-stack.kube-state-metrics.fullname" .'),
            RuleLabel("namespace", ".Release.Namespace"),
        ],
    ),
    ManifestSpec(
        "kubernetesControlPlane-prometheusRule.yaml",
        "monitoring-stack",
        chart_subdir="kubernetes-control-plane",
        values_prefix=".Values.kubernetesControlPlane",
        rule_labels=[
            RuleLabel(
                "kubelet_job",
                'include "monitoring-stack.kubelet.name" .',
                label_name="job",
                label_value="kubelet",
            ),
            RuleLabel(
                "kube_controller_manager_job",
                'include "monitoring-stack.kube-controller-manager.name" .',
                label_name="job",
                label_value="kube-controller-manager",
            ),
            RuleLabel(
                "kube_scheduler_job",
                'include "monitoring-stack.kube-scheduler.name" .',
                label_name="job",
                label_value="kube-scheduler",
            ),
            RuleLabel(
                "kube_state_metrics_job",
                'include "monitoring-stack.kube-state-metrics.fullname" .',
                label_name="job",
                label_value="kube-state-metrics",
            ),
            RuleLabel(
                "node_exporter_job",
                'include "monitoring-stack.node-exporter.fullname" .',
                label_name="job",
                label_value="node-exporter",
            ),
            RuleLabel("namespace", ".Release.Namespace"),
        ],
    ),
]


class LiteralStr(str):
    pass


def str_representer(dumper: SafeRepresenter, data: str):
    node = dumper.represent_str(data)
    if "\n" in data:
        node.style = "|"
    return node


def literal_str_representer(dumper: SafeRepresenter, data: LiteralStr):
    node = dumper.represent_str(data)
    node.style = "|"
    return node


class HelmDumper(yaml.SafeDumper):
    def __init__(
        self,
        stream: TextIO,
        default_style: str | None = None,
        default_flow_style: bool = False,
        canonical: bool | None = None,
        indent: int | None = None,
        width: int | None = None,
        allow_unicode: bool | None = None,
        line_break: str | None = None,
        encoding: str = None,
        explicit_start: bool | None = None,
        explicit_end: bool | None = None,
        version: str | None = None,
        tags: list[str] | None = None,
        sort_keys: bool = True,
    ):
        if width is None:
            width = float("inf")
        super().__init__(
            stream,
            default_style=default_style,
            default_flow_style=default_flow_style,
            canonical=canonical,
            indent=indent,
            width=width,
            allow_unicode=allow_unicode,
            line_break=line_break,
            encoding=encoding,
            explicit_start=explicit_start,
            explicit_end=explicit_end,
            version=version,
            tags=tags,
            sort_keys=sort_keys,
        )


HelmDumper.add_representer(str, str_representer)
HelmDumper.add_representer(LiteralStr, literal_str_representer)


def escape_helm(value: str) -> str:
    return re.sub(r"(\{\{|\}\})", r"{{`\1`}}", value)


class LabelSub:
    def __init__(self, spec: ManifestSpec):
        self.spec = spec

    def __call__(self, match_: re.Match[str]) -> str:
        match_label, match_value = match_.groups()

        for rule_label in self.spec.rule_labels:
            if rule_label.label_name != match_label:
                continue
            if rule_label.label_value is not None and rule_label.label_value != match_value:
                continue
            return f'{match_label}="{{{{ ${rule_label.var_name} }}}}"'
        return match_.group(0)


def fixup_rule_labels(spec: ManifestSpec, rule: str) -> str:
    labels = {re.escape(rl.label_name) for rl in spec.rule_labels}
    expr = r'({})="([a-zA-Z0-9_-]+)"'.format("|".join(labels))
    return re.sub(expr, LabelSub(spec), rule)


def make_rule_path(rule: ManifestSpec) -> Path:
    path = CHARTS_DIR / rule.chart / "templates"
    if rule.chart_subdir is not None:
        path = path / rule.chart_subdir
    path = path / "prometheus_rule.yaml"
    return path


def download_rule_file(spec: ManifestSpec) -> Path:
    path = CACHE_DIR / spec.filename
    if path.exists():
        logger.info("Using cached rules file: %s", path)
        return path

    url = f"{BASE_URL}/{spec.filename}"

    logger.info("Downloading URL: %s", url)

    response = httpx.get(url)
    response.raise_for_status()

    with path.open("wb") as file:
        for chunk in response.iter_bytes():
            file.write(chunk)

    return path


@dataclass
class Rule:
    text: str
    alert: str | None = None


def process_rule(spec: ManifestSpec, rule: dict[str, Any]) -> Rule:
    rule["expr"] = LiteralStr(rule["expr"])

    # if description := rule.get("annotations", {}).get("description"):
    #     rule["annotations"]["description"] = escape_helm(description)

    rule_text = yaml.dump([rule], Dumper=HelmDumper)
    rule_text = escape_helm(rule_text)
    rule_text = fixup_rule_labels(spec, rule_text)

    return Rule(
        rule_text,
        alert=rule.get("alert"),
    )


@dataclass
class Group:
    name: str
    rules: list[Rule]


def process_group(spec: ManifestSpec, group: dict[str, Any]) -> Group:
    rules = [process_rule(spec, rule) for rule in group["rules"]]
    return Group(group["name"], rules)


def process_rules(
    spec: ManifestSpec, manifest: dict[str, Any], tpl: jinja2.Template, out: TextIO
) -> None:
    groups = [process_group(spec, group) for group in manifest["spec"]["groups"]]

    tpl_ctx = {
        "macros_prefix": spec.macros_prefix(),
        "values_prefix": spec.values_prefix,
        "rule_labels": spec.rule_labels,
        "groups": groups,
    }
    rules_text = tpl.render(tpl_ctx)
    out.write(rules_text)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    CACHE_DIR.mkdir(exist_ok=True)

    j2_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(SCRIPT_DIR / "templates"),
        keep_trailing_newline=True,
    )
    tpl = j2_env.get_template("prometheus-rule.yaml.j2")

    for spec in MANIFEST_SPECS:
        src_path = download_rule_file(spec)
        with src_path.open() as src_file:
            manifest = yaml.load(src_file, Loader=yaml.SafeLoader)

        dest_path = make_rule_path(spec)
        logger.info("Writing %s", dest_path)
        with dest_path.open("w") as out:
            process_rules(spec, manifest, tpl, out)


if __name__ == "__main__":
    main()
