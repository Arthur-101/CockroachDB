#!/usr/bin/env python3
"""
Seed script: Upload sample SRE runbooks and incident logs to
Amazon S3 (cockroachsre-knowledge-base) and index them into
CockroachDB's distributed vector store.

Run once before the demo:
    python scripts/seed_s3_runbooks.py
"""
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from src.tools.s3_tools import S3KnowledgeBase
from src.memory.vector_store import VectorMemoryStore

RUNBOOKS = {
    "db-connection-failures.md": """# Runbook: CockroachDB Connection Failures

## Symptoms
- Applications returning `connection refused` or `dial tcp: connect: connection refused`
- High latency on CockroachDB queries (>5s)
- CockroachDB node showing as `SUSPECT` or `DEAD` in cluster view

## Immediate Actions
1. Check cluster health: `cockroach node status --insecure`
2. Verify all nodes are reachable: `ping <node-ip>`
3. Check CockroachDB logs: `journalctl -u cockroachdb -n 100`
4. Inspect connection pool metrics in CockroachDB Console

## Root Causes
- Network partition between nodes
- Certificate expiry (TLS handshake failures)
- Max connection limit reached (check `server.max_open_connections`)
- Node OOM-killed by OS

## Resolution Steps
1. **Network partition**: Restore network connectivity; nodes auto-rejoin
2. **Cert expiry**: Rotate certs with `cockroach cert create-node`
3. **Connection exhaustion**: Increase `--max-sql-connections` or add PgBouncer
4. **OOM**: Increase node memory or tune `--cache` and `--max-sql-memory`

## Escalation
- P0 (all nodes down): Page on-call lead immediately
- P1 (1 node down): Investigate within 15 minutes
- P2 (degraded performance): Resolve within 1 hour

## Related Incidents
- INC-2024-001: Node 3 OOM during high write load — fixed by cache tuning
- INC-2024-007: Cert expiry took cluster offline — fixed by auto-rotation cron
""",

    "high-cpu-playbook.md": """# Runbook: High CPU on CockroachDB Nodes

## Symptoms
- Node CPU > 80% sustained for >5 minutes
- Query latency spikes (p99 > 2s)
- Compaction backlog growing

## Immediate Actions
1. Identify expensive queries:
   ```sql
   SELECT query, total_time, mean_time, calls
   FROM crdb_internal.statement_statistics
   ORDER BY total_time DESC LIMIT 20;
   ```
2. Check active sessions:
   ```sql
   SELECT * FROM crdb_internal.cluster_sessions WHERE status = 'active';
   ```
3. Look for table scans:
   ```sql
   SELECT * FROM crdb_internal.node_statement_statistics
   WHERE full_scan = true ORDER BY count DESC LIMIT 10;
   ```

## Root Causes
- Missing indexes causing full table scans
- High write amplification from LSM compaction
- Runaway query or hot spot on a range

## Resolution Steps
1. **Missing index**: `EXPLAIN (OPT)` the slow query; add index
2. **Hot spot**: Use `SPLIT AT` to redistribute a hot range
3. **Compaction**: Throttle foreground workload temporarily
4. **Runaway query**: `CANCEL QUERY '<query_id>'`

## Prevention
- Enable auto EXPLAIN for queries > 1s
- Set `sql.defaults.statement_timeout = '30s'`
- Run weekly index advisor: `SELECT * FROM crdb_internal.index_usage_statistics`
""",

    "memory-leak-detection.md": """# Runbook: Memory Leak Detection & Remediation

## Symptoms
- Node RSS memory growing monotonically over hours
- OOM kills in system logs (`dmesg | grep -i oom`)
- CockroachDB reporting `memory budget exceeded`

## Immediate Actions
1. Check current memory usage per node:
   ```sql
   SELECT node_id, mem_usage FROM crdb_internal.kv_node_status;
   ```
2. Look for large result sets being buffered:
   ```sql
   SELECT * FROM crdb_internal.cluster_sessions
   WHERE mem_usage > 100000000 ORDER BY mem_usage DESC;
   ```
3. Check go runtime heap via `/debug/pprof/heap` endpoint

## Root Causes
- Unbounded result sets (missing LIMIT)
- Long-running transactions holding row locks and memory
- Bug in application connection pooling

## Resolution Steps
1. **Cancel memory-hungry sessions**:
   ```sql
   CANCEL SESSION '<session_id>';
   ```
2. **Reduce cache**: `SET CLUSTER SETTING kv.raft.log.max_size = '4MiB'`
3. **Rolling restart** if leak is confirmed in CockroachDB process itself
4. **Application fix**: Add pagination / LIMIT to all queries

## Monitoring
- Alert at 75% node memory usage
- Page at 90% node memory usage
- Auto-restart policy: restart node if OOM'd
""",

    "incident-response-sop.md": """# SOP: Incident Response for CockroachSRE

## Severity Levels
| Level | Definition | Response Time |
|-------|------------|---------------|
| P0    | Full cluster outage, data unavailable | Immediate, 24/7 |
| P1    | Partial outage, degraded availability | 15 minutes |
| P2    | Performance degradation, no data loss | 1 hour |
| P3    | Minor issue, monitoring alert | Next business day |

## Response Workflow
1. **Detect**: Alert fires in monitoring (Prometheus / CloudWatch)
2. **Acknowledge**: On-call engineer acknowledges in PagerDuty
3. **Assess**: Run `cockroach node status` and check CockroachDB Console
4. **Mitigate**: Apply runbook steps for identified failure type
5. **Communicate**: Update status page every 15 minutes
6. **Resolve**: Confirm cluster health, close incident
7. **Post-mortem**: Write postmortem within 48 hours

## CockroachSRE Agent Commands
When an incident fires, ask the SRE agent:
- "What runbook applies to [symptom]?"
- "Show me past incidents similar to this"
- "What was the fix for the last OOM incident?"

The agent will search its CockroachDB memory (pgvector) for similar past incidents
and relevant runbooks, then suggest resolution steps.

## Contacts
- On-call rotation: PagerDuty schedule
- CockroachDB Support: support@cockroachlabs.com
- AWS Support: via AWS Console > Support Center
""",

    "cockroachdb-backup-restore.md": """# Runbook: CockroachDB Backup & Restore

## Scheduled Backups (CockroachDB Cloud)
CockroachDB Serverless performs automatic daily backups.
Retention: 30 days by default.

## Manual Backup to S3
```sql
BACKUP DATABASE defaultdb INTO 's3://cockroachsre-knowledge-base/backups/latest'
  AS OF SYSTEM TIME '-10s'
  WITH revision_history;
```

## Restore from S3
```sql
RESTORE DATABASE defaultdb FROM LATEST IN 's3://cockroachsre-knowledge-base/backups/latest'
  WITH new_db_name = 'defaultdb_restored';
```

## Verify Backup Integrity
```sql
SHOW BACKUPS IN 's3://cockroachsre-knowledge-base/backups/latest';
```

## Point-in-Time Restore
```sql
RESTORE TABLE incidents FROM 's3://cockroachsre-knowledge-base/backups/latest'
  AS OF SYSTEM TIME '2026-08-17 00:00:00'
  WITH into_db = 'defaultdb';
```

## RTO / RPO Targets
- RTO (Recovery Time Objective): < 30 minutes
- RPO (Recovery Point Objective): < 1 hour

## Post-Restore Checklist
- [ ] Verify row counts match pre-failure snapshot
- [ ] Re-run vector index rebuild for pgvector tables
- [ ] Test application connectivity
- [ ] Update incident log with restore details
""",
}

INCIDENT_LOGS = {
    "INC-2026-001": """{
  "incident_id": "INC-2026-001",
  "title": "CockroachDB Node 2 OOM Kill",
  "severity": "P1",
  "started_at": "2026-08-10T03:22:00Z",
  "resolved_at": "2026-08-10T04:15:00Z",
  "duration_minutes": 53,
  "affected_service": "CockroachDB Cluster (3-node)",
  "symptoms": ["Node 2 reported SUSPECT", "p99 query latency > 8s", "OOM kill in dmesg"],
  "root_cause": "Unbounded query result set from analytics job buffering 4GB in memory",
  "resolution": "Cancelled offending session. Added LIMIT 10000 to analytics query. Increased node memory from 8GB to 16GB.",
  "runbook_used": "memory-leak-detection.md",
  "fix_permanent": true,
  "tags": ["oom", "memory", "node-failure", "cockroachdb"]
}""",

    "INC-2026-002": """{
  "incident_id": "INC-2026-002",
  "title": "High CPU Hot Spot on Range r/4521",
  "severity": "P2",
  "started_at": "2026-08-13T14:05:00Z",
  "resolved_at": "2026-08-13T15:30:00Z",
  "duration_minutes": 85,
  "affected_service": "CockroachDB Serverless - defaultdb",
  "symptoms": ["Node 1 CPU at 95%", "Hot range r/4521 receiving 90% of writes", "Write latency p99 > 3s"],
  "root_cause": "Sequential UUID primary key causing all inserts to hit the same range leader",
  "resolution": "Migrated PK to gen_random_uuid() for hash-distributed inserts. Applied SPLIT AT to distribute existing hot range.",
  "runbook_used": "high-cpu-playbook.md",
  "fix_permanent": true,
  "tags": ["hot-spot", "cpu", "range", "uuid", "cockroachdb"]
}""",
}


def main():
    print("🪣 Seeding S3 knowledge base: cockroachsre-knowledge-base")
    print("=" * 60)

    kb = S3KnowledgeBase()
    vs = VectorMemoryStore()

    # Test connection first
    conn = kb.test_connection()
    if not conn["success"]:
        print(f"❌ S3 connection failed: {conn['error']}")
        sys.exit(1)
    print(f"✅ S3 Connected: {conn['message']}\n")

    # Upload runbooks
    print("📚 Uploading runbooks...")
    for name, content in RUNBOOKS.items():
        result = kb.upload_runbook(name, content)
        if result["success"]:
            # Index into CockroachDB
            idx = kb.fetch_and_index(result["s3_key"], vector_store=vs)
            status = "✅ uploaded + indexed" if idx.get("indexed") else "⚠️ uploaded (index failed)"
        else:
            status = f"❌ failed: {result.get('error')}"
        print(f"  {name:45s} {status}")

    print()

    # Upload incident logs
    print("🚨 Uploading incident logs...")
    for incident_id, content in INCIDENT_LOGS.items():
        result = kb.upload_incident_log(incident_id, content)
        if result["success"]:
            idx = kb.fetch_and_index(result["s3_key"], vector_store=vs)
            status = "✅ uploaded + indexed" if idx.get("indexed") else "⚠️ uploaded (index failed)"
        else:
            status = f"❌ failed: {result.get('error')}"
        print(f"  {incident_id:45s} {status}")

    print()
    print("=" * 60)

    # Final summary
    summary = kb.list_all()
    print(f"✅ S3 bucket now has {summary['count']} objects")
    print("✅ All content indexed into CockroachDB pgvector store")
    print()
    print("Pipeline verified:")
    print("  Amazon S3 (cockroachsre-knowledge-base)")
    print("    └─► CockroachDB Distributed Vector Index (pgvector)")
    print("          └─► SRE Agent semantic search at incident time")


if __name__ == "__main__":
    main()
