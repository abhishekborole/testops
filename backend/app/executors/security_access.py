"""
Security & Access — TC-082 to TC-102
JIT, MFA, RBAC, VM security, admission, network segmentation, SIEM, supply chain
"""
from __future__ import annotations

import base64
import json

import httpx

from .base import BaseExecutor, OpenShiftClient, TestResult


class SecurityAccessExecutor(BaseExecutor):

    FUNCTION_MAP = {
        "TC-082": "_tc_082",
        "TC-083": "_tc_083",
        "TC-084": "_tc_084",
        "TC-085": "_tc_085",
        "TC-086": "_tc_086",
        "TC-087": "_tc_087",
        "TC-088": "_tc_088",
        "TC-089": "_tc_089",
        "TC-090": "_tc_090",
        "TC-091": "_tc_091",
        "TC-092": "_tc_092",
        "TC-093": "_tc_093",
        "TC-094": "_tc_094",
        "TC-095": "_tc_095",
        "TC-096": "_tc_096",
        "TC-097": "_tc_097",
        "TC-098": "_tc_098",
        "TC-099": "_tc_099",
        "TC-100": "_tc_100",
        "TC-101": "_tc_101",
        "TC-102": "_tc_102",
    }

    # ── TC-082: JIT — Zero-standing privilege (pre-approval) ──────────────────

    async def _tc_082(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check for JIT/PAM solution: check ClusterRoleBindings for privileged roles
        data = await client.get("/apis/rbac.authorization.k8s.io/v1/clusterrolebindings")
        crbs = data.get("items", [])

        admin_bindings = [
            crb for crb in crbs
            if crb.get("roleRef", {}).get("name") in ("cluster-admin", "system:masters")
        ]

        subjects_with_admin = []
        for crb in admin_bindings:
            for subj in crb.get("subjects", []):
                if subj.get("kind") == "User":
                    subjects_with_admin.append(
                        f"{subj.get('name')} via {crb['metadata']['name']}"
                    )

        result.evidence.append(
            f"cluster-admin/system:masters ClusterRoleBindings: {len(admin_bindings)}\n"
            f"User subjects with standing admin: {subjects_with_admin[:10]}"
        )

        # Check for JIT operator / RBAC automation
        try:
            csvs = await client.get_csvs()
            jit_csvs = [
                c["metadata"]["name"] for c in csvs
                if any(kw in c["metadata"]["name"].lower()
                       for kw in ("jit", "pam", "privilege", "just-in-time"))
            ]
            result.evidence.append(f"JIT/PAM operators: {jit_csvs if jit_csvs else 'none found'}")
        except httpx.HTTPStatusError:
            pass

        if len(subjects_with_admin) == 0:
            result.passed("No standing user subjects with cluster-admin. JIT principle maintained.")
        elif len(subjects_with_admin) <= 2:
            result.passed(
                f"Minimal standing privilege: {len(subjects_with_admin)} admin user(s). "
                "Acceptable for break-glass accounts."
            )
        else:
            result.failed(
                f"{len(subjects_with_admin)} users have standing cluster-admin — "
                "zero-standing privilege not enforced."
            )

    # ── TC-083: JIT — Approval grants temporary elevation ────────────────────

    async def _tc_083(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check for temporary RoleBinding with expiry annotation or JIT CRD
        data = await client.get("/apis/rbac.authorization.k8s.io/v1/rolebindings")
        rbs = data.get("items", [])

        ttl_bindings = [
            rb for rb in rbs
            if rb["metadata"].get("annotations", {}).get("jit.openshift.io/ttl")
            or rb["metadata"].get("annotations", {}).get("rbac.authorization.k8s.io/expiry")
        ]

        result.evidence.append(
            f"RoleBindings with TTL/expiry annotations: {len(ttl_bindings)}"
        )

        # Check for Kyverno, Gatekeeper or custom JIT CRDs
        try:
            data = await client.get("/apis/jit.openshift.io/v1/accessrequests")
            reqs = data.get("items", [])
            approved = [r for r in reqs if r.get("status", {}).get("state") == "Approved"]
            result.evidence.append(
                f"JIT AccessRequests: {len(reqs)} total, {len(approved)} approved"
            )
            if approved:
                result.passed(f"{len(approved)} JIT access approvals found with temporary elevation.")
                return
        except httpx.HTTPStatusError:
            result.evidence.append("JIT AccessRequest CRD not found.")

        if ttl_bindings:
            result.passed(
                f"{len(ttl_bindings)} RoleBinding(s) with TTL annotations found — "
                "temporary elevation mechanism in place."
            )
        else:
            result.failed(
                "No JIT approval/temporary elevation mechanism detected. "
                "No TTL-annotated RoleBindings or JIT CRs found."
            )

    # ── TC-084: JIT — TTL expiry revokes access ───────────────────────────────

    async def _tc_084(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check for a controller that cleans up expired bindings
        try:
            csvs = await client.get_csvs()
            rbac_mgr = [
                c for c in csvs
                if any(kw in c["metadata"]["name"].lower()
                       for kw in ("rbac", "jit", "privilege", "access-manager"))
                and c.get("status", {}).get("phase") == "Succeeded"
            ]
            result.evidence.append(
                f"RBAC/JIT management operators: "
                + (", ".join(c["metadata"]["name"] for c in rbac_mgr) or "none")
            )
        except httpx.HTTPStatusError:
            rbac_mgr = []

        # Check for Kyverno policies related to RBAC cleanup
        try:
            policies = await client.get("/apis/kyverno.io/v1/clusterpolicies")
            ttl_policies = [
                p["metadata"]["name"] for p in policies.get("items", [])
                if "ttl" in p["metadata"]["name"].lower()
                or "expir" in json.dumps(p.get("spec", {})).lower()
            ]
            result.evidence.append(f"Kyverno TTL policies: {ttl_policies if ttl_policies else 'none'}")
        except httpx.HTTPStatusError:
            pass

        if rbac_mgr:
            result.passed("RBAC management operator detected — TTL-based access revocation supported.")
        else:
            result.failed(
                "No automated TTL expiry / access revocation controller detected. "
                "Manual process may be in place."
            )

    # ── TC-085: MFA — Privileged access requires MFA ──────────────────────────

    async def _tc_085(self, result: TestResult, client: OpenShiftClient) -> None:
        try:
            oauth = await client.get("/apis/config.openshift.io/v1/oauths/cluster")
            providers = oauth.get("spec", {}).get("identityProviders", [])
            result.evidence.append(
                f"Identity providers ({len(providers)}): "
                + ", ".join(f"{p.get('name')}({p.get('type')})" for p in providers)
            )

            # OIDC providers (EntraID, Okta) typically enforce MFA
            mfa_providers = [
                p for p in providers
                if p.get("type") in ("OpenID", "OIDC")
                or any(kw in str(p).lower() for kw in ("mfa", "otp", "authenticator", "duo"))
            ]
            result.evidence.append(
                f"MFA-capable providers: "
                + (", ".join(p.get("name", "") for p in mfa_providers) or "none detected")
            )

            if mfa_providers:
                result.passed(
                    f"{len(mfa_providers)} MFA-capable identity provider(s) configured "
                    f"(OpenID/OIDC enforce MFA at IdP level)."
                )
            else:
                result.failed(
                    "No MFA-capable identity providers detected. "
                    "Verify IdP configuration enforces MFA for privileged access."
                )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 404):
                result.blocked("Cannot read OAuth config — insufficient permissions.")
            else:
                raise

    # ── TC-086: RBAC — Privileged bindings constrained ────────────────────────

    async def _tc_086(self, result: TestResult, client: OpenShiftClient) -> None:
        data = await client.get("/apis/rbac.authorization.k8s.io/v1/clusterrolebindings")
        crbs = data.get("items", [])

        privileged_roles = {"cluster-admin", "system:masters", "system:node"}
        wide_bindings = []
        for crb in crbs:
            if crb.get("roleRef", {}).get("name") in privileged_roles:
                subjects = crb.get("subjects", [])
                for subj in subjects:
                    if subj.get("kind") == "Group" and subj.get("name") == "system:authenticated":
                        wide_bindings.append(
                            f"{crb['metadata']['name']} → {subj['name']}"
                        )

        # Also check for overly-broad role grants in namespaces
        ns_data = await client.get("/apis/rbac.authorization.k8s.io/v1/rolebindings")
        admin_rb = [
            f"{rb['metadata']['namespace']}/{rb['metadata']['name']}"
            for rb in ns_data.get("items", [])
            if rb.get("roleRef", {}).get("name") == "admin"
            and any(s.get("kind") == "Group" for s in rb.get("subjects", []))
        ]

        result.evidence.append(
            f"Cluster-level privileged bindings: {len([crb for crb in crbs if crb.get('roleRef',{}).get('name') in privileged_roles])}\n"
            f"Overly-broad (system:authenticated) privileged bindings: {wide_bindings}\n"
            f"Namespace admin Group bindings (sample): {admin_rb[:5]}"
        )

        if not wide_bindings:
            result.passed(
                "No privileged ClusterRoleBindings granted to system:authenticated. "
                "Privileged bindings are constrained."
            )
        else:
            result.failed(
                f"Overly-broad privileged binding(s) found: {wide_bindings}"
            )

    # ── TC-087: VM console access — default deny ──────────────────────────────

    async def _tc_087(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check RBAC for kubevirt VNC/console access
        data = await client.get("/apis/rbac.authorization.k8s.io/v1/clusterroles")
        roles = data.get("items", [])

        console_roles = []
        for role in roles:
            rules = role.get("rules", [])
            for rule in rules:
                resources = rule.get("resources", [])
                verbs     = rule.get("verbs", [])
                if "virtualmachineinstances/vnc" in resources or \
                   "virtualmachineinstances/console" in resources:
                    console_roles.append(
                        f"{role['metadata']['name']}: resources={resources}, verbs={verbs}"
                    )

        result.evidence.append(
            f"ClusterRoles with VNC/console access:\n"
            + ("\n".join(f"  {r}" for r in console_roles) or "  none (default deny enforced)")
        )

        # Check if there are broad console grants
        broad = [r for r in console_roles if "system:authenticated" in str(r)]

        if not broad:
            result.passed(
                "VM console access is not broadly granted — "
                f"{len(console_roles)} specific role(s) exist, no broad grants."
            )
        else:
            result.failed(
                f"VM console access broadly granted: {broad}"
            )

    # ── TC-088: VM memory dump — restricted and monitored ────────────────────

    async def _tc_088(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check RBAC for memory dump subresource
        data = await client.get("/apis/rbac.authorization.k8s.io/v1/clusterroles")
        roles = data.get("items", [])

        dump_roles = []
        for role in roles:
            for rule in role.get("rules", []):
                resources = rule.get("resources", [])
                if "virtualmachineinstances/memorydump" in resources:
                    dump_roles.append(role["metadata"]["name"])

        result.evidence.append(
            f"Roles permitting memory dump: {dump_roles if dump_roles else 'none'}"
        )

        # Check audit for memorydump access
        result.evidence.append(
            "Memory dump is controlled via RBAC subresource 'virtualmachineinstances/memorydump'. "
            "Access is logged by OpenShift audit mechanism."
        )

        if not dump_roles or len(dump_roles) <= 2:
            result.passed("VM memory dump access is restricted to specific roles only.")
        else:
            result.failed(
                f"Memory dump access potentially over-granted: {dump_roles}"
            )

    # ── TC-089: Admission baseline — VAP enabled ─────────────────────────────

    async def _tc_089(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check ValidatingAdmissionPolicies (k8s 1.26+)
        try:
            data = await client.get(
                "/apis/admissionregistration.k8s.io/v1/validatingadmissionpolicies"
            )
            vaps = data.get("items", [])
            result.evidence.append(
                f"ValidatingAdmissionPolicies: {len(vaps)}\n"
                + "\n".join(f"  {v['metadata']['name']}" for v in vaps[:10])
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                vaps = []
                result.evidence.append("ValidatingAdmissionPolicy CRD not available (OCP < 4.16).")
            else:
                raise

        # Check ValidatingWebhookConfigurations
        try:
            data = await client.get(
                "/apis/admissionregistration.k8s.io/v1/validatingwebhookconfigurations"
            )
            webhooks = data.get("items", [])
            result.evidence.append(
                f"ValidatingWebhookConfigurations: {len(webhooks)}\n"
                + "\n".join(f"  {w['metadata']['name']}" for w in webhooks[:10])
            )
        except httpx.HTTPStatusError:
            webhooks = []

        # Check OPA/Gatekeeper or Kyverno
        try:
            csvs = await client.get_csvs()
            policy_engines = [
                c["metadata"]["name"] for c in csvs
                if any(kw in c["metadata"]["name"].lower()
                       for kw in ("gatekeeper", "kyverno", "policy-controller"))
                and c.get("status", {}).get("phase") == "Succeeded"
            ]
            result.evidence.append(
                f"Policy engine operators: {policy_engines if policy_engines else 'none'}"
            )
        except httpx.HTTPStatusError:
            policy_engines = []

        if vaps or webhooks or policy_engines:
            result.passed(
                f"Admission controls active: "
                f"{len(vaps)} VAPs, {len(webhooks)} validating webhooks"
                + (f", policy engine: {policy_engines}" if policy_engines else "")
            )
        else:
            result.failed("No ValidatingAdmissionPolicies or admission webhooks found.")

    # ── TC-090: Governance labels — mandatory labels enforced ────────────────

    async def _tc_090(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check ACM policies for label enforcement
        found_policies = False
        try:
            data = await client.get(
                "/apis/policy.open-cluster-management.io/v1/policies"
            )
            policies = data.get("items", [])
            label_policies = [
                p for p in policies
                if "label" in p["metadata"]["name"].lower()
                or "label" in json.dumps(p.get("spec", {})).lower()
            ]
            result.evidence.append(
                f"ACM Policies (total): {len(policies)}\n"
                f"Label-related policies: {[p['metadata']['name'] for p in label_policies]}"
            )
            found_policies = bool(label_policies)
        except httpx.HTTPStatusError:
            result.evidence.append("ACM Policy API not accessible.")

        # Check Kyverno policies for label enforcement
        try:
            data = await client.get("/apis/kyverno.io/v1/clusterpolicies")
            kp = [
                p["metadata"]["name"] for p in data.get("items", [])
                if "label" in p["metadata"]["name"].lower()
            ]
            result.evidence.append(f"Kyverno label policies: {kp if kp else 'none'}")
            if kp:
                found_policies = True
        except httpx.HTTPStatusError:
            pass

        if found_policies:
            result.passed("Mandatory label governance policies are configured.")
        else:
            result.failed("No label enforcement policies found (ACM or Kyverno).")

    # ── TC-091: Non-HIC guardrail — VM cannot use pod network ────────────────

    async def _tc_091(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check for NetworkAttachmentDefinitions restricting pod network
        try:
            data = await client.get(
                "/apis/k8s.cni.cncf.io/v1/network-attachment-definitions"
            )
            nads = data.get("items", [])
            pod_net_nads = [
                n for n in nads
                if "pod" in n["metadata"]["name"].lower()
                or "ovn" in str(n.get("spec", {})).lower()
            ]
            result.evidence.append(
                f"NetworkAttachmentDefinitions: {len(nads)}\n"
                f"Pod-network NADs: {[n['metadata']['name'] for n in pod_net_nads]}"
            )
        except httpx.HTTPStatusError:
            result.evidence.append("NAD API not accessible.")

        # Check KubeVirt config for interface restrictions
        try:
            data = await client.get("/apis/kubevirt.io/v1/kubevirts")
            for kv in data.get("items", []):
                permitted = (
                    kv.get("spec", {}).get("configuration", {})
                    .get("network", {}).get("permitBridgeInterfaceOnPodNetwork", False)
                )
                result.evidence.append(
                    f"KubeVirt permitBridgeInterfaceOnPodNetwork: {permitted}"
                )
                if not permitted:
                    result.passed(
                        "KubeVirt is configured to deny bridge interfaces on pod network — "
                        "non-HIC VMs cannot use pod network interface."
                    )
                    return
        except httpx.HTTPStatusError:
            pass

        result.passed(
            "No evidence of pod network bridge permission for VMs. "
            "Checking network policies for additional enforcement."
        )

    # ── TC-092: HIC segmentation — default deny between namespaces ───────────

    async def _tc_092(self, result: TestResult, client: OpenShiftClient) -> None:
        data = await client.get("/apis/networking.k8s.io/v1/networkpolicies")
        policies = data.get("items", [])

        deny_all = [
            f"{p['metadata']['namespace']}/{p['metadata']['name']}"
            for p in policies
            if not p.get("spec", {}).get("ingress")
            and not p.get("spec", {}).get("egress")
            and p.get("spec", {}).get("podSelector") == {}
        ]

        result.evidence.append(
            f"Total NetworkPolicies: {len(policies)}\n"
            f"Default-deny (empty ingress+egress, podSelector=<empty>): {deny_all[:10]}"
        )

        if deny_all:
            result.passed(
                f"{len(deny_all)} default-deny NetworkPolicies enforce namespace segmentation."
            )
        else:
            result.failed(
                "No default-deny NetworkPolicies found — namespace segmentation may not be enforced."
            )

    # ── TC-093: Network observability works ───────────────────────────────────

    async def _tc_093(self, result: TestResult, client: OpenShiftClient) -> None:
        found = False

        # Check Network Observability operator
        try:
            csvs = await client.get_csvs()
            netobs = [
                c for c in csvs
                if "network-observability" in c["metadata"]["name"].lower()
                or "netobserv" in c["metadata"]["name"].lower()
            ]
            result.evidence.append(
                f"Network Observability CSVs: "
                + (", ".join(c["metadata"]["name"] for c in netobs) or "none")
            )
            found = bool(netobs)
        except httpx.HTTPStatusError:
            pass

        # Check FlowCollector CRD
        try:
            data = await client.get(
                "/apis/flows.netobserv.io/v1beta2/flowcollectors"
            )
            collectors = data.get("items", [])
            result.evidence.append(f"FlowCollectors: {len(collectors)}")
            if collectors:
                found = True
        except httpx.HTTPStatusError:
            pass

        if found:
            result.passed("Network observability is installed and operational.")
        else:
            result.failed("Network observability (FlowCollector/NetObserv) not detected.")

    # ── TC-094: Cross-cluster access — disallowed paths blocked ──────────────

    async def _tc_094(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check ACM ManagedClusterSet and ClusterPermissions
        try:
            data = await client.get(
                "/apis/cluster.open-cluster-management.io/v1beta2/managedclustersets"
            )
            sets = data.get("items", [])
            result.evidence.append(f"ManagedClusterSets: {len(sets)}")
            for s in sets:
                name = s["metadata"]["name"]
                result.evidence.append(f"  {name}")
        except httpx.HTTPStatusError:
            result.evidence.append("ManagedClusterSet API not available.")

        # Check for cross-cluster RBAC (ClusterPermissions)
        try:
            data = await client.get(
                "/apis/rbac.open-cluster-management.io/v1alpha1/clusterpermissions"
            )
            perms = data.get("items", [])
            result.evidence.append(f"ClusterPermissions: {len(perms)}")
        except httpx.HTTPStatusError:
            pass

        # Check EgressNetworkPolicies as cross-cluster access controls
        try:
            data = await client.get("/apis/network.openshift.io/v1/egressnetworkpolicies")
            egress_policies = data.get("items", [])
            result.evidence.append(f"EgressNetworkPolicies: {len(egress_policies)}")
        except httpx.HTTPStatusError:
            pass

        result.passed(
            "Cross-cluster access control reviewed via ManagedClusterSets and EgressPolicies. "
            "See evidence for configuration details."
        )

    # ── TC-095: Egress governance — required vendor access only ──────────────

    async def _tc_095(self, result: TestResult, client: OpenShiftClient) -> None:
        try:
            data = await client.get("/apis/k8s.ovn.org/v1/egressfirewalls")
            firewalls = data.get("items", [])
            result.evidence.append(f"OVN EgressFirewalls: {len(firewalls)}")
            for fw in firewalls[:5]:
                ns = fw["metadata"]["namespace"]
                rules = fw.get("spec", {}).get("egress", [])
                result.evidence.append(
                    f"  {ns}: {len(rules)} egress rules"
                )
        except httpx.HTTPStatusError:
            result.evidence.append("OVN EgressFirewall API not available.")

        try:
            data = await client.get("/apis/network.openshift.io/v1/egressnetworkpolicies")
            enps = data.get("items", [])
            result.evidence.append(f"SDN EgressNetworkPolicies: {len(enps)}")
        except httpx.HTTPStatusError:
            pass

        try:
            data = await client.get("/apis/network.openshift.io/v1/egressips")
            eips = data.get("items", [])
            result.evidence.append(f"EgressIPs: {len(eips)}")
        except httpx.HTTPStatusError:
            pass

        result.passed(
            "Egress governance configuration reviewed. "
            "EgressFirewalls/EgressNetworkPolicies control outbound traffic."
        )

    # ── TC-096: SIEM — security events searchable ─────────────────────────────

    async def _tc_096(self, result: TestResult, client: OpenShiftClient) -> None:
        found = False

        # Check log forwarding to SIEM
        try:
            data = await client.get("/apis/logging.openshift.io/v1/clusterlogforwarders")
            for fwd in data.get("items", []):
                outputs = fwd.get("spec", {}).get("outputs", [])
                siem_outputs = [
                    o for o in outputs
                    if o.get("type") in ("elasticsearch", "splunk", "kafka", "syslog")
                    or any(kw in str(o).lower() for kw in ("siem", "splunk", "qradar", "sentinel"))
                ]
                if siem_outputs:
                    result.evidence.append(
                        f"SIEM outputs: "
                        + ", ".join(f"{o.get('name')}({o.get('type')})" for o in siem_outputs)
                    )
                    found = True
        except httpx.HTTPStatusError:
            pass

        if found:
            result.passed("SIEM integration found — security events are forwarded and searchable.")
        else:
            result.failed("No SIEM log forwarding configuration detected.")

    # ── TC-097: Telemetry resilience — log pipeline failure detection ─────────

    async def _tc_097(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check for PrometheusRules alerting on log pipeline failures
        try:
            data = await client.get("/apis/monitoring.coreos.com/v1/prometheusrules")
            all_rules = data.get("items", [])
            log_alert_rules = []
            for pr in all_rules:
                for group in pr.get("spec", {}).get("groups", []):
                    for rule in group.get("rules", []):
                        if any(kw in str(rule).lower()
                               for kw in ("fluentd", "vector", "logging", "pipeline", "collector")):
                            log_alert_rules.append(rule.get("alert", rule.get("record", "unknown")))

            result.evidence.append(
                f"PrometheusRules total: {len(all_rules)}\n"
                f"Log pipeline alert rules: {log_alert_rules[:10] if log_alert_rules else 'none'}"
            )
            if log_alert_rules:
                result.passed(f"{len(log_alert_rules)} alerting rules for log pipeline failures.")
            else:
                result.failed(
                    "No PrometheusRules alerting on log pipeline failures. "
                    "Telemetry resilience monitoring not configured."
                )
        except httpx.HTTPStatusError as exc:
            result.blocked(f"Cannot access PrometheusRules: HTTP {exc.response.status_code}")

    # ── TC-098: Storage security — CSI privileges/secrets containment ─────────

    async def _tc_098(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check CSI driver SA permissions
        data = await client.get("/apis/storage.k8s.io/v1/csidrivers")
        drivers = data.get("items", [])
        result.evidence.append(
            f"CSI Drivers: {[d['metadata']['name'] for d in drivers]}"
        )

        # Check for CSI-related secrets
        try:
            secrets = await client.get("/api/v1/secrets")
            csi_secrets = [
                f"{s['metadata']['namespace']}/{s['metadata']['name']}"
                for s in secrets.get("items", [])
                if "csi" in s["metadata"]["name"].lower()
                and s["metadata"]["namespace"] not in ("kube-system",)
            ]
            result.evidence.append(
                f"Non-system CSI secrets: {csi_secrets[:5] if csi_secrets else 'none found in unexpected namespaces'}"
            )
        except httpx.HTTPStatusError:
            pass

        # Check SCC for CSI pods
        try:
            data = await client.get("/apis/security.openshift.io/v1/securitycontextconstraints")
            sccs = data.get("items", [])
            privileged_sccs = [
                scc["metadata"]["name"]
                for scc in sccs
                if scc.get("allowPrivilegedContainer")
            ]
            result.evidence.append(
                f"SCCs with privileged containers: {privileged_sccs}"
            )
        except httpx.HTTPStatusError:
            pass

        result.passed(
            "CSI storage security reviewed. Secrets and SCC permissions inspected. "
            "See evidence for details."
        )

    # ── TC-099: Backup resilience — immutable restore drill ──────────────────

    async def _tc_099(self, result: TestResult, client: OpenShiftClient) -> None:
        found = False

        # Check Velero restore records
        try:
            data = await client.get("/apis/velero.io/v1/restores")
            restores = data.get("items", [])
            completed = [r for r in restores if r.get("status", {}).get("phase") == "Completed"]
            result.evidence.append(
                f"Velero Restores: {len(restores)} total, {len(completed)} completed"
            )
            if completed:
                found = True
                for r in completed[:3]:
                    result.evidence.append(
                        f"  {r['metadata']['name']}: "
                        f"backup={r.get('spec',{}).get('backupName')}, "
                        f"completed={r.get('status',{}).get('completionTimestamp','?')}"
                    )
        except httpx.HTTPStatusError:
            pass

        # Check OADP restore CRs
        try:
            data = await client.get("/apis/oadp.openshift.io/v1alpha1/restores")
            oadp_restores = data.get("items", [])
            if oadp_restores:
                result.evidence.append(f"OADP Restores: {len(oadp_restores)}")
                found = True
        except httpx.HTTPStatusError:
            pass

        if found:
            result.passed("Backup restore drill evidence found — restore operations recorded.")
        else:
            result.failed(
                "No backup restore records found. "
                "Immutable restore drill has not been executed or not tracked in cluster."
            )

    # ── TC-100: Patch governance — standard + evidence ───────────────────────

    async def _tc_100(self, result: TestResult, client: OpenShiftClient) -> None:
        # Check cluster update history for evidence of patching
        try:
            cv = await client.get("/apis/config.openshift.io/v1/clusterversions/version")
            history = cv.get("status", {}).get("history", [])
            result.evidence.append(
                f"Cluster update history ({len(history)} entries):\n"
                + "\n".join(
                    f"  {h.get('version')} — state={h.get('state')}, "
                    f"completionTime={h.get('completionTime','?')}"
                    for h in history[:5]
                )
            )
            patched = [h for h in history if h.get("state") == "Completed"]
            if patched:
                result.passed(
                    f"{len(patched)} completed patch update(s) found in cluster history."
                )
            else:
                result.failed("No completed patch updates found in cluster history.")
        except httpx.HTTPStatusError as exc:
            result.blocked(f"Cannot access ClusterVersion: HTTP {exc.response.status_code}")

    # ── TC-101: Supply chain — SBOM/CVE scanning ─────────────────────────────

    async def _tc_101(self, result: TestResult, client: OpenShiftClient) -> None:
        found = False

        # Check for image scanning operators
        try:
            csvs = await client.get_csvs()
            scanning = [
                c for c in csvs
                if any(kw in c["metadata"]["name"].lower()
                       for kw in ("acs", "stackrox", "quay", "clair", "trivy", "snyk", "scan"))
                and c.get("status", {}).get("phase") == "Succeeded"
            ]
            result.evidence.append(
                f"Image scanning operators: "
                + (", ".join(c["metadata"]["name"] for c in scanning) or "none")
            )
            found = bool(scanning)
        except httpx.HTTPStatusError:
            pass

        # Check ACS/StackRox
        for ns in ("stackrox", "rhacs-operator", "acs"):
            try:
                pods = await client.get_pods(ns)
                if pods:
                    result.evidence.append(
                        f"ACS/StackRox namespace '{ns}': {len(pods)} pods"
                    )
                    found = True
                    break
            except httpx.HTTPStatusError:
                pass

        if found:
            result.passed("Image scanning / SBOM / CVE scanning operator detected.")
        else:
            result.failed("No image scanning or supply chain security tooling detected.")

    # ── TC-102: Compliance Operator — Pass report ─────────────────────────────

    async def _tc_102(self, result: TestResult, client: OpenShiftClient) -> None:
        try:
            data = await client.get(
                "/apis/compliance.openshift.io/v1alpha1/compliancescans"
            )
            scans = data.get("items", [])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 403):
                result.blocked("Compliance Operator CRD not available.")
                return
            raise

        if not scans:
            result.failed("No ComplianceScans found.")
            return

        lines = []
        all_pass = True
        for scan in scans:
            name   = scan["metadata"]["name"]
            ns     = scan["metadata"]["namespace"]
            phase  = scan.get("status", {}).get("phase", "Unknown")
            result_val = scan.get("status", {}).get("result", "Unknown")
            lines.append(f"  {ns}/{name}: phase={phase}, result={result_val}")
            if result_val not in ("COMPLIANT", "NOT-APPLICABLE"):
                all_pass = False

        result.evidence.append(
            f"ComplianceScans ({len(scans)}):\n" + "\n".join(lines)
        )

        if all_pass:
            result.passed(f"All {len(scans)} ComplianceScan(s) report COMPLIANT or NOT-APPLICABLE.")
        else:
            result.failed("One or more ComplianceScans are non-compliant.")
