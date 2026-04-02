"""
Seed the database with reference data from constants.js.
Run once: python seed.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app.models.location import Location
from app.models.cluster import Cluster
from app.models.category import Category
from app.models.testcase import TestCase
from app.models.environment import Environment

LOCS = {
    "DC-MUM-01": {"label": "Mumbai DC \u2013 Zone A", "zone": "Zone A", "clusters": ["OCP-MUM-PRD-01", "OCP-MUM-PRD-02", "OCP-MUM-UAT-01"]},
    "DC-DEL-01": {"label": "Delhi DC \u2013 Zone B",  "zone": "Zone B", "clusters": ["OCP-DEL-PRD-01", "OCP-DEL-UAT-01"]},
    "DC-BLR-01": {"label": "Bangalore DC \u2013 Zone C", "zone": "Zone C", "clusters": ["OCP-BLR-PRD-01", "OCP-BLR-PRD-02", "OCP-BLR-DEV-01"]},
    "DC-HYD-01": {"label": "Hyderabad DC \u2013 Zone D", "zone": "Zone D", "clusters": ["OCP-HYD-PRD-01", "OCP-HYD-UAT-01"]},
}

CATS = [
    {"id": "cluster-health", "name": "Cluster Health & Core", "critical": True, "tests": ["Node readiness validation", "Control plane component health", "etcd cluster quorum check", "API server availability", "Scheduler and controller-manager status", "DNS resolution (CoreDNS) verification", "Cluster operator health sweep"]},
    {"id": "network",        "name": "Network",               "critical": True, "tests": ["Pod-to-pod connectivity", "East-west traffic via OVN-Kubernetes", "Load balancer VIP assignment", "Ingress controller routing", "NetworkPolicy enforcement", "SDN MTU configuration", "DNS external resolution"]},
    {"id": "storage",        "name": "Storage",               "critical": True, "tests": ["PVC dynamic provisioning (block)", "PVC dynamic provisioning (file)", "PowerMax host connectivity", "Storage class availability", "Volume snapshot creation", "PVC expansion validation", "Data persistence across pod restarts"]},
    {"id": "vm-ops",         "name": "VM Operations",         "critical": False, "tests": ["VM create and boot cycle", "VM start / stop / restart", "VM disk hot-attach", "VM NIC hot-attach", "VM console access", "VM resource limits enforcement", "VM template instantiation"]},
    {"id": "vm-mig",         "name": "VM Migrations",         "critical": True, "tests": ["Live migration (same node)", "Live migration (cross-node)", "vSphere cold import via MTV", "vSphere warm import via MTV", "Migration network bandwidth", "Post-migration health check"]},
    {"id": "security",       "name": "Security",              "critical": True, "tests": ["RBAC policy enforcement", "SCC validation", "Network policy isolation", "Secret encryption at rest", "TLS certificate validity", "Pod security admission", "Audit log availability"]},
    {"id": "monitoring",     "name": "Monitoring & Logging",  "critical": False, "tests": ["Prometheus scrape targets", "Alertmanager connectivity", "Grafana dashboard access", "Loki log ingestion", "Alert routing verification", "Custom metric collection"]},
    {"id": "backup",         "name": "Backup & Restore",      "critical": True, "tests": ["OADP backup creation", "OADP restore validation", "Velero schedule execution", "PV snapshot backup", "Cross-namespace restore", "Backup retention policy"]},
    {"id": "integration",    "name": "Integration",           "critical": False, "tests": ["ACM hub connectivity", "GitOps (ArgoCD) sync", "CI/CD pipeline trigger", "LDAP authentication", "External registry pull", "Webhook endpoint validation"]},
    {"id": "compliance",     "name": "Compliance",            "critical": False, "tests": ["CIS Kubernetes benchmark", "PCI-DSS control mapping", "Pod security standard audit", "Node hardening baseline", "Image scan policy enforcement"]},
    {"id": "self-service",   "name": "Self Service",          "critical": False, "tests": ["OpenShift console login", "Project creation via self-service", "Resource quota enforcement", "User role assignment", "Namespace isolation check"]},
]


def seed():
    db = SessionLocal()
    try:
        # Skip if already seeded
        if db.query(Location).count() > 0:
            print("Already seeded — skipping.")
            return

        print("Seeding locations and clusters...")
        for code, data in LOCS.items():
            loc = Location(code=code, label=data["label"], zone=data["zone"])
            db.add(loc)
            db.flush()
            for cluster_name in data["clusters"]:
                db.add(Cluster(name=cluster_name, location_id=loc.id))

        print("Seeding categories and test cases...")
        for order, cat_data in enumerate(CATS):
            cat = Category(
                slug=cat_data["id"],
                name=cat_data["name"],
                is_critical=cat_data["critical"],
                display_order=order,
            )
            db.add(cat)
            db.flush()
            for tc_order, tc_name in enumerate(cat_data["tests"]):
                db.add(TestCase(name=tc_name, category_id=cat.id, display_order=tc_order))

        print("Seeding environments...")
        for order, name in enumerate(["Production", "UAT", "Dev"]):
            db.add(Environment(name=name, display_order=order))

        db.commit()
        locs = db.query(Location).count()
        clusters = db.query(Cluster).count()
        cats = db.query(Category).count()
        tcs = db.query(TestCase).count()
        envs = db.query(Environment).count()
        print(f"Done: {locs} locations, {clusters} clusters, {cats} categories, {tcs} test cases, {envs} environments.")
    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
