"""
Compliance & Policy — TC-071 to TC-073
"""
from __future__ import annotations

import httpx

from .base import BaseExecutor, OpenShiftClient, TestResult

COMPLIANCE_GROUP = "compliance.openshift.io/v1alpha1"


class ComplianceExecutor(BaseExecutor):

    FUNCTION_MAP = {
        "TC-071": "_tc_071",
        "TC-072": "_tc_072",
        "TC-073": "_tc_073",
    }

    # ── TC-071: Compliance Operator Health ────────────────────────────────────

    async def _tc_071(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check Compliance Operator CSV
        try:
            csvs = await client.get_csvs()
            comp_csvs = [
                csv for csv in csvs
                if "compliance" in csv["metadata"]["name"].lower()
                and csv.get("status", {}).get("phase") == "Succeeded"
            ]
            result.evidence.append(
                f"Compliance Operator CSVs: "
                + (", ".join(c["metadata"]["name"] for c in comp_csvs) or "none")
            )
        except httpx.HTTPStatusError:
            comp_csvs = []
            result.evidence.append("CSV API not accessible.")

        # Check ComplianceSuite CRD
        try:
            data = await client.get(f"/apis/{COMPLIANCE_GROUP}/compliancesuites")
            suites = data.get("items", [])
            result.evidence.append(f"ComplianceSuites: {len(suites)}")

            for suite in suites:
                name   = suite["metadata"]["name"]
                ns     = suite["metadata"]["namespace"]
                phase  = suite.get("status", {}).get("phase", "Unknown")
                result.evidence.append(f"  {ns}/{name}: phase={phase}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 403):
                result.evidence.append("ComplianceSuite CRD not available.")
                suites = []
            else:
                raise

        # Check Compliance Operator pods
        try:
            pods = await client.get_pods("openshift-compliance")
            running = [p for p in pods if p.get("status", {}).get("phase") == "Running"]
            result.evidence.append(
                f"Compliance Operator pods: {len(running)}/{len(pods)} running"
            )
        except httpx.HTTPStatusError:
            running = []
            pods    = []

        if comp_csvs and running:
            result.passed(
                f"Compliance Operator healthy: {len(comp_csvs)} CSV(s) Succeeded, "
                f"{len(running)} pods running."
            )
        elif comp_csvs:
            result.failed("Compliance Operator CSV found but no pods running.")
        else:
            result.failed("Compliance Operator not installed or not healthy.")

    # ── TC-072: Verify Compliance Results and Violations ─────────────────────

    async def _tc_072(self, result: TestResult, client: OpenShiftClient) -> None:
        try:
            data = await client.get(f"/apis/{COMPLIANCE_GROUP}/compliancecheckresults")
            checks = data.get("items", [])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 403):
                result.blocked("ComplianceCheckResult CRD not available.")
                return
            raise

        if not checks:
            result.failed("No ComplianceCheckResults found — compliance scans may not have run.")
            return

        by_status: dict[str, int] = {}
        for check in checks:
            s = check.get("status", {}).get("result", "Unknown")
            by_status[s] = by_status.get(s, 0) + 1

        result.evidence.append(
            f"ComplianceCheckResults ({len(checks)} total):\n"
            + "\n".join(f"  {status}: {count}" for status, count in sorted(by_status.items()))
        )

        passed_count = by_status.get("PASS", 0)
        fail_count   = by_status.get("FAIL", 0)
        error_count  = by_status.get("ERROR", 0)

        if fail_count == 0 and error_count == 0:
            result.passed(f"All {passed_count} compliance checks PASS. No violations.")
        elif fail_count > 0:
            # List top violations
            fails = [
                c["metadata"]["name"]
                for c in checks
                if c.get("status", {}).get("result") == "FAIL"
            ]
            result.evidence.append(f"Sample FAIL checks: {fails[:10]}")
            result.failed(
                f"{fail_count} compliance violation(s) found out of {len(checks)} checks."
            )
        else:
            result.failed(f"{error_count} check error(s). Investigate compliance scan.")

    # ── TC-073: Cluster Version, Patch Level, CSI, MTV, CNV versions ─────────

    async def _tc_073(self, result: TestResult, client: OpenShiftClient) -> None:
        lines = []

        # OCP version
        try:
            cv = await client.get("/apis/config.openshift.io/v1/clusterversions/version")
            desired = cv.get("status", {}).get("desired", {})
            version = desired.get("version", "unknown")
            channel = cv.get("spec", {}).get("channel", "unknown")
            lines.append(f"OCP Version: {version} (channel: {channel})")

            # History
            history = cv.get("status", {}).get("history", [])
            if history:
                last = history[0]
                lines.append(
                    f"Last update: {last.get('version')} — state: {last.get('state')}"
                )
        except httpx.HTTPStatusError:
            lines.append("ClusterVersion: API not accessible.")

        # CSI drivers
        try:
            drivers = await client.get("/apis/storage.k8s.io/v1/csidrivers")
            driver_names = [d["metadata"]["name"] for d in drivers.get("items", [])]
            lines.append(f"CSI Drivers ({len(driver_names)}): {', '.join(driver_names)}")
        except httpx.HTTPStatusError:
            lines.append("CSI Drivers: not accessible.")

        # MTV (Migration Toolkit for Virtualization)
        try:
            csvs = await client.get_csvs()
            mtv = next(
                (c for c in csvs if "mtv" in c["metadata"]["name"].lower()
                 or "migration" in c.get("spec", {}).get("displayName", "").lower()),
                None,
            )
            if mtv:
                lines.append(
                    f"MTV version: {mtv.get('spec', {}).get('version', 'unknown')} "
                    f"({mtv.get('status', {}).get('phase', 'unknown')})"
                )
            else:
                lines.append("MTV: not installed.")
        except httpx.HTTPStatusError:
            pass

        # CNV / OpenShift Virtualization
        try:
            data = await client.get(
                "/apis/hco.kubevirt.io/v1beta1/hyperconvergeds"
            )
            hcos = data.get("items", [])
            for hco in hcos:
                ver = hco.get("status", {}).get("versions", [])
                for v in ver:
                    lines.append(f"CNV component {v.get('name')}: {v.get('version')}")
                if not ver:
                    lines.append(f"CNV HyperConverged: {hco['metadata']['name']} found")
        except httpx.HTTPStatusError:
            lines.append("CNV/HyperConverged: API not accessible.")

        result.evidence.append("Version summary:\n" + "\n".join(lines))

        if any("OCP Version" in l for l in lines):
            result.passed("Cluster version and component details collected.")
        else:
            result.failed("Could not retrieve cluster version information.")
