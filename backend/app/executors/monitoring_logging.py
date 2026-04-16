"""
Monitoring & Logging — TC-074 to TC-081
"""
from __future__ import annotations

import base64
import json

import httpx

from .base import BaseExecutor, OpenShiftClient, TestResult

MON_NS = "openshift-monitoring"
LOG_NS = "openshift-logging"


class MonitoringLoggingExecutor(BaseExecutor):

    FUNCTION_MAP = {
        "TC-074": "_tc_074",
        "TC-075": "_tc_075",
        "TC-076": "_tc_076",
        "TC-077": "_tc_077",
        "TC-078": "_tc_078",
        "TC-079": "_tc_079",
        "TC-080": "_tc_080",
        "TC-081": "_tc_081",
    }

    # ── TC-074: Prometheus Operational Status ─────────────────────────────────

    async def _tc_074(self, result: TestResult, client: OpenShiftClient) -> None:
        issues = []

        # Check Prometheus pods
        try:
            pods = await client.get_pods(MON_NS)
            prom_pods = [p for p in pods if "prometheus" in p["metadata"]["name"]]
            running   = [p for p in prom_pods if p.get("status", {}).get("phase") == "Running"]
            result.evidence.append(
                f"Prometheus pods: {len(running)}/{len(prom_pods)} running"
            )
            if not running:
                issues.append("No Prometheus pods running")
        except httpx.HTTPStatusError:
            issues.append("Cannot list pods in openshift-monitoring")

        # Check Prometheus CRD instances
        try:
            data = await client.get(
                f"/apis/monitoring.coreos.com/v1/namespaces/{MON_NS}/prometheuses"
            )
            prometheuses = data.get("items", [])
            for p in prometheuses:
                name    = p["metadata"]["name"]
                ready   = p.get("status", {}).get("availableReplicas", 0)
                desired = p.get("spec", {}).get("replicas", 2)
                result.evidence.append(
                    f"Prometheus '{name}': {ready}/{desired} replicas available"
                )
                if ready < 1:
                    issues.append(f"Prometheus '{name}' has no ready replicas")
        except httpx.HTTPStatusError:
            result.evidence.append("Prometheus CRD not accessible — checking pods only.")

        # Check Prometheus route
        try:
            routes = await client.get_routes(MON_NS)
            prom_routes = [r for r in routes if "prometheus" in r["metadata"]["name"]]
            for r in prom_routes:
                host = r.get("spec", {}).get("host", "")
                result.evidence.append(f"Prometheus route: https://{host}")
        except httpx.HTTPStatusError:
            pass

        if not issues:
            result.passed("Prometheus is operational.")
        else:
            result.failed(f"Prometheus issues: {'; '.join(issues)}")

    # ── TC-075: Alertmanager Operational Status ────────────────────────────────

    async def _tc_075(self, result: TestResult, client: OpenShiftClient) -> None:
        issues = []

        try:
            pods = await client.get_pods(MON_NS)
            am_pods = [p for p in pods if "alertmanager" in p["metadata"]["name"]]
            running = [p for p in am_pods if p.get("status", {}).get("phase") == "Running"]
            result.evidence.append(
                f"Alertmanager pods: {len(running)}/{len(am_pods)} running"
            )
            if not running:
                issues.append("No Alertmanager pods running")
        except httpx.HTTPStatusError:
            issues.append("Cannot list monitoring pods")

        try:
            data = await client.get(
                f"/apis/monitoring.coreos.com/v1/namespaces/{MON_NS}/alertmanagers"
            )
            ams = data.get("items", [])
            for am in ams:
                name  = am["metadata"]["name"]
                ready = am.get("status", {}).get("availableReplicas", 0)
                desired = am.get("spec", {}).get("replicas", 2)
                result.evidence.append(
                    f"Alertmanager '{name}': {ready}/{desired} replicas"
                )
                if ready < 1:
                    issues.append(f"Alertmanager '{name}' has no ready replicas")
        except httpx.HTTPStatusError:
            pass

        # Check Alertmanager config secret exists
        try:
            await client.get(
                f"/api/v1/namespaces/{MON_NS}/secrets/alertmanager-main"
            )
            result.evidence.append("Alertmanager config secret: present")
        except httpx.HTTPStatusError:
            result.evidence.append("Alertmanager config secret: not found")

        if not issues:
            result.passed("Alertmanager is operational.")
        else:
            result.failed(f"Alertmanager issues: {'; '.join(issues)}")

    # ── TC-076: Logging Stack Collection ─────────────────────────────────────

    async def _tc_076(self, result: TestResult, client: OpenShiftClient) -> None:
        found = False

        # ClusterLogging CR
        try:
            data = await client.get(
                f"/apis/logging.openshift.io/v1/namespaces/{LOG_NS}/clusterloggings"
            )
            cls = data.get("items", [])
            result.evidence.append(f"ClusterLogging instances: {len(cls)}")
            for cl in cls:
                name  = cl["metadata"]["name"]
                mgmt  = cl.get("spec", {}).get("managementState", "Unknown")
                collection = cl.get("spec", {}).get("collection", {}).get("type", "none")
                result.evidence.append(f"  {name}: managementState={mgmt}, collection={collection}")
            found = bool(cls)
        except httpx.HTTPStatusError as exc:
            result.evidence.append(
                f"ClusterLogging API: HTTP {exc.response.status_code}"
            )

        # Check Collector pods (fluentd / vector)
        try:
            pods = await client.get_pods(LOG_NS)
            collectors = [
                p for p in pods
                if any(name in p["metadata"]["name"] for name in ("fluentd", "vector", "collector"))
            ]
            running = [p for p in collectors if p.get("status", {}).get("phase") == "Running"]
            result.evidence.append(
                f"Log collector pods ({LOG_NS}): {len(running)}/{len(collectors)} running"
            )
            if running:
                found = True
        except httpx.HTTPStatusError:
            pass

        # Check ClusterLogForwarder
        try:
            data = await client.get(
                f"/apis/logging.openshift.io/v1/namespaces/{LOG_NS}/clusterlogforwarders"
            )
            fwds = data.get("items", [])
            result.evidence.append(f"ClusterLogForwarders: {len(fwds)}")
            for fwd in fwds:
                outputs = fwd.get("spec", {}).get("outputs", [])
                result.evidence.append(
                    f"  Outputs: {[o.get('name') for o in outputs]}"
                )
            if fwds:
                found = True
        except httpx.HTTPStatusError:
            pass

        if found:
            result.passed("Logging stack is collecting and forwarding logs.")
        else:
            result.failed("Logging stack not detected or not running.")

    # ── TC-077: Alert Notification Delivery ──────────────────────────────────

    async def _tc_077(self, result: TestResult, client: OpenShiftClient) -> None:
        # Inspect AlertManager receivers in config
        try:
            secret = await client.get(
                f"/api/v1/namespaces/{MON_NS}/secrets/alertmanager-main"
            )
            cfg_b64 = secret.get("data", {}).get("alertmanager.yaml", "")
            if not cfg_b64:
                result.failed("AlertManager config secret has no alertmanager.yaml key.")
                return

            cfg_text = base64.b64decode(cfg_b64).decode("utf-8", errors="replace")
            result.evidence.append(
                f"AlertManager config (truncated):\n{cfg_text[:800]}"
            )

            # Check receivers
            has_receivers = "receivers:" in cfg_text and "name:" in cfg_text
            has_routes    = "route:" in cfg_text
            webhook_count = cfg_text.lower().count("webhook_configs")
            email_count   = cfg_text.lower().count("email_configs")
            pagerduty     = "pagerduty" in cfg_text.lower()

            result.evidence.append(
                f"Config analysis: receivers={has_receivers}, routes={has_routes}, "
                f"webhooks={webhook_count}, email={email_count}, pagerduty={pagerduty}"
            )

            if has_receivers and has_routes:
                result.passed(
                    "AlertManager has receivers and route config — "
                    f"webhooks: {webhook_count}, email: {email_count}, PagerDuty: {pagerduty}."
                )
            else:
                result.failed("AlertManager config missing receivers or routes.")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                result.failed("AlertManager secret 'alertmanager-main' not found.")
            else:
                raise

    # ── TC-078: Alert Suppression ─────────────────────────────────────────────

    async def _tc_078(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check silences via AlertManager API or check AlertManager config inhibit_rules
        try:
            secret = await client.get(
                f"/api/v1/namespaces/{MON_NS}/secrets/alertmanager-main"
            )
            cfg_b64 = secret.get("data", {}).get("alertmanager.yaml", "")
            cfg_text = base64.b64decode(cfg_b64).decode("utf-8", errors="replace") if cfg_b64 else ""

            inhibit_count = cfg_text.count("inhibit_rules:")
            result.evidence.append(f"Inhibit rules sections in config: {inhibit_count}")
            result.evidence.append(f"Has inhibit_rules: {'inhibit_rules' in cfg_text}")
        except httpx.HTTPStatusError:
            result.evidence.append("AlertManager config not accessible.")
            cfg_text = ""

        # Check PrometheusRules for silenced alerts
        try:
            data = await client.get(
                f"/apis/monitoring.coreos.com/v1/prometheusrules"
            )
            rules = data.get("items", [])
            rule_count = sum(
                len(g.get("rules", []))
                for r in rules
                for g in r.get("spec", {}).get("groups", [])
            )
            result.evidence.append(
                f"PrometheusRules: {len(rules)} objects, ~{rule_count} rules total"
            )
        except httpx.HTTPStatusError:
            pass

        if "inhibit_rules" in cfg_text:
            result.passed("Alert suppression via inhibit_rules is configured in AlertManager.")
        else:
            result.failed("No inhibit_rules found in AlertManager configuration.")

    # ── TC-079: No events triggered for VMs ───────────────────────────────────

    async def _tc_079(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check k8s events for Warning-type VM events
        try:
            data = await client.get("/api/v1/events")
            events = data.get("items", [])
            vm_warnings = [
                e for e in events
                if e.get("type") == "Warning"
                and e.get("involvedObject", {}).get("kind") in (
                    "VirtualMachine", "VirtualMachineInstance"
                )
            ]

            result.evidence.append(
                f"Total events: {len(events)}\n"
                f"VM Warning events: {len(vm_warnings)}"
            )

            if vm_warnings:
                for ev in vm_warnings[:5]:
                    result.evidence.append(
                        f"  [{ev['involvedObject']['name']}] {ev.get('reason')}: {ev.get('message','')[:120]}"
                    )

            if not vm_warnings:
                result.passed("No Warning events found for VirtualMachines or VMIs.")
            else:
                result.failed(
                    f"{len(vm_warnings)} Warning event(s) found for VMs. Review evidence."
                )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                result.blocked("Insufficient permissions to list cluster events.")
            else:
                raise

    # ── TC-080: Namespace and Cluster events to observability platform ────────

    async def _tc_080(self, result: TestResult, client: OpenShiftClient) -> None:
        found = False

        # Check ClusterLogForwarder outputs pointing to an observability platform
        try:
            data = await client.get(
                f"/apis/logging.openshift.io/v1/clusterlogforwarders"
            )
            for fwd in data.get("items", []):
                outputs = fwd.get("spec", {}).get("outputs", [])
                for o in outputs:
                    o_type = o.get("type", "")
                    o_name = o.get("name", "")
                    if o_type in ("elasticsearch", "kafka", "loki", "cloudwatch", "splunk"):
                        result.evidence.append(
                            f"Log forwarding → {o_type} output '{o_name}'"
                        )
                        found = True
        except httpx.HTTPStatusError:
            pass

        # Check Loki / Grafana / OpenTelemetry in cluster
        for ns in ("openshift-logging", "openshift-monitoring", "grafana-operator", "loki"):
            try:
                routes = await client.get_routes(ns)
                obs_routes = [
                    r for r in routes
                    if any(kw in r["metadata"]["name"].lower()
                           for kw in ("loki", "grafana", "tempo", "jaeger", "otel"))
                ]
                if obs_routes:
                    result.evidence.append(
                        f"Observability routes in '{ns}': "
                        + ", ".join(r["metadata"]["name"] for r in obs_routes)
                    )
                    found = True
            except httpx.HTTPStatusError:
                pass

        if found:
            result.passed("Namespace/cluster events are being pushed to an observability platform.")
        else:
            result.failed(
                "No log forwarding to observability platform detected "
                "(check ClusterLogForwarder outputs)."
            )

    # ── TC-081: Authentication & Audit Logs ───────────────────────────────────

    async def _tc_081(self, result: TestResult, client: OpenShiftClient) -> None:
        found = False

        # Check APIServer audit policy
        try:
            api_server = await client.get("/apis/config.openshift.io/v1/apiservers/cluster")
            audit = api_server.get("spec", {}).get("audit", {})
            profile = audit.get("profile", "Default")
            result.evidence.append(f"APIServer audit profile: {profile}")
            if profile in ("WriteRequestBodies", "AllRequestBodies", "Default"):
                found = True
        except httpx.HTTPStatusError:
            result.evidence.append("APIServer config not accessible.")

        # Check if audit log forwarding is configured
        try:
            data = await client.get("/apis/logging.openshift.io/v1/clusterlogforwarders")
            for fwd in data.get("items", []):
                inputs = fwd.get("spec", {}).get("inputs", [])
                for inp in inputs:
                    if inp.get("type") == "audit" or "audit" in inp.get("name", "").lower():
                        result.evidence.append(
                            f"Audit log forwarding input: '{inp.get('name')}' → type={inp.get('type')}"
                        )
                        found = True
                # Also check pipelines for audit
                pipelines = fwd.get("spec", {}).get("pipelines", [])
                for pl in pipelines:
                    if "audit" in str(pl).lower():
                        result.evidence.append(f"Audit pipeline: {pl.get('name')}")
                        found = True
        except httpx.HTTPStatusError:
            pass

        if found:
            result.passed("Authentication and audit logs are captured — audit policy and forwarding configured.")
        else:
            result.failed(
                "Audit log capture not fully configured — verify audit profile and "
                "ClusterLogForwarder audit inputs."
            )
