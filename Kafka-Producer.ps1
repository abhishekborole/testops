# TestOPS Kafka Producer
# Publishes test results to testops-topic for a given Run ID

$RunId = "PRT-SCDFV-874"
$FailCount = 2


$KAFKA_PATH = "C:\kafka"
$TOPIC = "testops-topic"
$BROKER = "localhost:9092"

# All 69 test cases — names must exactly match what's in the TestOPS database
$tests = @(
    @{id=1;  name="Node readiness validation";              category="cluster-health"},
    @{id=2;  name="Control plane component health";         category="cluster-health"},
    @{id=3;  name="etcd cluster quorum check";              category="cluster-health"},
    @{id=4;  name="API server availability";                category="cluster-health"},
    @{id=5;  name="Scheduler and controller-manager status";category="cluster-health"},
    @{id=6;  name="DNS resolution (CoreDNS) verification";  category="cluster-health"},
    @{id=7;  name="Cluster operator health sweep";          category="cluster-health"},

    @{id=8;  name="Pod-to-pod connectivity";                category="network"},
    @{id=9;  name="East-west traffic via OVN-Kubernetes";   category="network"},
    @{id=10; name="Load balancer VIP assignment";           category="network"},
    @{id=11; name="Ingress controller routing";             category="network"},
    @{id=12; name="NetworkPolicy enforcement";              category="network"},
    @{id=13; name="SDN MTU configuration";                  category="network"},
    @{id=14; name="DNS external resolution";                category="network"},

    @{id=15; name="PVC dynamic provisioning (block)";       category="storage"},
    @{id=16; name="PVC dynamic provisioning (file)";        category="storage"},
    @{id=17; name="PowerMax host connectivity";             category="storage"},
    @{id=18; name="Storage class availability";             category="storage"},
    @{id=19; name="Volume snapshot creation";               category="storage"},
    @{id=20; name="PVC expansion validation";               category="storage"},
    @{id=21; name="Data persistence across pod restarts";   category="storage"},

    @{id=22; name="VM create and boot cycle";               category="vm-ops"},
    @{id=23; name="VM start / stop / restart";              category="vm-ops"},
    @{id=24; name="VM disk hot-attach";                     category="vm-ops"},
    @{id=25; name="VM NIC hot-attach";                      category="vm-ops"},
    @{id=26; name="VM console access";                      category="vm-ops"},
    @{id=27; name="VM resource limits enforcement";         category="vm-ops"},
    @{id=28; name="VM template instantiation";              category="vm-ops"},

    @{id=29; name="Live migration (same node)";             category="vm-mig"},
    @{id=30; name="Live migration (cross-node)";            category="vm-mig"},
    @{id=31; name="vSphere cold import via MTV";            category="vm-mig"},
    @{id=32; name="vSphere warm import via MTV";            category="vm-mig"},
    @{id=33; name="Migration network bandwidth";            category="vm-mig"},
    @{id=34; name="Post-migration health check";            category="vm-mig"},

    @{id=35; name="RBAC policy enforcement";                category="security"},
    @{id=36; name="SCC validation";                         category="security"},
    @{id=37; name="Network policy isolation";               category="security"},
    @{id=38; name="Secret encryption at rest";              category="security"},
    @{id=39; name="TLS certificate validity";               category="security"},
    @{id=40; name="Pod security admission";                 category="security"},
    @{id=41; name="Audit log availability";                 category="security"},

    @{id=42; name="Prometheus scrape targets";              category="monitoring"},
    @{id=43; name="Alertmanager connectivity";              category="monitoring"},
    @{id=44; name="Grafana dashboard access";               category="monitoring"},
    @{id=45; name="Loki log ingestion";                     category="monitoring"},
    @{id=46; name="Alert routing verification";             category="monitoring"},
    @{id=47; name="Custom metric collection";               category="monitoring"},

    @{id=48; name="OADP backup creation";                   category="backup"},
    @{id=49; name="OADP restore validation";                category="backup"},
    @{id=50; name="Velero schedule execution";              category="backup"},
    @{id=51; name="PV snapshot backup";                     category="backup"},
    @{id=52; name="Cross-namespace restore";                category="backup"},
    @{id=53; name="Backup retention policy";                category="backup"},

    @{id=54; name="ACM hub connectivity";                   category="integration"},
    @{id=55; name="GitOps (ArgoCD) sync";                   category="integration"},
    @{id=56; name="CI/CD pipeline trigger";                 category="integration"},
    @{id=57; name="LDAP authentication";                    category="integration"},
    @{id=58; name="External registry pull";                 category="integration"},
    @{id=59; name="Webhook endpoint validation";            category="integration"},

    @{id=60; name="CIS Kubernetes benchmark";               category="compliance"},
    @{id=61; name="PCI-DSS control mapping";                category="compliance"},
    @{id=62; name="Pod security standard audit";            category="compliance"},
    @{id=63; name="Node hardening baseline";                category="compliance"},
    @{id=64; name="Image scan policy enforcement";          category="compliance"},

    @{id=65; name="OpenShift console login";                category="self-service"},
    @{id=66; name="Project creation via self-service";      category="self-service"},
    @{id=67; name="Resource quota enforcement";             category="self-service"},
    @{id=68; name="User role assignment";                   category="self-service"},
    @{id=69; name="Namespace isolation check";              category="self-service"}
)

Set-Location $KAFKA_PATH

Write-Host "Sending Test Events for Run: $RunId"
Write-Host "Fail Count: $FailCount"

$FailCount = [Math]::Min($FailCount, $tests.Count)
$failedTestIds = ($tests | ForEach-Object { $_.id } | Get-Random -Count $FailCount)

$passedCount = 0
$failedCount = 0

foreach ($test in $tests) {
    $status = if ($failedTestIds -contains $test.id) { $failedCount++; "failed" } else { $passedCount++; "passed" }
    $duration = Get-Random -Minimum 200 -Maximum 3000
    $log = "[{0}] INFO Test {1}" -f (Get-Date -Format "HH:mm:ss"), $status.ToUpper()

    $message = @{
        run_id      = $RunId
        event       = "test_update"
        category_id = $test.category
        test_name   = $test.name
        status      = $status
        duration_ms = $duration
        log         = $log
        timestamp   = (Get-Date).ToString("o")
    } | ConvertTo-Json -Compress

    $message | & "$KAFKA_PATH\bin\windows\kafka-console-producer.bat" --topic $TOPIC --bootstrap-server $BROKER
    Write-Host "  [$status] $($test.name)"
}

# Send run_completed — triggers DB persist and closes the SSE stream
$total     = $tests.Count
$rate      = [Math]::Round(($passedCount / $total) * 100, 1)
$verdict   = if ($rate -ge 95) { "ready" } elseif ($rate -ge 75) { "at-risk" } else { "not-ready" }

$completion = @{
    run_id       = $RunId
    event        = "run_completed"
    overall_rate = $rate
    verdict      = $verdict
    timestamp    = (Get-Date).ToString("o")
} | ConvertTo-Json -Compress

$completion | & "$KAFKA_PATH\bin\windows\kafka-console-producer.bat" --topic $TOPIC --bootstrap-server $BROKER

Write-Host ""
Write-Host "--------------------------------------"
Write-Host "TEST RUN SUMMARY"
Write-Host "Run ID      : $RunId"
Write-Host "Total       : $total"
Write-Host "Passed      : $passedCount"
Write-Host "Failed      : $failedCount"
Write-Host "Pass Rate   : $rate%"
Write-Host "Verdict     : $verdict"
Write-Host "--------------------------------------"
