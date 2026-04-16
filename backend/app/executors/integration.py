"""
Integration — TC-061 to TC-069
AAP, BHOM, ServiceNow, EDA, EntraID, ODS, Unicorn
"""
from __future__ import annotations

import httpx

from .base import BaseExecutor, OpenShiftClient, TestResult


class IntegrationExecutor(BaseExecutor):

    FUNCTION_MAP = {
        "TC-061": "_tc_061",
        "TC-062": "_tc_062",
        "TC-063": "_tc_063",
        "TC-064": "_tc_064",
        "TC-065": "_tc_065",
        "TC-066": "_tc_066",
        "TC-067": "_tc_067",
        "TC-068": "_tc_068",
        "TC-069": "_tc_069",
    }

    async def _check_operator_csv(
        self, result: TestResult, client: OpenShiftClient,
        keywords: list[str], label: str,
    ) -> bool:
        """Return True if a Succeeded CSV matching any keyword is found."""
        try:
            csvs = await client.get_csvs()
        except httpx.HTTPStatusError:
            result.evidence.append(f"{label}: CSV API not accessible.")
            return False

        matched = [
            csv for csv in csvs
            if csv.get("status", {}).get("phase") == "Succeeded"
            and any(kw.lower() in csv.get("spec", {}).get("displayName", "").lower()
                    or kw.lower() in csv["metadata"]["name"].lower()
                    for kw in keywords)
        ]
        result.evidence.append(
            f"{label} CSVs (Succeeded): "
            + (", ".join(c["metadata"]["name"] for c in matched) or "none found")
        )
        return bool(matched)

    async def _check_cr_exists(
        self, result: TestResult, client: OpenShiftClient,
        api_path: str, label: str,
    ) -> tuple[bool, list[dict]]:
        try:
            data = await client.get(api_path)
            items = data.get("items", [])
            result.evidence.append(f"{label}: {len(items)} resource(s) found at {api_path}")
            return True, items
        except httpx.HTTPStatusError as exc:
            result.evidence.append(
                f"{label}: API {api_path} returned HTTP {exc.response.status_code}"
            )
            return False, []

    # ── TC-061: AAP (Ansible Automation Platform) ─────────────────────────────

    async def _tc_061(self, result: TestResult, client: OpenShiftClient) -> None:
        found_csv = await self._check_operator_csv(
            result, client, ["Ansible Automation Platform", "ansible-automation-platform"], "AAP"
        )

        # Check AAP CRs
        found_cr, items = await self._check_cr_exists(
            result, client,
            "/apis/aap.ansible.com/v1alpha1/ansibleautomationplatforms", "AAP CR"
        )

        if not found_cr:
            found_cr, items = await self._check_cr_exists(
                result, client,
                "/apis/automationcontroller.ansible.com/v1beta1/automationcontrollers",
                "AutomationController CR"
            )

        # Check AAP route
        try:
            for ns in ("aap", "ansible-automation-platform"):
                routes = await client.get_routes(ns)
                if routes:
                    result.evidence.append(
                        f"AAP routes in '{ns}': "
                        + ", ".join(r["metadata"]["name"] for r in routes)
                    )
                    break
        except httpx.HTTPStatusError:
            pass

        if found_csv or (found_cr and items):
            result.passed("AAP operator installed and running on cluster.")
        else:
            result.failed("AAP not detected — no CSV or CR found.")

    # ── TC-062: BHOM — Operator/Instance ─────────────────────────────────────

    async def _tc_062(self, result: TestResult, client: OpenShiftClient) -> None:
        found = await self._check_operator_csv(
            result, client,
            ["Business Automation", "BHOM", "bamoe", "ibm-automation"], "BHOM"
        )

        # Also check for IBM Automation Insights / BHOM namespace
        for ns in ("bhom", "ibm-automation", "cp4a"):
            try:
                pods = await client.get_pods(ns)
                running = [p for p in pods if p.get("status", {}).get("phase") == "Running"]
                if pods:
                    result.evidence.append(
                        f"Namespace '{ns}': {len(running)}/{len(pods)} pods running"
                    )
                    found = True
                    break
            except httpx.HTTPStatusError:
                pass

        if found:
            result.passed("BHOM (Business Automation) integration detected.")
        else:
            result.failed("BHOM not detected — no CSV, pods, or CRs found.")

    # ── TC-063: BHOM — Event Forwarding ──────────────────────────────────────

    async def _tc_063(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check event forwarding configuration (ClusterLogForwarder / AlertManager webhook)
        found_fwd = False

        try:
            data = await client.get(
                "/apis/logging.openshift.io/v1/clusterlogforwarders"
            )
            forwarders = data.get("items", [])
            for f in forwarders:
                outputs = f.get("spec", {}).get("outputs", [])
                bhom_outputs = [
                    o for o in outputs
                    if "bhom" in str(o).lower() or "ibm" in str(o).lower()
                ]
                if bhom_outputs:
                    found_fwd = True
                    result.evidence.append(f"BHOM log forwarding found: {bhom_outputs[:2]}")
        except httpx.HTTPStatusError:
            result.evidence.append("ClusterLogForwarder API not accessible.")

        # Check AlertManager receiver config
        try:
            am_cfg = await client.get(
                "/api/v1/namespaces/openshift-monitoring/secrets/alertmanager-main"
            )
            import base64
            cfg_b64 = am_cfg.get("data", {}).get("alertmanager.yaml", "")
            if cfg_b64:
                cfg_text = base64.b64decode(cfg_b64).decode("utf-8", errors="replace")
                if "bhom" in cfg_text.lower() or "ibm" in cfg_text.lower():
                    found_fwd = True
                    result.evidence.append("BHOM receiver found in AlertManager config.")
        except httpx.HTTPStatusError:
            pass

        if found_fwd:
            result.passed("BHOM event forwarding configuration found.")
        else:
            result.failed("No BHOM event forwarding configuration detected.")

    # ── TC-064: BHOM — Observability Dashboard ────────────────────────────────

    async def _tc_064(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check for Grafana / BHOM dashboard routes
        found = False
        for ns in ("bhom", "grafana", "ibm-automation", "openshift-monitoring"):
            try:
                routes = await client.get_routes(ns)
                bhom_routes = [r for r in routes
                               if any(kw in r["metadata"]["name"].lower()
                                      for kw in ("grafana", "bhom", "dashboard", "ibm"))]
                if bhom_routes:
                    result.evidence.append(
                        f"Dashboard routes in '{ns}': "
                        + ", ".join(
                            f"{r['metadata']['name']} → "
                            f"https://{r.get('spec',{}).get('host','')}"
                            for r in bhom_routes
                        )
                    )
                    found = True
                    break
            except httpx.HTTPStatusError:
                pass

        if found:
            result.passed("BHOM observability dashboard route found.")
        else:
            result.failed("No BHOM dashboard route detected.")

    # ── TC-065: ServiceNow Integration ───────────────────────────────────────

    async def _tc_065(self, result: TestResult, client: OpenShiftClient) -> None:
        found = False

        # Check for ServiceNow webhook in AlertManager
        try:
            secret = await client.get(
                "/api/v1/namespaces/openshift-monitoring/secrets/alertmanager-main"
            )
            import base64
            cfg_b64 = secret.get("data", {}).get("alertmanager.yaml", "")
            if cfg_b64:
                cfg = base64.b64decode(cfg_b64).decode("utf-8", errors="replace")
                if "servicenow" in cfg.lower() or "service-now" in cfg.lower():
                    found = True
                    result.evidence.append("ServiceNow receiver in AlertManager config found.")
        except httpx.HTTPStatusError:
            pass

        # Check for SNow operator/integration CRDs
        try:
            data = await client.get("/apis/servicenow.io/v1/snowconfigs")
            if data.get("items"):
                found = True
                result.evidence.append(f"ServiceNow configs: {len(data['items'])} found.")
        except httpx.HTTPStatusError:
            pass

        # Check ConfigMaps with ServiceNow config
        try:
            cms = await client.get("/api/v1/configmaps")
            snow_cms = [
                cm["metadata"]["name"]
                for cm in cms.get("items", [])
                if "servicenow" in cm["metadata"]["name"].lower()
                or "snow" in cm["metadata"]["name"].lower()
            ]
            if snow_cms:
                found = True
                result.evidence.append(f"ServiceNow ConfigMaps: {snow_cms[:5]}")
        except httpx.HTTPStatusError:
            pass

        if found:
            result.passed("ServiceNow integration configuration detected.")
        else:
            result.failed("No ServiceNow integration configuration found.")

    # ── TC-066: EDA (Event-Driven Ansible) ───────────────────────────────────

    async def _tc_066(self, result: TestResult, client: OpenShiftClient) -> None:
        found_csv = await self._check_operator_csv(
            result, client,
            ["Event-Driven Ansible", "eda", "ansible-eda"], "EDA"
        )

        found_cr, items = await self._check_cr_exists(
            result, client,
            "/apis/eda.ansible.com/v1alpha1/edaconfigs", "EDA Config CR"
        )

        if not found_cr:
            found_cr, items = await self._check_cr_exists(
                result, client,
                "/apis/aap.ansible.com/v1alpha1/edaservers", "EDAServer CR"
            )

        if found_csv or (found_cr and items):
            result.passed("EDA (Event-Driven Ansible) operator installed.")
        else:
            result.failed("EDA not detected — no CSV or CR found.")

    # ── TC-067: EntraID (Azure AD) Integration ────────────────────────────────

    async def _tc_067(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check OAuth identity providers
        try:
            oauth = await client.get("/apis/config.openshift.io/v1/oauths/cluster")
            providers = oauth.get("spec", {}).get("identityProviders", [])
            oidc_providers = [
                p for p in providers
                if p.get("type") == "OpenID"
                or "microsoft" in str(p).lower()
                or "azure" in str(p).lower()
                or "entraid" in str(p).lower()
            ]
            result.evidence.append(
                f"Identity providers: {[p.get('name') for p in providers]}\n"
                f"OIDC/EntraID providers: {[p.get('name') for p in oidc_providers]}"
            )

            if oidc_providers:
                result.passed(
                    f"{len(oidc_providers)} OpenID/EntraID identity provider(s) configured: "
                    f"{[p.get('name') for p in oidc_providers]}"
                )
            else:
                result.failed(
                    "No EntraID/Azure AD identity provider found in OAuth config. "
                    f"Configured providers: {[p.get('name') for p in providers]}"
                )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 404):
                result.blocked("Cannot access cluster OAuth config.")
            else:
                raise

    # ── TC-068: ODS (OpenShift Data Science) ─────────────────────────────────

    async def _tc_068(self, result: TestResult, client: OpenShiftClient) -> None:
        found = False

        # Check ODS operator CSV
        found_csv = await self._check_operator_csv(
            result, client,
            ["OpenShift Data Science", "RHODS", "rhods", "Open Data Hub"], "ODS"
        )

        # Check DataScienceCluster CRD
        found_cr, items = await self._check_cr_exists(
            result, client,
            "/apis/datasciencecluster.opendatahub.io/v1/datascienceclusters",
            "DataScienceCluster"
        )

        if not found_cr:
            found_cr, items = await self._check_cr_exists(
                result, client,
                "/apis/opendatahub.io/v1alpha/odhdashboardconfigs",
                "ODS Dashboard Config"
            )

        # Check RHODS namespace
        for ns in ("redhat-ods-applications", "opendatahub"):
            try:
                pods = await client.get_pods(ns)
                if pods:
                    running = [p for p in pods if p.get("status", {}).get("phase") == "Running"]
                    result.evidence.append(
                        f"ODS namespace '{ns}': {len(running)}/{len(pods)} running"
                    )
                    found = True
                    break
            except httpx.HTTPStatusError:
                pass

        if found_csv or found_cr or found:
            result.passed("ODS (OpenShift Data Science / RHODS) detected on cluster.")
        else:
            result.failed("ODS not detected — no CSV, CRs, or pods found.")

    # ── TC-069: Unicorn Integration ───────────────────────────────────────────

    async def _tc_069(self, result: TestResult, client: OpenShiftClient) -> None:
        # "Unicorn" is likely an internal/custom integration platform
        found = False

        # Check for unicorn-related deployments / configmaps / namespaces
        try:
            ns_data = await client.get_namespaces()
            unicorn_ns = [
                ns["metadata"]["name"]
                for ns in ns_data
                if "unicorn" in ns["metadata"]["name"].lower()
            ]
            result.evidence.append(
                f"Unicorn namespaces: {unicorn_ns if unicorn_ns else 'none'}"
            )
            if unicorn_ns:
                found = True
        except httpx.HTTPStatusError:
            pass

        # Check deployments
        try:
            deps = await client.get("/apis/apps/v1/deployments")
            unicorn_deps = [
                f"{d['metadata']['namespace']}/{d['metadata']['name']}"
                for d in deps.get("items", [])
                if "unicorn" in d["metadata"]["name"].lower()
            ]
            result.evidence.append(
                f"Unicorn deployments: {unicorn_deps[:5] if unicorn_deps else 'none'}"
            )
            if unicorn_deps:
                found = True
        except httpx.HTTPStatusError:
            pass

        if found:
            result.passed("Unicorn integration components found on cluster.")
        else:
            result.failed("No Unicorn-related resources detected on cluster.")
