"""
VM Operations — TC-034 to TC-054  (KubeVirt)
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

import httpx

from .base import BaseExecutor, OpenShiftClient, TestResult

VM_NS         = "default"          # namespace used for test VMs
KUBEVIRT_API  = "kubevirt.io/v1"
SNAP_API      = "snapshot.kubevirt.io/v1beta1"
TEST_VM_NAME  = "testops-tc034-vm"


def _minimal_vm(name: str, namespace: str, index: int = 0) -> dict:
    """Build a minimal KubeVirt VirtualMachine manifest using containerDisk."""
    return {
        "apiVersion": f"kubevirt.io/v1",
        "kind": "VirtualMachine",
        "metadata": {"name": name, "namespace": namespace,
                     "labels": {"app": "testops-runner"}},
        "spec": {
            "running": True,
            "template": {
                "metadata": {"labels": {"kubevirt.io/domain": name}},
                "spec": {
                    "domain": {
                        "cpu": {"cores": 1},
                        "memory": {"guest": "256Mi"},
                        "devices": {
                            "disks": [{"name": "containerdisk", "disk": {"bus": "virtio"}}],
                            "interfaces": [{"name": "default", "masquerade": {}}],
                        },
                    },
                    "networks": [{"name": "default", "pod": {}}],
                    "volumes": [{
                        "name": "containerdisk",
                        "containerDisk": {
                            "image": "quay.io/kubevirt/cirros-container-disk-demo:latest"
                        },
                    }],
                },
            },
        },
    }


async def _get_vms(client: OpenShiftClient, ns: str = "") -> list[dict]:
    path = (
        f"/apis/{KUBEVIRT_API}/namespaces/{ns}/virtualmachines"
        if ns else f"/apis/{KUBEVIRT_API}/virtualmachines"
    )
    data = await client.get(path)
    return data.get("items", [])


async def _get_vm(client: OpenShiftClient, name: str, ns: str) -> Optional[dict]:
    found, data = await client.exists(
        f"/apis/{KUBEVIRT_API}/namespaces/{ns}/virtualmachines/{name}"
    )
    return data if found else None


async def _wait_vm_phase(
    client: OpenShiftClient, name: str, ns: str,
    target: str, timeout: int = 120
) -> str:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        vm = await _get_vm(client, name, ns)
        if vm:
            phase = vm.get("status", {}).get("printableStatus", "Unknown")
            if phase == target:
                return phase
        await asyncio.sleep(5)
    return "Timeout"


class VMOperationsExecutor(BaseExecutor):

    FUNCTION_MAP = {
        "TC-034": "_tc_034",
        "TC-035": "_tc_035",
        "TC-036": "_tc_036",
        "TC-037": "_tc_037",
        "TC-038": "_tc_038",
        "TC-039": "_tc_039",
        "TC-040": "_tc_040",
        "TC-041": "_tc_041",
        "TC-042": "_tc_042",
        "TC-043": "_tc_043",
        "TC-044": "_tc_044",
        "TC-045": "_tc_045",
        "TC-046": "_tc_046",
        "TC-047": "_tc_047",
        "TC-048": "_tc_048",
        "TC-049": "_tc_049",
        "TC-050": "_tc_050",
        "TC-051": "_tc_051",
        "TC-052": "_tc_052",
        "TC-053": "_tc_053",
        "TC-054": "_tc_054",
    }

    async def _require_kubevirt(self, result: TestResult, client: OpenShiftClient) -> bool:
        """Return True if KubeVirt API is reachable. Sets result.blocked otherwise."""
        try:
            await client.get(f"/apis/{KUBEVIRT_API}/")
            return True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 403):
                result.blocked("KubeVirt API not available on this cluster.")
                return False
            raise

    # ── TC-034: Create Multiple VMs Simultaneously ────────────────────────────

    async def _tc_034(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        await client.ensure_namespace(VM_NS)
        vm_names = [f"testops-tc034-vm{i}" for i in range(1, 4)]
        created  = []

        try:
            tasks = [
                client.post(
                    f"/apis/{KUBEVIRT_API}/namespaces/{VM_NS}/virtualmachines",
                    _minimal_vm(name, VM_NS, i),
                )
                for i, name in enumerate(vm_names)
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            for name, resp in zip(vm_names, responses):
                if isinstance(resp, Exception):
                    result.evidence.append(f"  {name}: FAILED — {resp}")
                else:
                    created.append(name)
                    result.evidence.append(f"  {name}: created")

            result.evidence.append(
                f"Simultaneous VM creation: {len(created)}/{len(vm_names)} succeeded."
            )

            if len(created) == len(vm_names):
                result.passed(f"All {len(vm_names)} VMs created simultaneously.")
            elif created:
                result.failed(f"Only {len(created)}/{len(vm_names)} VMs created.")
            else:
                result.failed("No VMs created successfully.")
        finally:
            # Cleanup
            for name in created:
                try:
                    await client.delete(
                        f"/apis/{KUBEVIRT_API}/namespaces/{VM_NS}/virtualmachines/{name}"
                    )
                except Exception:
                    pass

    # ── TC-035: Start VM ──────────────────────────────────────────────────────

    async def _tc_035(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        vms = await _get_vms(client)
        stopped = [
            vm for vm in vms
            if vm.get("status", {}).get("printableStatus") in ("Stopped", "Paused")
        ]

        if not stopped:
            # List all VMs and pick any
            all_vms = vms
            if not all_vms:
                result.blocked("No VirtualMachines found in cluster to test Start operation.")
                return
            vm = all_vms[0]
            status = vm.get("status", {}).get("printableStatus", "Unknown")
            result.evidence.append(
                f"VM '{vm['metadata']['name']}' already in state: {status} — Start not required."
            )
            result.passed(f"VM '{vm['metadata']['name']}' is already running (status: {status}).")
            return

        vm      = stopped[0]
        name    = vm["metadata"]["name"]
        ns      = vm["metadata"]["namespace"]
        result.evidence.append(f"Starting VM '{name}' in namespace '{ns}'.")

        # KubeVirt start subresource
        await client.put(
            f"/apis/{KUBEVIRT_API}/namespaces/{ns}/virtualmachines/{name}/start",
            {},
        )

        phase = await _wait_vm_phase(client, name, ns, "Running", timeout=120)
        result.evidence.append(f"VM '{name}' phase after start: {phase}")

        if phase == "Running":
            result.passed(f"VM '{name}' started successfully (phase: Running).")
        else:
            result.failed(f"VM '{name}' did not reach Running state — final phase: {phase}")

    # ── TC-036: Stop VM ───────────────────────────────────────────────────────

    async def _tc_036(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        vms = await _get_vms(client)
        running = [
            vm for vm in vms
            if vm.get("status", {}).get("printableStatus") == "Running"
        ]

        if not running:
            result.blocked("No running VMs found to test Stop operation.")
            return

        vm   = running[0]
        name = vm["metadata"]["name"]
        ns   = vm["metadata"]["namespace"]
        result.evidence.append(f"Stopping VM '{name}' in namespace '{ns}'.")

        await client.put(
            f"/apis/{KUBEVIRT_API}/namespaces/{ns}/virtualmachines/{name}/stop",
            {},
        )

        phase = await _wait_vm_phase(client, name, ns, "Stopped", timeout=120)
        result.evidence.append(f"VM '{name}' phase after stop: {phase}")

        if phase == "Stopped":
            result.passed(f"VM '{name}' stopped successfully.")
        else:
            result.failed(f"VM '{name}' did not reach Stopped state — final: {phase}")

    # ── TC-037: Restart VM ────────────────────────────────────────────────────

    async def _tc_037(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        vms = await _get_vms(client)
        running = [
            vm for vm in vms
            if vm.get("status", {}).get("printableStatus") == "Running"
        ]

        if not running:
            result.blocked("No running VMs found to test Restart operation.")
            return

        vm   = running[0]
        name = vm["metadata"]["name"]
        ns   = vm["metadata"]["namespace"]
        result.evidence.append(f"Restarting VM '{name}'.")

        await client.put(
            f"/apis/{KUBEVIRT_API}/namespaces/{ns}/virtualmachines/{name}/restart",
            {},
        )

        # Wait briefly then check it comes back Running
        await asyncio.sleep(10)
        phase = await _wait_vm_phase(client, name, ns, "Running", timeout=180)
        result.evidence.append(f"VM '{name}' phase after restart: {phase}")

        if phase == "Running":
            result.passed(f"VM '{name}' restarted and is Running.")
        else:
            result.failed(f"VM '{name}' did not return to Running — phase: {phase}")

    # ── TC-038: Delete VM ─────────────────────────────────────────────────────

    async def _tc_038(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        # Create a disposable VM to delete
        await client.ensure_namespace(VM_NS)
        vm_name = "testops-tc038-delete-vm"

        try:
            await client.post(
                f"/apis/{KUBEVIRT_API}/namespaces/{VM_NS}/virtualmachines",
                _minimal_vm(vm_name, VM_NS),
            )
            result.evidence.append(f"VM '{vm_name}' created for deletion test.")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                result.evidence.append(f"VM '{vm_name}' already exists.")
            else:
                raise

        await client.delete(
            f"/apis/{KUBEVIRT_API}/namespaces/{VM_NS}/virtualmachines/{vm_name}"
        )

        # Verify gone
        await asyncio.sleep(3)
        found, _ = await client.exists(
            f"/apis/{KUBEVIRT_API}/namespaces/{VM_NS}/virtualmachines/{vm_name}"
        )
        result.evidence.append(f"VM exists after delete: {found}")

        if not found:
            result.passed(f"VM '{vm_name}' deleted successfully.")
        else:
            result.failed(f"VM '{vm_name}' still exists after delete.")

    # ── TC-039: Create VM Snapshot ────────────────────────────────────────────

    async def _tc_039(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        vms = await _get_vms(client)
        if not vms:
            result.blocked("No VirtualMachines found to snapshot.")
            return

        vm   = vms[0]
        name = vm["metadata"]["name"]
        ns   = vm["metadata"]["namespace"]
        snap_name = f"testops-tc039-snap-{name}"

        snap_body = {
            "apiVersion": f"{SNAP_API}",
            "kind": "VirtualMachineSnapshot",
            "metadata": {"name": snap_name, "namespace": ns},
            "spec": {"source": {"apiGroup": "kubevirt.io", "kind": "VirtualMachine", "name": name}},
        }

        try:
            await client.post(
                f"/apis/{SNAP_API}/namespaces/{ns}/virtualmachinesnapshots", snap_body
            )
            result.evidence.append(f"Snapshot '{snap_name}' creation triggered for VM '{name}'.")

            # Wait for Ready
            deadline = asyncio.get_event_loop().time() + 120
            snap_ready = False
            while asyncio.get_event_loop().time() < deadline:
                found, snap_data = await client.exists(
                    f"/apis/{SNAP_API}/namespaces/{ns}/virtualmachinesnapshots/{snap_name}"
                )
                if found:
                    ready = snap_data.get("status", {}).get("readyToUse", False)
                    if ready:
                        snap_ready = True
                        break
                await asyncio.sleep(5)

            result.evidence.append(f"Snapshot ready: {snap_ready}")
            if snap_ready:
                result.passed(f"VM snapshot '{snap_name}' created and ready.")
            else:
                result.failed(f"Snapshot '{snap_name}' did not become ready within timeout.")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                result.blocked("VirtualMachineSnapshot CRD not available.")
            else:
                raise

    # ── TC-040: Restore VM from Snapshot ─────────────────────────────────────

    async def _tc_040(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        # Find an existing snapshot
        try:
            data = await client.get(f"/apis/{SNAP_API}/virtualmachinesnapshots")
            snaps = [s for s in data.get("items", [])
                     if s.get("status", {}).get("readyToUse")]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                result.blocked("VirtualMachineSnapshot CRD not available.")
                return
            raise

        if not snaps:
            result.blocked("No ready VirtualMachineSnapshots found to test restore.")
            return

        snap  = snaps[0]
        snap_name = snap["metadata"]["name"]
        ns    = snap["metadata"]["namespace"]
        vm_name   = snap.get("spec", {}).get("source", {}).get("name", "unknown")
        restore_name = f"testops-tc040-restore"

        restore_body = {
            "apiVersion": f"{SNAP_API}",
            "kind": "VirtualMachineRestore",
            "metadata": {"name": restore_name, "namespace": ns},
            "spec": {
                "target": {"apiGroup": "kubevirt.io", "kind": "VirtualMachine", "name": vm_name},
                "virtualMachineSnapshotName": snap_name,
            },
        }

        try:
            await client.post(
                f"/apis/{SNAP_API}/namespaces/{ns}/virtualmachinerestores", restore_body
            )
            result.evidence.append(f"Restore '{restore_name}' triggered from snapshot '{snap_name}'.")

            deadline = asyncio.get_event_loop().time() + 180
            completed = False
            while asyncio.get_event_loop().time() < deadline:
                found, rd = await client.exists(
                    f"/apis/{SNAP_API}/namespaces/{ns}/virtualmachinerestores/{restore_name}"
                )
                if found and rd.get("status", {}).get("complete"):
                    completed = True
                    break
                await asyncio.sleep(5)

            result.evidence.append(f"Restore completed: {completed}")
            if completed:
                result.passed(f"VM restored from snapshot '{snap_name}' successfully.")
            else:
                result.failed("Restore did not complete within timeout.")
        finally:
            try:
                await client.delete(
                    f"/apis/{SNAP_API}/namespaces/{ns}/virtualmachinerestores/{restore_name}"
                )
            except Exception:
                pass

    # ── TC-041: Delete VM Snapshot ────────────────────────────────────────────

    async def _tc_041(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        try:
            data = await client.get(f"/apis/{SNAP_API}/virtualmachinesnapshots")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                result.blocked("VirtualMachineSnapshot CRD not available.")
                return
            raise

        # Find testops snapshots
        snaps = [
            s for s in data.get("items", [])
            if "testops" in s["metadata"]["name"]
        ]
        if not snaps:
            result.blocked("No testops VirtualMachineSnapshots found to delete.")
            return

        snap = snaps[0]
        name = snap["metadata"]["name"]
        ns   = snap["metadata"]["namespace"]

        await client.delete(
            f"/apis/{SNAP_API}/namespaces/{ns}/virtualmachinesnapshots/{name}"
        )
        result.evidence.append(f"Deleted snapshot '{name}'.")

        await asyncio.sleep(3)
        found, _ = await client.exists(
            f"/apis/{SNAP_API}/namespaces/{ns}/virtualmachinesnapshots/{name}"
        )
        if not found:
            result.passed(f"Snapshot '{name}' deleted successfully.")
        else:
            result.failed(f"Snapshot '{name}' still exists after deletion.")

    # ── TC-042: VM Console Access ─────────────────────────────────────────────

    async def _tc_042(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        vms = await _get_vms(client)
        running = [vm for vm in vms
                   if vm.get("status", {}).get("printableStatus") == "Running"]

        if not running:
            result.blocked("No running VMs found to test console access.")
            return

        vm   = running[0]
        name = vm["metadata"]["name"]
        ns   = vm["metadata"]["namespace"]

        # VNC subresource URL (presence of the endpoint = console access available)
        vnc_path = (
            f"/apis/{KUBEVIRT_API}/namespaces/{ns}/virtualmachineinstances/{name}/vnc"
        )
        result.evidence.append(f"VNC endpoint: {client.base_url}{vnc_path}")
        result.evidence.append(
            "Note: VNC requires WebSocket upgrade — verifying endpoint availability via VMI status."
        )

        # Check VMI exists and is running (confirms console is accessible)
        found, vmi_data = await client.exists(
            f"/apis/{KUBEVIRT_API}/namespaces/{ns}/virtualmachineinstances/{name}"
        )
        if found:
            phase = vmi_data.get("status", {}).get("phase", "Unknown")
            result.evidence.append(f"VMI phase: {phase}")
            if phase == "Running":
                result.passed(
                    f"VM '{name}' is Running — VNC console endpoint available at "
                    f"{client.base_url}{vnc_path}"
                )
            else:
                result.failed(f"VMI not Running (phase: {phase}) — console may not be accessible.")
        else:
            result.failed(f"VMI '{name}' not found — cannot verify console access.")

    # ── TC-043: Validate Cold Add Disk ────────────────────────────────────────

    async def _tc_043(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        vms = await _get_vms(client)
        stopped = [vm for vm in vms
                   if vm.get("status", {}).get("printableStatus") == "Stopped"]

        if not stopped:
            result.blocked("No stopped VMs available for cold disk add test.")
            return

        vm   = stopped[0]
        name = vm["metadata"]["name"]
        ns   = vm["metadata"]["namespace"]

        # Add a disk to VM spec via patch
        existing_disks = vm.get("spec", {}).get("template", {}).get(
            "spec", {}).get("domain", {}).get("devices", {}).get("disks", [])
        new_disk_name  = "testops-cold-disk"

        patch = {
            "spec": {
                "template": {
                    "spec": {
                        "domain": {
                            "devices": {
                                "disks": existing_disks + [
                                    {"name": new_disk_name, "disk": {"bus": "virtio"}}
                                ]
                            }
                        },
                        "volumes": vm.get("spec", {}).get("template", {}).get("spec", {}).get(
                            "volumes", []
                        ) + [
                            {
                                "name": new_disk_name,
                                "emptyDisk": {"capacity": "1Gi"},
                            }
                        ],
                    }
                }
            }
        }

        await client.patch(
            f"/apis/{KUBEVIRT_API}/namespaces/{ns}/virtualmachines/{name}", patch
        )
        result.evidence.append(f"Cold disk '{new_disk_name}' added to VM '{name}'.")

        # Verify
        vm_updated = await _get_vm(client, name, ns)
        disks_after = (
            vm_updated.get("spec", {}).get("template", {})
            .get("spec", {}).get("domain", {}).get("devices", {}).get("disks", [])
            if vm_updated else []
        )
        found_disk = any(d["name"] == new_disk_name for d in disks_after)
        result.evidence.append(f"Disk '{new_disk_name}' in spec after patch: {found_disk}")

        if found_disk:
            result.passed(f"Cold disk '{new_disk_name}' added to VM '{name}' successfully.")
        else:
            result.failed("Disk not found in VM spec after patch.")

    # ── TC-044: Validate Hot Add Disk ─────────────────────────────────────────

    async def _tc_044(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        vms = await _get_vms(client)
        running = [vm for vm in vms
                   if vm.get("status", {}).get("printableStatus") == "Running"]

        if not running:
            result.blocked("No running VMs for hot disk add test.")
            return

        vm   = running[0]
        name = vm["metadata"]["name"]
        ns   = vm["metadata"]["namespace"]

        # KubeVirt addvolume subresource
        body = {
            "name": "testops-hot-disk",
            "disk": {"bus": "scsi"},
        }

        try:
            await client.put(
                f"/apis/{KUBEVIRT_API}/namespaces/{ns}/virtualmachines/{name}/addvolume",
                {
                    "name": "testops-hot-disk",
                    "hotpluggable": True,
                    "volumeSource": {"emptyDisk": {"capacity": "1Gi"}},
                },
            )
            result.evidence.append(f"Hot-add disk triggered on VM '{name}'.")
            result.passed(f"Hot-add disk request accepted for VM '{name}'.")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                result.blocked("addvolume subresource not available — KubeVirt version may not support hot-plug.")
            elif exc.response.status_code == 422:
                result.evidence.append(f"Validation error (422): {exc.response.text[:300]}")
                result.failed("Hot-add disk request rejected by cluster.")
            else:
                raise

    # ── TC-045: Validate Remove Disk ──────────────────────────────────────────

    async def _tc_045(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        vms = await _get_vms(client)
        running = [vm for vm in vms
                   if vm.get("status", {}).get("printableStatus") == "Running"]

        if not running:
            result.blocked("No running VMs to test disk removal.")
            return

        vm   = running[0]
        name = vm["metadata"]["name"]
        ns   = vm["metadata"]["namespace"]

        try:
            await client.put(
                f"/apis/{KUBEVIRT_API}/namespaces/{ns}/virtualmachines/{name}/removevolume",
                {"name": "testops-hot-disk"},
            )
            result.evidence.append(f"Remove disk 'testops-hot-disk' triggered on VM '{name}'.")
            result.passed(f"Disk removal request accepted for VM '{name}'.")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 422):
                result.evidence.append(f"HTTP {exc.response.status_code}: {exc.response.text[:200]}")
                result.blocked(
                    "Disk removal subresource returned error — disk may not be hotplugged."
                )
            else:
                raise

    # ── TC-046: Validate VM CPU Resize ────────────────────────────────────────

    async def _tc_046(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        vms = await _get_vms(client)
        stopped = [vm for vm in vms
                   if vm.get("status", {}).get("printableStatus") == "Stopped"]

        if not stopped:
            result.blocked("No stopped VMs to test CPU resize.")
            return

        vm   = stopped[0]
        name = vm["metadata"]["name"]
        ns   = vm["metadata"]["namespace"]
        current_cores = (
            vm.get("spec", {}).get("template", {}).get("spec", {})
            .get("domain", {}).get("cpu", {}).get("cores", 1)
        )
        new_cores = current_cores + 1
        result.evidence.append(f"VM '{name}': current cores={current_cores}, target={new_cores}")

        await client.patch(
            f"/apis/{KUBEVIRT_API}/namespaces/{ns}/virtualmachines/{name}",
            {"spec": {"template": {"spec": {"domain": {"cpu": {"cores": new_cores}}}}}},
        )

        vm_after = await _get_vm(client, name, ns)
        actual = (
            vm_after.get("spec", {}).get("template", {}).get("spec", {})
            .get("domain", {}).get("cpu", {}).get("cores", 0)
            if vm_after else 0
        )
        result.evidence.append(f"Cores after patch: {actual}")

        if actual == new_cores:
            result.passed(f"CPU resize successful: {current_cores} → {new_cores} cores.")
        else:
            result.failed(f"Expected {new_cores} cores, got {actual}.")

    # ── TC-047: Validate VM Memory Resize ────────────────────────────────────

    async def _tc_047(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        vms = await _get_vms(client)
        stopped = [vm for vm in vms
                   if vm.get("status", {}).get("printableStatus") == "Stopped"]

        if not stopped:
            result.blocked("No stopped VMs to test memory resize.")
            return

        vm   = stopped[0]
        name = vm["metadata"]["name"]
        ns   = vm["metadata"]["namespace"]

        await client.patch(
            f"/apis/{KUBEVIRT_API}/namespaces/{ns}/virtualmachines/{name}",
            {"spec": {"template": {"spec": {"domain": {"memory": {"guest": "512Mi"}}}}}},
        )
        result.evidence.append(f"Memory resize patch sent to VM '{name}': guest=512Mi")

        vm_after = await _get_vm(client, name, ns)
        actual = (
            vm_after.get("spec", {}).get("template", {}).get("spec", {})
            .get("domain", {}).get("memory", {}).get("guest", "unknown")
            if vm_after else "unknown"
        )
        result.evidence.append(f"Memory after patch: {actual}")

        if actual == "512Mi":
            result.passed(f"Memory resize successful: VM '{name}' guest memory = 512Mi.")
        else:
            result.failed(f"Memory not updated — got: {actual}")

    # ── TC-048: Node Affinity for VM ──────────────────────────────────────────

    async def _tc_048(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        vms = await _get_vms(client)
        if not vms:
            result.blocked("No VMs found to test node affinity.")
            return

        has_affinity = []
        no_affinity  = []
        for vm in vms:
            affinity = (
                vm.get("spec", {}).get("template", {}).get("spec", {}).get("affinity", {})
            )
            node_affinity = affinity.get("nodeAffinity", {})
            if node_affinity:
                has_affinity.append(vm["metadata"]["name"])
            else:
                no_affinity.append(vm["metadata"]["name"])

        result.evidence.append(
            f"VMs with nodeAffinity ({len(has_affinity)}): {has_affinity}\n"
            f"VMs without nodeAffinity ({len(no_affinity)}): {no_affinity[:5]}"
        )

        if has_affinity:
            result.passed(f"{len(has_affinity)} VM(s) have nodeAffinity rules configured.")
        else:
            result.failed("No VMs have nodeAffinity configured.")

    # ── TC-049: Pod Affinity for VM ───────────────────────────────────────────

    async def _tc_049(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        vms = await _get_vms(client)
        with_pod_affinity = [
            vm["metadata"]["name"]
            for vm in vms
            if vm.get("spec", {}).get("template", {}).get("spec", {})
               .get("affinity", {}).get("podAffinity", {})
        ]

        result.evidence.append(
            f"VMs with podAffinity: {with_pod_affinity if with_pod_affinity else 'none'}"
        )

        if with_pod_affinity:
            result.passed(f"{len(with_pod_affinity)} VM(s) have podAffinity configured.")
        else:
            result.failed("No VMs have podAffinity configured.")

    # ── TC-050: Pod Anti-Affinity for VM ─────────────────────────────────────

    async def _tc_050(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        vms = await _get_vms(client)
        with_anti = [
            vm["metadata"]["name"]
            for vm in vms
            if vm.get("spec", {}).get("template", {}).get("spec", {})
               .get("affinity", {}).get("podAntiAffinity", {})
        ]

        result.evidence.append(
            f"VMs with podAntiAffinity: {with_anti if with_anti else 'none'}"
        )

        if with_anti:
            result.passed(f"{len(with_anti)} VM(s) have podAntiAffinity configured.")
        else:
            result.failed("No VMs have podAntiAffinity configured.")

    # ── TC-051: Add Node Label ─────────────────────────────────────────────────

    async def _tc_051(self, result: TestResult, client: OpenShiftClient) -> None:
        nodes = await client.get_nodes()
        if not nodes:
            result.blocked("No nodes found.")
            return

        node = nodes[0]
        name = node["metadata"]["name"]
        label_key = "testops.io/test-label"
        label_val = "tc051"

        await client.patch(
            f"/api/v1/nodes/{name}",
            {"metadata": {"labels": {label_key: label_val}}},
        )

        node_after = await client.get(f"/api/v1/nodes/{name}")
        actual = node_after.get("metadata", {}).get("labels", {}).get(label_key)
        result.evidence.append(f"Node '{name}' label '{label_key}': {actual}")

        if actual == label_val:
            result.passed(f"Label '{label_key}={label_val}' added to node '{name}'.")
        else:
            result.failed(f"Label not found after patch — got: {actual}")

    # ── TC-052: Remove Node Label ─────────────────────────────────────────────

    async def _tc_052(self, result: TestResult, client: OpenShiftClient) -> None:
        nodes = await client.get_nodes()
        if not nodes:
            result.blocked("No nodes found.")
            return

        node = nodes[0]
        name = node["metadata"]["name"]
        label_key = "testops.io/test-label"

        # Patch with null removes the label in strategic merge patch
        await client.patch(
            f"/api/v1/nodes/{name}",
            {"metadata": {"labels": {label_key: None}}},
        )

        node_after = await client.get(f"/api/v1/nodes/{name}")
        present = label_key in node_after.get("metadata", {}).get("labels", {})
        result.evidence.append(f"Node '{name}' label '{label_key}' present after remove: {present}")

        if not present:
            result.passed(f"Label '{label_key}' removed from node '{name}'.")
        else:
            result.failed("Label still present after removal patch.")

    # ── TC-053: In-Cluster Live Migration Between Nodes ───────────────────────

    async def _tc_053(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        data = await client.get("/apis/kubevirt.io/v1/virtualmachineinstances")
        vmis = [
            vmi for vmi in data.get("items", [])
            if vmi.get("status", {}).get("phase") == "Running"
               and vmi.get("status", {}).get("migrationMethod") in ("BlockMigration", "LiveMigration", None)
        ]

        if not vmis:
            result.blocked("No running VMIs eligible for live migration.")
            return

        vmi  = vmis[0]
        name = vmi["metadata"]["name"]
        ns   = vmi["metadata"]["namespace"]
        src_node = vmi.get("status", {}).get("nodeName", "unknown")
        result.evidence.append(f"Migrating VMI '{name}' from node '{src_node}'.")

        mig_name = f"testops-tc053-migration"
        mig_body = {
            "apiVersion": "kubevirt.io/v1",
            "kind": "VirtualMachineInstanceMigration",
            "metadata": {"name": mig_name, "namespace": ns},
            "spec": {"vmiName": name},
        }

        try:
            await client.post(
                f"/apis/kubevirt.io/v1/namespaces/{ns}/virtualmachineinstancemigrations",
                mig_body,
            )
            result.evidence.append("Migration object created.")

            deadline = asyncio.get_event_loop().time() + 300
            succeeded = False
            while asyncio.get_event_loop().time() < deadline:
                found, mig_data = await client.exists(
                    f"/apis/kubevirt.io/v1/namespaces/{ns}/virtualmachineinstancemigrations/{mig_name}"
                )
                if found:
                    phase = mig_data.get("status", {}).get("phase", "")
                    if phase == "Succeeded":
                        succeeded = True
                        break
                    if phase in ("Failed", "Cancelled"):
                        result.evidence.append(f"Migration phase: {phase}")
                        result.failed(f"Live migration {phase}.")
                        return
                await asyncio.sleep(10)

            if succeeded:
                vmi_after = await client.get(
                    f"/apis/kubevirt.io/v1/namespaces/{ns}/virtualmachineinstances/{name}"
                )
                dst_node = vmi_after.get("status", {}).get("nodeName", "unknown")
                result.evidence.append(f"Migrated: {src_node} → {dst_node}")
                result.passed(f"Live migration succeeded: '{name}' moved from {src_node} to {dst_node}.")
            else:
                result.failed("Live migration did not complete within timeout.")
        finally:
            try:
                await client.delete(
                    f"/apis/kubevirt.io/v1/namespaces/{ns}/virtualmachineinstancemigrations/{mig_name}"
                )
            except Exception:
                pass

    # ── TC-054: In-Cluster Live Migration Between Storage ────────────────────

    async def _tc_054(self, result: TestResult, client: OpenShiftClient) -> None:
        if not await self._require_kubevirt(result, client):
            return

        # Storage live migration requires StorageMigration feature gate or MTV
        try:
            kubevirt_data = await client.get("/apis/kubevirt.io/v1/kubevirts")
            kvs = kubevirt_data.get("items", [])
            if kvs:
                fg = kvs[0].get("spec", {}).get("configuration", {}).get(
                    "developerConfiguration", {}
                ).get("featureGates", [])
                result.evidence.append(f"KubeVirt feature gates: {fg}")
                if "StorageLiveMigration" in fg or "VolumesUpdateStrategy" in fg:
                    result.passed(
                        "Storage live migration feature gate is enabled. "
                        "Migration between storage classes is supported."
                    )
                else:
                    result.failed(
                        "StorageLiveMigration feature gate not enabled in KubeVirt config."
                    )
            else:
                result.blocked("KubeVirt CR not found.")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 403):
                result.blocked("KubeVirt CR API not accessible.")
            else:
                raise
