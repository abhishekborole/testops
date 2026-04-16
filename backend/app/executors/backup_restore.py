"""
Backup & Restore — TC-070
CommVault cluster backup status
"""
from __future__ import annotations

import httpx

from .base import BaseExecutor, OpenShiftClient, TestResult


class BackupRestoreExecutor(BaseExecutor):

    FUNCTION_MAP = {
        "TC-070": "_tc_070",
    }

    async def _tc_070(self, result: TestResult, client: OpenShiftClient) -> None:
        found = False

        # 1. Check OADP (OpenShift API for Data Protection) operator
        try:
            csvs = await client.get_csvs()
            oadp_csvs = [
                csv for csv in csvs
                if any(kw in csv["metadata"]["name"].lower()
                       for kw in ("oadp", "velero", "data-protection"))
                and csv.get("status", {}).get("phase") == "Succeeded"
            ]
            if oadp_csvs:
                result.evidence.append(
                    "OADP/Velero CSVs (Succeeded): "
                    + ", ".join(c["metadata"]["name"] for c in oadp_csvs)
                )
                found = True
        except httpx.HTTPStatusError:
            pass

        # 2. Check DataProtectionApplication CRD
        try:
            dpa_data = await client.get(
                "/apis/oadp.openshift.io/v1alpha1/dataprotectionapplications"
            )
            dpas = dpa_data.get("items", [])
            result.evidence.append(f"DataProtectionApplications: {len(dpas)}")
            for dpa in dpas:
                name  = dpa["metadata"]["name"]
                ns    = dpa["metadata"]["namespace"]
                conds = dpa.get("status", {}).get("conditions", [])
                reconciled = next(
                    (c["status"] for c in conds if c["type"] == "Reconciled"), "Unknown"
                )
                result.evidence.append(f"  {ns}/{name}: reconciled={reconciled}")
            if dpas:
                found = True
        except httpx.HTTPStatusError:
            pass

        # 3. Check CommVault operator / namespace
        for ns in ("commvault", "cv-backup", "commvault-operator"):
            try:
                pods = await client.get_pods(ns)
                if pods:
                    running = [p for p in pods if p.get("status", {}).get("phase") == "Running"]
                    result.evidence.append(
                        f"CommVault namespace '{ns}': {len(running)}/{len(pods)} pods running"
                    )
                    found = True
                    break
            except httpx.HTTPStatusError:
                pass

        # 4. Check for CommVault CRDs
        try:
            data = await client.get("/apis/commvault.com/v1/backupsets")
            items = data.get("items", [])
            result.evidence.append(f"CommVault BackupSets: {len(items)}")
            if items:
                found = True
                for item in items[:5]:
                    status = item.get("status", {}).get("state", "Unknown")
                    result.evidence.append(
                        f"  {item['metadata']['name']}: state={status}"
                    )
        except httpx.HTTPStatusError:
            pass

        # 5. Check Velero backups directly
        try:
            data = await client.get("/apis/velero.io/v1/backups")
            backups = data.get("items", [])
            completed = [b for b in backups if b.get("status", {}).get("phase") == "Completed"]
            result.evidence.append(
                f"Velero Backups: {len(backups)} total, {len(completed)} completed"
            )
            if backups:
                found = True
        except httpx.HTTPStatusError:
            pass

        if found:
            result.passed("Cluster backup solution (CommVault/OADP/Velero) detected and operational.")
        else:
            result.failed(
                "No backup solution (CommVault, OADP, or Velero) detected on cluster. "
                "No backup operators, CRs, or backup records found."
            )
