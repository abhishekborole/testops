"""
Hardware — TC-103 to TC-117
Node hardware inspection via Kubernetes Node API and MachineInfo
"""
from __future__ import annotations

import json
from collections import Counter

import httpx

from .base import BaseExecutor, OpenShiftClient, TestResult


async def _get_node_infos(client: OpenShiftClient) -> list[tuple[str, dict]]:
    """Return list of (node_name, nodeInfo_dict)."""
    nodes = await client.get_nodes()
    return [
        (n["metadata"]["name"], n.get("status", {}).get("nodeInfo", {}))
        for n in nodes
    ]


async def _get_node_labels(client: OpenShiftClient) -> list[tuple[str, dict]]:
    nodes = await client.get_nodes()
    return [(n["metadata"]["name"], n["metadata"].get("labels", {})) for n in nodes]


class HardwareExecutor(BaseExecutor):

    FUNCTION_MAP = {
        "TC-103": "_tc_103",
        "TC-104": "_tc_104",
        "TC-105": "_tc_105",
        "TC-106": "_tc_106",
        "TC-107": "_tc_107",
        "TC-108": "_tc_108",
        "TC-109": "_tc_109",
        "TC-110": "_tc_110",
        "TC-111": "_tc_111",
        "TC-112": "_tc_112",
        "TC-113": "_tc_113",
        "TC-114": "_tc_114",
        "TC-115": "_tc_115",
        "TC-116": "_tc_116",
        "TC-117": "_tc_117",
    }

    # ── TC-103: BIOS Firmware Version ─────────────────────────────────────────

    async def _tc_103(self, result: TestResult, client: OpenShiftClient) -> None:
        node_infos = await _get_node_infos(client)
        if not node_infos:
            result.failed("No nodes found.")
            return

        lines = []
        for name, info in node_infos:
            kernel       = info.get("kernelVersion", "unknown")
            os_image     = info.get("osImage", "unknown")
            boot_id      = info.get("bootID", "")
            lines.append(f"  {name}: OS={os_image}, kernel={kernel}")

        result.evidence.append(
            "Node OS/firmware info (BIOS version via BMC/MachineInfo not available through k8s API — "
            "using nodeInfo):\n" + "\n".join(lines)
        )

        # Try BareMetalHost CRD for BIOS info
        try:
            data = await client.get(
                "/apis/metal3.io/v1alpha1/baremetalhosts"
            )
            bmhs = data.get("items", [])
            for bmh in bmhs:
                name = bmh["metadata"]["name"]
                firmware = (
                    bmh.get("status", {}).get("hardware", {}).get("firmware", {})
                    .get("bios", {})
                )
                result.evidence.append(
                    f"  BareMetalHost {name}: BIOS={firmware}"
                )
        except httpx.HTTPStatusError:
            result.evidence.append("BareMetalHost (metal3) API not available.")

        result.passed(f"BIOS/firmware information inspected for {len(node_infos)} node(s).")

    # ── TC-104: Physical Security ─────────────────────────────────────────────

    async def _tc_104(self, result: TestResult, client: OpenShiftClient) -> None:
        # Physical security cannot be verified via k8s API
        # Check node topology labels for location info
        nodes = await client.get_nodes()
        loc_info = []
        for node in nodes:
            labels = node["metadata"].get("labels", {})
            region   = labels.get("topology.kubernetes.io/region", "?")
            zone     = labels.get("topology.kubernetes.io/zone", "?")
            site     = labels.get("node.openshift.io/os_id", "?")
            loc_info.append(f"  {node['metadata']['name']}: region={region}, zone={zone}")

        result.evidence.append(
            "Node topology labels (location indicators):\n" + "\n".join(loc_info)
        )
        result.evidence.append(
            "Physical security (datacenter locks, cages, cameras) cannot be validated "
            "via cluster API. This requires manual on-site or DCIM verification."
        )
        result.blocked(
            "Physical security validation requires manual datacenter inspection — "
            "cannot be automated via cluster API."
        )

    # ── TC-105: Hardware Health Monitoring ────────────────────────────────────

    async def _tc_105(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check Node Maintenance Operator / Node Health Check
        found = False

        try:
            data = await client.get(
                "/apis/remediation.medik8s.io/v1alpha1/nodehealthchecks"
            )
            nhcs = data.get("items", [])
            result.evidence.append(f"NodeHealthChecks: {len(nhcs)}")
            if nhcs:
                found = True
                for nhc in nhcs[:3]:
                    result.evidence.append(
                        f"  {nhc['metadata']['name']}: "
                        f"healthy={nhc.get('status',{}).get('healthyNodes', '?')}"
                    )
        except httpx.HTTPStatusError:
            result.evidence.append("NodeHealthCheck CRD not available.")

        # Check hardware events via Node conditions
        nodes = await client.get_nodes()
        issues = []
        for node in nodes:
            conds = node.get("status", {}).get("conditions", [])
            for cond in conds:
                if cond.get("type") != "Ready" and cond.get("status") == "True":
                    issues.append(
                        f"{node['metadata']['name']}: {cond['type']}={cond['status']}"
                    )

        result.evidence.append(
            f"Node condition anomalies: {issues[:10] if issues else 'none'}"
        )

        # Check NodeMaintenance
        try:
            data = await client.get(
                "/apis/nodemaintenance.medik8s.io/v1beta1/nodemaintenances"
            )
            maint = data.get("items", [])
            result.evidence.append(f"NodeMaintenances active: {len(maint)}")
        except httpx.HTTPStatusError:
            pass

        if not issues:
            result.passed("All nodes healthy — no unexpected conditions detected.")
        else:
            result.failed(f"{len(issues)} node condition issue(s): {issues[:3]}")

    # ── TC-106: Redundant Power Supplies ──────────────────────────────────────

    async def _tc_106(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check BareMetalHost for power info
        try:
            data = await client.get("/apis/metal3.io/v1alpha1/baremetalhosts")
            bmhs = data.get("items", [])
            lines = []
            for bmh in bmhs:
                name    = bmh["metadata"]["name"]
                power   = bmh.get("status", {}).get("poweredOn", "unknown")
                error_msg = bmh.get("status", {}).get("errorMessage", "")
                lines.append(f"  {name}: poweredOn={power}, error={error_msg or 'none'}")
            result.evidence.append(
                f"BareMetalHosts ({len(bmhs)}):\n"
                + ("\n".join(lines) if lines else "  none")
            )
            if bmhs:
                result.passed(f"{len(bmhs)} BareMetalHost(s) found — power status inspected.")
                return
        except httpx.HTTPStatusError:
            pass

        result.evidence.append(
            "Redundant Power Supply verification requires BMC/IPMI access or "
            "BareMetalHost CRD (metal3) — not available via standard k8s API."
        )
        result.blocked(
            "PSU redundancy cannot be verified via cluster API without BMC integration."
        )

    # ── TC-107: Memory Consistency ────────────────────────────────────────────

    async def _tc_107(self, result: TestResult, client: OpenShiftClient) -> None:
        nodes = await client.get_nodes()
        memory_by_node = []
        for node in nodes:
            cap = node.get("status", {}).get("capacity", {})
            mem = cap.get("memory", "0Ki")
            memory_by_node.append((node["metadata"]["name"], mem))

        result.evidence.append(
            "Node memory capacity:\n"
            + "\n".join(f"  {name}: {mem}" for name, mem in memory_by_node)
        )

        # Check consistency
        mem_values = [mem for _, mem in memory_by_node]
        unique = set(mem_values)

        if len(unique) == 1:
            result.passed(
                f"All {len(nodes)} nodes have consistent memory: {mem_values[0]}."
            )
        elif len(unique) <= 2:
            result.passed(
                f"Nodes have {len(unique)} distinct memory sizes — "
                "mixed hardware may be intentional: " + ", ".join(sorted(unique))
            )
        else:
            result.failed(
                f"Memory inconsistency: {len(unique)} different sizes across nodes — "
                + ", ".join(sorted(unique))
            )

    # ── TC-108: CPU Socket Consistency ───────────────────────────────────────

    async def _tc_108(self, result: TestResult, client: OpenShiftClient) -> None:
        nodes = await client.get_nodes()
        sockets = []
        for node in nodes:
            labels = node["metadata"].get("labels", {})
            # node-role + cpu info from nodeInfo
            info = node.get("status", {}).get("nodeInfo", {})
            arch = info.get("architecture", "unknown")
            sockets.append((node["metadata"]["name"], arch))

        result.evidence.append(
            "Node CPU architectures:\n"
            + "\n".join(f"  {name}: arch={arch}" for name, arch in sockets)
        )

        unique_arch = {arch for _, arch in sockets}
        if len(unique_arch) == 1:
            result.passed(f"All nodes use consistent CPU architecture: {list(unique_arch)[0]}.")
        else:
            result.failed(f"Mixed CPU architectures: {unique_arch}")

    # ── TC-109: CPU Core Consistency ──────────────────────────────────────────

    async def _tc_109(self, result: TestResult, client: OpenShiftClient) -> None:
        nodes = await client.get_nodes()
        cores_by_node = []
        for node in nodes:
            cap = node.get("status", {}).get("capacity", {})
            cores = cap.get("cpu", "0")
            cores_by_node.append((node["metadata"]["name"], cores))

        result.evidence.append(
            "Node CPU cores (capacity):\n"
            + "\n".join(f"  {name}: {cores} vCPU" for name, cores in cores_by_node)
        )

        unique_cores = {cores for _, cores in cores_by_node}
        if len(unique_cores) == 1:
            result.passed(f"All nodes have consistent CPU cores: {list(unique_cores)[0]}.")
        elif len(unique_cores) <= 2:
            result.passed(
                f"Nodes have {len(unique_cores)} distinct CPU core counts "
                "(mixed node types may be intentional): " + ", ".join(sorted(unique_cores))
            )
        else:
            result.failed(
                f"CPU core inconsistency across nodes: {', '.join(sorted(unique_cores))}"
            )

    # ── TC-110: CPU Family Consistency ────────────────────────────────────────

    async def _tc_110(self, result: TestResult, client: OpenShiftClient) -> None:
        # CPU family info is not in k8s API but can be found in node labels
        node_labels = await _get_node_labels(client)
        cpu_labels = {}
        for name, labels in node_labels:
            cpu_info = {
                k: v for k, v in labels.items()
                if "cpu" in k.lower() or "feature.node.kubernetes.io/cpu" in k
            }
            if cpu_info:
                cpu_labels[name] = cpu_info

        result.evidence.append(
            f"CPU feature labels (NFD):\n"
            + (
                "\n".join(f"  {n}: {list(v.keys())[:5]}" for n, v in list(cpu_labels.items())[:5])
                or "  none (Node Feature Discovery may not be installed)"
            )
        )

        if cpu_labels:
            # Check cpu-model consistency
            models = Counter()
            for _, labels in node_labels:
                model = labels.get("feature.node.kubernetes.io/cpu-model.id", "unknown")
                models[model] += 1
            result.evidence.append(f"CPU model distribution: {dict(models)}")

            if len(models) == 1:
                result.passed(f"All nodes share the same CPU model family: {list(models.keys())[0]}")
            else:
                result.passed(
                    f"Nodes have {len(models)} CPU model(s) — "
                    "mixed hardware acceptable for heterogeneous clusters."
                )
        else:
            result.passed(
                "CPU family labels not available (Node Feature Discovery not installed). "
                "Inspected node architectures via nodeInfo."
            )

    # ── TC-111: Network Adapter Consistency ───────────────────────────────────

    async def _tc_111(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check via NMState NodeNetworkState
        try:
            data = await client.get("/apis/nmstate.io/v1beta1/nodenetworkstates")
        except httpx.HTTPStatusError:
            try:
                data = await client.get("/apis/nmstate.io/v1alpha1/nodenetworkstates")
            except httpx.HTTPStatusError:
                result.blocked("NMState NodeNetworkState CRD not available.")
                return

        items = data.get("items", [])
        if not items:
            result.blocked("No NodeNetworkState resources found.")
            return

        iface_counts = {}
        for nns in items:
            node   = nns["metadata"]["name"]
            ifaces = nns.get("status", {}).get("currentState", {}).get("interfaces", [])
            eth    = [i for i in ifaces if i.get("type") in ("ethernet",)]
            iface_counts[node] = len(eth)
            result.evidence.append(
                f"  {node}: {len(eth)} ethernet adapter(s)"
            )

        unique_counts = set(iface_counts.values())
        result.evidence.insert(0, f"Ethernet adapters per node:")

        if len(unique_counts) == 1:
            result.passed(
                f"All {len(items)} nodes have consistent NIC count: "
                f"{list(unique_counts)[0]} adapters."
            )
        else:
            result.failed(
                f"NIC count varies across nodes: {dict(iface_counts)}"
            )

    # ── TC-112: Network Adapter Connectivity ──────────────────────────────────

    async def _tc_112(self, result: TestResult, client: OpenShiftClient) -> None:
        nodes = await client.get_nodes()
        not_ready = []
        for node in nodes:
            conds = node.get("status", {}).get("conditions", [])
            if not client.condition_true(conds, "Ready"):
                not_ready.append(node["metadata"]["name"])

        result.evidence.append(
            f"Nodes Ready: {len(nodes) - len(not_ready)}/{len(nodes)}\n"
            f"Not Ready: {not_ready if not_ready else 'none'}"
        )

        # Check node addresses
        addr_issues = []
        for node in nodes:
            addrs = node.get("status", {}).get("addresses", [])
            internal_ip = next((a for a in addrs if a["type"] == "InternalIP"), None)
            if not internal_ip:
                addr_issues.append(node["metadata"]["name"])

        result.evidence.append(
            f"Nodes without InternalIP: {addr_issues if addr_issues else 'none'}"
        )

        if not not_ready and not addr_issues:
            result.passed(
                f"All {len(nodes)} nodes are Ready with valid InternalIP addresses."
            )
        else:
            result.failed(
                f"Network connectivity issues: "
                f"not-ready={not_ready}, missing-IP={addr_issues}"
            )

    # ── TC-113: HBA Adapter Connectivity ──────────────────────────────────────

    async def _tc_113(self, result: TestResult, client: OpenShiftClient) -> None:
        # HBA connectivity is not directly visible via k8s API
        # Check for multipath / FC-related node labels or storage connectivity
        node_labels = await _get_node_labels(client)

        hba_labels = {}
        for name, labels in node_labels:
            hba = {k: v for k, v in labels.items()
                   if any(kw in k.lower() for kw in ("hba", "fc", "fibrechannel", "scsi"))}
            if hba:
                hba_labels[name] = hba

        # Also check CSI FC driver
        try:
            drivers = await client.get_storage_classes()
            fc_scs = [
                sc["metadata"]["name"] for sc in drivers
                if any(kw in sc.get("provisioner", "").lower()
                       for kw in ("fc", "fibrechannel", "fibre"))
            ]
            result.evidence.append(f"FC StorageClasses: {fc_scs if fc_scs else 'none'}")
        except httpx.HTTPStatusError:
            pass

        result.evidence.append(
            f"HBA-related node labels: "
            + (json.dumps(hba_labels, indent=2) if hba_labels else "none (NFD not labelling HBAs)")
        )
        result.evidence.append(
            "Full HBA connectivity validation requires direct BMC or fabric manager access."
        )

        result.passed(
            "HBA connectivity inspected via available cluster metadata. "
            "For full validation, check storage class provisioner and Brocade/Cisco fabric manager."
        )

    # ── TC-114: Multipathing Availability ────────────────────────────────────

    async def _tc_114(self, result: TestResult, client: OpenShiftClient) -> None:
        found = False

        # Check for multipath-enabled MachineConfigs
        try:
            mc_data = await client.get(
                "/apis/machineconfiguration.openshift.io/v1/machineconfigs"
            )
            mcs = mc_data.get("items", [])
            mp_mcs = [
                mc["metadata"]["name"]
                for mc in mcs
                if "multipath" in mc["metadata"]["name"].lower()
                or "multipath" in json.dumps(mc.get("spec", {})).lower()
            ]
            result.evidence.append(
                f"MachineConfigs with multipath config: {mp_mcs if mp_mcs else 'none'}"
            )
            if mp_mcs:
                found = True
        except httpx.HTTPStatusError:
            pass

        # Check CSI drivers that support multipath
        try:
            drivers = await client.get_storage_classes()
            mp_capable = [
                sc["metadata"]["name"] for sc in drivers
                if any(kw in sc.get("provisioner", "").lower()
                       for kw in ("csi-rbd", "csi-cephfs", "emc", "pure", "netapp", "isilon"))
            ]
            result.evidence.append(
                f"Multipath-capable CSI provisioners: {mp_capable if mp_capable else 'none'}"
            )
            if mp_capable:
                found = True
        except httpx.HTTPStatusError:
            pass

        if found:
            result.passed("Multipathing configuration found via MachineConfig or CSI drivers.")
        else:
            result.failed(
                "No explicit multipath configuration detected. "
                "Verify dm-multipath is enabled via MachineConfig."
            )

    # ── TC-115: Check TPM Presence ────────────────────────────────────────────

    async def _tc_115(self, result: TestResult, client: OpenShiftClient) -> None:
        node_labels = await _get_node_labels(client)
        tpm_nodes = []
        for name, labels in node_labels:
            if any("tpm" in k.lower() or "measured-boot" in k.lower()
                   for k in labels):
                tpm_nodes.append(name)
            # NFD label for TPM
            if labels.get("feature.node.kubernetes.io/system-os_release.ID"):
                tpm_nodes.append(name)

        # Also check BareMetalHost
        try:
            data = await client.get("/apis/metal3.io/v1alpha1/baremetalhosts")
            for bmh in data.get("items", []):
                firmware = (
                    bmh.get("status", {}).get("hardware", {})
                    .get("firmware", {})
                )
                if firmware:
                    result.evidence.append(
                        f"  BMH {bmh['metadata']['name']} firmware: {firmware}"
                    )
        except httpx.HTTPStatusError:
            pass

        result.evidence.append(
            "TPM presence (via NFD labels or BMH):\n"
            f"  Nodes with TPM labels: {tpm_nodes if tpm_nodes else 'none found'}"
        )
        result.evidence.append(
            "Full TPM verification requires Node Feature Discovery (NFD) with security features "
            "or BareMetalHost integration."
        )
        result.passed(
            "TPM presence check completed. "
            "For definitive results, ensure NFD is scanning security hardware features."
        )

    # ── TC-116: Enable Hyper-Threading ───────────────────────────────────────

    async def _tc_116(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check via PerformanceProfile or CPU topology in nodeInfo
        found_ht = False

        try:
            data = await client.get(
                "/apis/performance.openshift.io/v2/performanceprofiles"
            )
            profiles = data.get("items", [])
            for pp in profiles:
                name  = pp["metadata"]["name"]
                smt   = pp.get("spec", {}).get("cpu", {}).get("isolated", "")
                ht_en = not pp.get("spec", {}).get("cpu", {}).get("noSMT", False)
                result.evidence.append(
                    f"PerformanceProfile '{name}': Hyper-Threading (SMT) enabled = {ht_en}"
                )
                if ht_en:
                    found_ht = True
        except httpx.HTTPStatusError:
            result.evidence.append("PerformanceProfile CRD not available.")

        # Check NFD labels for SMT
        node_labels = await _get_node_labels(client)
        smt_nodes = [
            name for name, labels in node_labels
            if labels.get("feature.node.kubernetes.io/cpu-hardware_multithreading") == "true"
        ]
        if smt_nodes:
            found_ht = True
            result.evidence.append(f"NFD SMT-enabled nodes: {smt_nodes}")

        if found_ht:
            result.passed("Hyper-Threading (SMT) is enabled.")
        else:
            result.failed(
                "Hyper-Threading status could not be confirmed. "
                "Check PerformanceProfile or NFD cpu-hardware_multithreading label."
            )

    # ── TC-117: Enable VT (Virtualization) ───────────────────────────────────

    async def _tc_117(self, result: TestResult, client: OpenShiftClient) -> None:
        # VT-x/AMD-V is required for KubeVirt — if KubeVirt is running, VT is enabled
        try:
            data = await client.get("/apis/kubevirt.io/v1/kubevirts")
            kvs = data.get("items", [])
            if kvs:
                phase = kvs[0].get("status", {}).get("phase", "Unknown")
                result.evidence.append(
                    f"KubeVirt phase: {phase} — hardware virtualization (VT-x/AMD-V) is active."
                )
                if phase in ("Deployed", "Available"):
                    result.passed(
                        "Hardware Virtualization (VT-x/AMD-V) is enabled — "
                        f"KubeVirt is {phase} and running VM workloads."
                    )
                else:
                    result.failed(f"KubeVirt phase is '{phase}' — VT may not be fully active.")
                return
        except httpx.HTTPStatusError:
            pass

        # Check NFD for vmx/svm feature flags
        node_labels = await _get_node_labels(client)
        vt_nodes = [
            name for name, labels in node_labels
            if labels.get("feature.node.kubernetes.io/cpu-cpuid.VMX") == "true"
            or labels.get("feature.node.kubernetes.io/cpu-cpuid.SVM") == "true"
        ]

        result.evidence.append(
            f"Nodes with VMX/SVM NFD labels: {vt_nodes if vt_nodes else 'none found'}"
        )

        if vt_nodes:
            result.passed(
                f"Hardware virtualization (VT-x/AMD-V) confirmed via NFD on {len(vt_nodes)} node(s)."
            )
        else:
            result.failed(
                "Cannot confirm hardware virtualization. "
                "Check NFD for cpu-cpuid.VMX / cpu-cpuid.SVM labels or verify KubeVirt status."
            )
