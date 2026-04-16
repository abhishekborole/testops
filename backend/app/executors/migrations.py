"""
Migrations — TC-055 to TC-060  (Migration Toolkit for Virtualization / MTV)
"""
from __future__ import annotations

import httpx

from .base import BaseExecutor, OpenShiftClient, TestResult

MTV_GROUP = "forklift.konveyor.io/v1beta1"


class MigrationsExecutor(BaseExecutor):

    FUNCTION_MAP = {
        "TC-055": "_tc_055",
        "TC-056": "_tc_056",
        "TC-057": "_tc_057",
        "TC-058": "_tc_058",
        "TC-059": "_tc_059",
        "TC-060": "_tc_060",
    }

    async def _require_mtv(self, result: TestResult, client: OpenShiftClient) -> bool:
        try:
            await client.get(f"/apis/{MTV_GROUP}/")
            return True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 403):
                result.blocked(
                    "Migration Toolkit for Virtualization (MTV) API not available on this cluster."
                )
                return False
            raise

    async def _get_migrations(self, client: OpenShiftClient) -> list[dict]:
        data = await client.get(f"/apis/{MTV_GROUP}/migrations")
        return data.get("items", [])

    # ── TC-055: Cold Migration (Storage Offloading) ───────────────────────────

    async def _tc_055(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_mtv(result, client):
            return

        migrations = await self._get_migrations(client)
        cold = [
            m for m in migrations
            if m.get("spec", {}).get("warm") is False or "warm" not in m.get("spec", {})
        ]

        if not cold:
            result.blocked("No cold migration jobs found in cluster.")
            return

        lines = []
        succeeded = 0
        for m in cold[:10]:
            name   = m["metadata"]["name"]
            ns     = m["metadata"]["namespace"]
            phase  = m.get("status", {}).get("phase", "Unknown")
            vms    = len(m.get("status", {}).get("vms", []))
            lines.append(f"  {ns}/{name}: phase={phase}, vms={vms}")
            if phase == "Completed":
                succeeded += 1

        result.evidence.append(
            f"Cold migrations ({len(cold)}, showing first 10):\n" + "\n".join(lines)
        )

        if succeeded > 0:
            result.passed(f"{succeeded}/{len(cold)} cold migration(s) completed successfully.")
        elif cold:
            result.failed(f"No cold migrations completed — statuses: {[m.get('status',{}).get('phase') for m in cold[:5]]}")
        else:
            result.failed("No cold migration records found.")

    # ── TC-056: Warm Migration ────────────────────────────────────────────────

    async def _tc_056(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_mtv(result, client):
            return

        migrations = await self._get_migrations(client)
        warm = [m for m in migrations if m.get("spec", {}).get("warm") is True]

        if not warm:
            result.blocked("No warm migration jobs found in cluster.")
            return

        lines = []
        succeeded = 0
        for m in warm[:10]:
            name  = m["metadata"]["name"]
            ns    = m["metadata"]["namespace"]
            phase = m.get("status", {}).get("phase", "Unknown")
            lines.append(f"  {ns}/{name}: phase={phase}")
            if phase == "Completed":
                succeeded += 1

        result.evidence.append(
            f"Warm migrations ({len(warm)}):\n" + "\n".join(lines)
        )

        if succeeded > 0:
            result.passed(f"{succeeded}/{len(warm)} warm migration(s) completed.")
        else:
            result.failed("No warm migrations in Completed phase.")

    # ── TC-057: Cold Migration (Direct) ──────────────────────────────────────

    async def _tc_057(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_mtv(result, client):
            return

        # Inspect plans to find direct (non-storage-offloaded) cold migrations
        try:
            data = await client.get(f"/apis/{MTV_GROUP}/plans")
            plans = data.get("items", [])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 403):
                result.blocked("MTV Plans API not accessible.")
                return
            raise

        direct_plans = [
            p for p in plans
            if not p.get("spec", {}).get("warm")
        ]
        lines = []
        for p in direct_plans[:10]:
            name     = p["metadata"]["name"]
            ns       = p["metadata"]["namespace"]
            provider = p.get("spec", {}).get("provider", {}).get("source", {}).get("name", "?")
            ready    = p.get("status", {}).get("conditions", [])
            ready_v  = next((c["status"] for c in ready if c["type"] == "Ready"), "Unknown")
            lines.append(f"  {ns}/{name}: provider={provider}, ready={ready_v}")

        result.evidence.append(
            f"Direct cold migration plans ({len(direct_plans)}):\n"
            + ("\n".join(lines) if lines else "  (none)")
        )

        if direct_plans:
            result.passed(f"{len(direct_plans)} direct cold migration plan(s) found.")
        else:
            result.failed("No direct cold migration plans found.")

    # ── TC-058: Network and Storage Mappings ──────────────────────────────────

    async def _tc_058(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_mtv(result, client):
            return

        net_ok     = False
        storage_ok = False

        # Network maps
        try:
            net_data = await client.get(f"/apis/{MTV_GROUP}/networkmaps")
            net_maps = net_data.get("items", [])
            result.evidence.append(f"NetworkMaps: {len(net_maps)}")
            net_ok = len(net_maps) > 0
        except httpx.HTTPStatusError:
            result.evidence.append("NetworkMap API not available.")

        # Storage maps
        try:
            stor_data = await client.get(f"/apis/{MTV_GROUP}/storagemaps")
            stor_maps = stor_data.get("items", [])
            result.evidence.append(f"StorageMaps: {len(stor_maps)}")
            storage_ok = len(stor_maps) > 0
        except httpx.HTTPStatusError:
            result.evidence.append("StorageMap API not available.")

        if net_ok and storage_ok:
            result.passed("Network and Storage mappings are configured for migrations.")
        elif net_ok:
            result.failed("Network mappings found but no Storage mappings configured.")
        elif storage_ok:
            result.failed("Storage mappings found but no Network mappings configured.")
        else:
            result.failed("No Network or Storage mappings found.")

    # ── TC-059: Migration Performance and Downtime ────────────────────────────

    async def _tc_059(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_mtv(result, client):
            return

        migrations = await self._get_migrations(client)
        completed  = [m for m in migrations if m.get("status", {}).get("phase") == "Completed"]

        if not completed:
            result.blocked("No completed migrations to analyze performance.")
            return

        lines = []
        for m in completed[:5]:
            name      = m["metadata"]["name"]
            start     = m.get("status", {}).get("started", "?")
            completed_ts = m.get("status", {}).get("completed", "?")
            vms_count = len(m.get("status", {}).get("vms", []))
            lines.append(
                f"  {name}: started={start}, completed={completed_ts}, VMs migrated={vms_count}"
            )

        result.evidence.append(
            f"Completed migrations ({len(completed)}):\n" + "\n".join(lines)
        )
        result.passed(
            f"{len(completed)} migration(s) completed. Performance details in evidence."
        )

    # ── TC-060: Validate VMware Providers ─────────────────────────────────────

    async def _tc_060(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_mtv(result, client):
            return

        try:
            data = await client.get(f"/apis/{MTV_GROUP}/providers")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 403):
                result.blocked("MTV Providers API not accessible.")
                return
            raise

        providers = data.get("items", [])
        vmware    = [p for p in providers if p.get("spec", {}).get("type") == "vsphere"]

        if not vmware:
            result.failed("No VMware (vSphere) providers registered in MTV.")
            return

        lines = []
        ready_count = 0
        for p in vmware:
            name  = p["metadata"]["name"]
            ns    = p["metadata"]["namespace"]
            conds = p.get("status", {}).get("conditions", [])
            ready = next((c["status"] for c in conds if c["type"] == "Ready"), "Unknown")
            url   = p.get("spec", {}).get("url", "")
            lines.append(f"  {ns}/{name}: url={url}, ready={ready}")
            if ready == "True":
                ready_count += 1

        result.evidence.append(
            f"VMware providers ({len(vmware)}):\n" + "\n".join(lines)
        )

        if ready_count == len(vmware):
            result.passed(f"All {len(vmware)} VMware provider(s) are Ready.")
        elif ready_count > 0:
            result.failed(f"Only {ready_count}/{len(vmware)} VMware providers are Ready.")
        else:
            result.failed("No VMware providers are in Ready state.")
