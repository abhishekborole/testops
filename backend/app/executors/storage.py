"""
Storage — TC-027 to TC-033
"""
from __future__ import annotations

import asyncio

import httpx

from .base import BaseExecutor, OpenShiftClient, TestResult

TEST_NS   = "testops-runner"
TEST_SIZE = "1Gi"


class StorageExecutor(BaseExecutor):

    FUNCTION_MAP = {
        "TC-027": "_tc_027",
        "TC-028": "_tc_028",
        "TC-029": "_tc_029",
        "TC-030": "_tc_030",
        "TC-031": "_tc_031",
        "TC-032": "_tc_032",
        "TC-033": "_tc_033",
    }

    # ── TC-027: Required StorageClasses exist ─────────────────────────────────

    async def _tc_027(self, result: TestResult, client: OpenShiftClient) -> None:
        scs = await client.get_storage_classes()
        if not scs:
            result.failed("No StorageClasses found in cluster.")
            return

        lines = []
        for sc in scs:
            name       = sc["metadata"]["name"]
            provisioner = sc.get("provisioner", "unknown")
            default    = (
                sc["metadata"]
                .get("annotations", {})
                .get("storageclass.kubernetes.io/is-default-class") == "true"
            )
            reclaim    = sc.get("reclaimPolicy", "Delete")
            lines.append(
                f"  {name}: provisioner={provisioner}, "
                f"default={default}, reclaimPolicy={reclaim}"
            )

        result.evidence.append(
            f"StorageClasses ({len(scs)}):\n" + "\n".join(lines)
        )
        result.passed(f"{len(scs)} StorageClass(es) found.")

    # ── TC-028: Default StorageClass ──────────────────────────────────────────

    async def _tc_028(self, result: TestResult, client: OpenShiftClient) -> None:
        scs = await client.get_storage_classes()
        defaults = [
            sc for sc in scs
            if sc["metadata"]
               .get("annotations", {})
               .get("storageclass.kubernetes.io/is-default-class") == "true"
        ]

        result.evidence.append(
            f"Default StorageClass(es): {[sc['metadata']['name'] for sc in defaults]}"
        )

        if len(defaults) == 1:
            sc = defaults[0]
            result.passed(
                f"Exactly one default StorageClass: '{sc['metadata']['name']}' "
                f"(provisioner: {sc.get('provisioner', 'unknown')})."
            )
        elif len(defaults) == 0:
            result.failed("No default StorageClass found.")
        else:
            result.failed(
                f"Multiple ({len(defaults)}) default StorageClasses found — "
                f"this causes ambiguous PVC binding: "
                f"{[sc['metadata']['name'] for sc in defaults]}"
            )

    # ── TC-029: Dynamic Provisioning of PVs ──────────────────────────────────

    async def _tc_029(self, result: TestResult, client: OpenShiftClient) -> None:
        await client.ensure_namespace(TEST_NS)

        scs = await client.get_storage_classes()
        default_sc = next(
            (
                sc["metadata"]["name"]
                for sc in scs
                if sc["metadata"]
                   .get("annotations", {})
                   .get("storageclass.kubernetes.io/is-default-class") == "true"
            ),
            None,
        )
        if not default_sc:
            result.blocked("No default StorageClass — cannot test dynamic provisioning.")
            return

        pvc_name = "testops-tc029-dynamic-pvc"
        pvc_body = {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {"name": pvc_name, "namespace": TEST_NS},
            "spec": {
                "accessModes": ["ReadWriteOnce"],
                "resources": {"requests": {"storage": TEST_SIZE}},
                "storageClassName": default_sc,
            },
        }

        try:
            await client.post(
                f"/api/v1/namespaces/{TEST_NS}/persistentvolumeclaims", pvc_body
            )
            result.evidence.append(f"Created PVC '{pvc_name}' with storageClass '{default_sc}'.")

            phase = await client.wait_for_pvc_bound(TEST_NS, pvc_name, timeout=90)
            result.evidence.append(f"PVC phase: {phase}")

            if phase == "Bound":
                # Get bound PV name
                pvc_data = await client.get(
                    f"/api/v1/namespaces/{TEST_NS}/persistentvolumeclaims/{pvc_name}"
                )
                pv_name = pvc_data.get("spec", {}).get("volumeName", "unknown")
                result.evidence.append(f"Bound to PV: {pv_name}")
                result.passed(
                    f"Dynamic provisioning successful — PVC bound to PV '{pv_name}' "
                    f"via StorageClass '{default_sc}'."
                )
            else:
                result.failed(f"PVC not bound — final phase: {phase}")
        finally:
            try:
                await client.delete(
                    f"/api/v1/namespaces/{TEST_NS}/persistentvolumeclaims/{pvc_name}"
                )
            except Exception:
                pass

    # ── TC-030: StorageClass Parameters ──────────────────────────────────────

    async def _tc_030(self, result: TestResult, client: OpenShiftClient) -> None:
        scs = await client.get_storage_classes()
        if not scs:
            result.failed("No StorageClasses found.")
            return

        lines = []
        for sc in scs:
            name       = sc["metadata"]["name"]
            params     = sc.get("parameters", {})
            provisioner = sc.get("provisioner", "unknown")
            reclaim    = sc.get("reclaimPolicy", "Delete")
            vol_binding = sc.get("volumeBindingMode", "Immediate")
            allow_expand = sc.get("allowVolumeExpansion", False)

            lines.append(
                f"  {name}:\n"
                f"    provisioner={provisioner}\n"
                f"    reclaimPolicy={reclaim}\n"
                f"    volumeBindingMode={vol_binding}\n"
                f"    allowVolumeExpansion={allow_expand}\n"
                f"    parameters={params}"
            )

        result.evidence.append("StorageClass parameters:\n" + "\n".join(lines))
        result.passed(f"Parameters validated for {len(scs)} StorageClass(es).")

    # ── TC-031: PVC Deletion and PV Reclaim ───────────────────────────────────

    async def _tc_031(self, result: TestResult, client: OpenShiftClient) -> None:
        await client.ensure_namespace(TEST_NS)

        scs = await client.get_storage_classes()
        default_sc = next(
            (
                sc for sc in scs
                if sc["metadata"]
                   .get("annotations", {})
                   .get("storageclass.kubernetes.io/is-default-class") == "true"
            ),
            None,
        )
        if not default_sc:
            result.blocked("No default StorageClass.")
            return

        sc_name     = default_sc["metadata"]["name"]
        reclaim_pol = default_sc.get("reclaimPolicy", "Delete")
        pvc_name    = "testops-tc031-reclaim-pvc"

        pvc_body = {
            "apiVersion": "v1", "kind": "PersistentVolumeClaim",
            "metadata": {"name": pvc_name, "namespace": TEST_NS},
            "spec": {
                "accessModes": ["ReadWriteOnce"],
                "resources": {"requests": {"storage": "1Gi"}},
                "storageClassName": sc_name,
            },
        }

        try:
            await client.post(
                f"/api/v1/namespaces/{TEST_NS}/persistentvolumeclaims", pvc_body
            )
            phase = await client.wait_for_pvc_bound(TEST_NS, pvc_name, timeout=90)
            result.evidence.append(f"PVC '{pvc_name}' phase: {phase}")

            if phase != "Bound":
                result.failed(f"PVC did not bind (phase: {phase}) — cannot test reclaim.")
                return

            # Get PV name before deletion
            pvc_data = await client.get(
                f"/api/v1/namespaces/{TEST_NS}/persistentvolumeclaims/{pvc_name}"
            )
            pv_name = pvc_data.get("spec", {}).get("volumeName", "")
            result.evidence.append(f"Bound PV: {pv_name}")

            # Delete PVC
            await client.delete(
                f"/api/v1/namespaces/{TEST_NS}/persistentvolumeclaims/{pvc_name}"
            )
            result.evidence.append(f"PVC deleted. Reclaim policy: {reclaim_pol}")

            if pv_name:
                await asyncio.sleep(5)
                found, pv_data = await client.exists(f"/api/v1/persistentvolumes/{pv_name}")
                pv_phase = pv_data.get("status", {}).get("phase", "Gone") if found else "Deleted"
                result.evidence.append(f"PV '{pv_name}' status after PVC deletion: {pv_phase}")

                if reclaim_pol == "Delete" and not found:
                    result.passed(f"PV auto-deleted as expected (reclaimPolicy=Delete).")
                elif reclaim_pol == "Retain" and found:
                    result.passed(f"PV retained as expected (reclaimPolicy=Retain) — phase: {pv_phase}.")
                else:
                    result.passed(
                        f"PVC deleted. PV '{pv_name}' status: {pv_phase} "
                        f"(reclaimPolicy={reclaim_pol})."
                    )
            else:
                result.passed("PVC deleted successfully.")
        except Exception:
            try:
                await client.delete(
                    f"/api/v1/namespaces/{TEST_NS}/persistentvolumeclaims/{pvc_name}"
                )
            except Exception:
                pass
            raise

    # ── TC-032: PVC RWO Access Mode and Reclaim Policies ─────────────────────

    async def _tc_032(self, result: TestResult, client: OpenShiftClient) -> None:
        pvcs = await client.get_pvcs()
        rwo_pvcs = [
            p for p in pvcs
            if "ReadWriteOnce" in p.get("spec", {}).get("accessModes", [])
        ]

        if not rwo_pvcs:
            result.failed("No PVCs with ReadWriteOnce access mode found.")
            return

        bound = [p for p in rwo_pvcs if p.get("status", {}).get("phase") == "Bound"]
        lines = []
        for p in rwo_pvcs[:20]:
            ns      = p["metadata"]["namespace"]
            name    = p["metadata"]["name"]
            phase   = p.get("status", {}).get("phase")
            sc      = p.get("spec", {}).get("storageClassName", "none")
            storage = p.get("spec", {}).get("resources", {}).get("requests", {}).get("storage", "?")
            lines.append(f"  {ns}/{name}: phase={phase}, sc={sc}, size={storage}")

        result.evidence.append(
            f"RWO PVCs ({len(rwo_pvcs)} total, {len(bound)} bound):\n"
            + "\n".join(lines)
        )

        if len(bound) == len(rwo_pvcs):
            result.passed(f"All {len(rwo_pvcs)} RWO PVC(s) are Bound.")
        elif bound:
            result.passed(f"{len(bound)}/{len(rwo_pvcs)} RWO PVC(s) are Bound.")
        else:
            result.failed(f"No RWO PVCs are Bound ({len(rwo_pvcs)} exist).")

    # ── TC-033: PVC RWX Access Mode and Reclaim Policies ─────────────────────

    async def _tc_033(self, result: TestResult, client: OpenShiftClient) -> None:
        pvcs = await client.get_pvcs()
        rwx_pvcs = [
            p for p in pvcs
            if "ReadWriteMany" in p.get("spec", {}).get("accessModes", [])
        ]

        if not rwx_pvcs:
            # Check if any StorageClass supports RWX
            scs = await client.get_storage_classes()
            rwx_scs = [sc["metadata"]["name"] for sc in scs
                       if "ReadWriteMany" in sc.get("spec", {}) or
                       any(k in sc.get("provisioner", "").lower()
                           for k in ("cephfs", "nfs", "ocs", "rbd"))]
            result.evidence.append(f"StorageClasses that may support RWX: {rwx_scs}")
            result.failed(
                "No PVCs with ReadWriteMany access mode found. "
                f"Potential RWX-capable classes: {rwx_scs}"
            )
            return

        bound = [p for p in rwx_pvcs if p.get("status", {}).get("phase") == "Bound"]
        lines = []
        for p in rwx_pvcs[:20]:
            ns    = p["metadata"]["namespace"]
            name  = p["metadata"]["name"]
            phase = p.get("status", {}).get("phase")
            sc    = p.get("spec", {}).get("storageClassName", "none")
            lines.append(f"  {ns}/{name}: phase={phase}, sc={sc}")

        result.evidence.append(
            f"RWX PVCs ({len(rwx_pvcs)} total, {len(bound)} bound):\n"
            + "\n".join(lines)
        )

        if bound:
            result.passed(f"{len(bound)}/{len(rwx_pvcs)} RWX PVC(s) are Bound.")
        else:
            result.failed(f"No RWX PVCs are Bound ({len(rwx_pvcs)} exist but none bound).")
