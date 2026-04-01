export const LOCS = {
  "DC-MUM-01": { label: "Mumbai DC – Zone A", clusters: ["OCP-MUM-PRD-01", "OCP-MUM-PRD-02", "OCP-MUM-UAT-01"] },
  "DC-DEL-01": { label: "Delhi DC – Zone B", clusters: ["OCP-DEL-PRD-01", "OCP-DEL-UAT-01"] },
  "DC-BLR-01": { label: "Bangalore DC – Zone C", clusters: ["OCP-BLR-PRD-01", "OCP-BLR-PRD-02", "OCP-BLR-DEV-01"] },
  "DC-HYD-01": { label: "Hyderabad DC – Zone D", clusters: ["OCP-HYD-PRD-01", "OCP-HYD-UAT-01"] }
};

export const CATS = [
  { id: "cluster-health", name: "Cluster Health & Core", critical: true, tests: ["Node readiness validation", "Control plane component health", "etcd cluster quorum check", "API server availability", "Scheduler and controller-manager status", "DNS resolution (CoreDNS) verification", "Cluster operator health sweep"] },
  { id: "network", name: "Network", critical: true, tests: ["Pod-to-pod connectivity", "East-west traffic via OVN-Kubernetes", "Load balancer VIP assignment", "Ingress controller routing", "NetworkPolicy enforcement", "SDN MTU configuration", "DNS external resolution"] },
  { id: "storage", name: "Storage", critical: true, tests: ["PVC dynamic provisioning (block)", "PVC dynamic provisioning (file)", "PowerMax host connectivity", "Storage class availability", "Volume snapshot creation", "PVC expansion validation", "Data persistence across pod restarts"] },
  { id: "vm-ops", name: "VM Operations", critical: false, tests: ["VM create and boot cycle", "VM start / stop / restart", "VM disk hot-attach", "VM NIC hot-attach", "VM console access", "VM resource limits enforcement", "VM template instantiation"] },
  { id: "vm-mig", name: "VM Migrations", critical: true, tests: ["Live migration (same node)", "Live migration (cross-node)", "vSphere cold import via MTV", "vSphere warm import via MTV", "Migration network bandwidth", "Post-migration health check"] },
  { id: "security", name: "Security", critical: true, tests: ["RBAC policy enforcement", "SCC validation", "Network policy isolation", "Secret encryption at rest", "TLS certificate validity", "Pod security admission", "Audit log availability"] },
  { id: "monitoring", name: "Monitoring & Logging", critical: false, tests: ["Prometheus scrape targets", "Alertmanager connectivity", "Grafana dashboard access", "Loki log ingestion", "Alert routing verification", "Custom metric collection"] },
  { id: "backup", name: "Backup & Restore", critical: true, tests: ["OADP backup creation", "OADP restore validation", "Velero schedule execution", "PV snapshot backup", "Cross-namespace restore", "Backup retention policy"] },
  { id: "integration", name: "Integration", critical: false, tests: ["ACM hub connectivity", "GitOps (ArgoCD) sync", "CI/CD pipeline trigger", "LDAP authentication", "External registry pull", "Webhook endpoint validation"] },
  { id: "compliance", name: "Compliance", critical: false, tests: ["CIS Kubernetes benchmark", "PCI-DSS control mapping", "Pod security standard audit", "Node hardening baseline", "Image scan policy enforcement"] },
  { id: "self-service", name: "Self Service", critical: false, tests: ["OpenShift console login", "Project creation via self-service", "Resource quota enforcement", "User role assignment", "Namespace isolation check"] }
];

export const M = {
  preflight: "claude-haiku-4-5-20251001",
  monitoring: "claude-haiku-4-5-20251001",
  logSummary: "claude-haiku-4-5-20251001",
  failAnalysis: "claude-sonnet-4-6",
  remediation: "claude-sonnet-4-6",
  compare: "claude-sonnet-4-6",
  patterns: "claude-sonnet-4-6",
  goNoGo: "claude-opus-4-6",
  chat: "claude-sonnet-4-6"
};

export const ML = {
  "claude-haiku-4-5-20251001": "Haiku 3.5 · Fast",
  "claude-sonnet-4-6": "Sonnet 4.6 · Balanced",
  "claude-opus-4-6": "Opus 4.6 · Deep Reasoning"
};

export const VM = {
  ready: { label: "Production Ready", icon: "✓", color: "#22c55e", bg: "#f0fdf4", border: "#86efac" },
  "at-risk": { label: "At Risk", icon: "⚠", color: "#f59e0b", bg: "#fffbeb", border: "#fcd34d" },
  "not-ready": { label: "Not Ready", icon: "✗", color: "#ef4444", bg: "#fef2f2", border: "#fca5a5" },
  running: { label: "In Progress", icon: "⏳", color: "#DB0011", bg: "#fdf2f3", border: "#a5b4fc" }
};

export const ENVS = ["Production", "UAT", "Dev"];
