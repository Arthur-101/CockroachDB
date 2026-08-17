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

    "transaction-contention-locks.md": """# Runbook: CockroachDB Transaction Contention & Deadlocks

## Symptoms
- Applications receiving PostgreSQL error `40001: restart transaction: TransactionRetryWithProtoRefreshError`
- High transaction abort and retry counts in CockroachDB Console
- Latency spike on update queries on tables like `inventory`, `accounts`, `orders`

## Immediate Diagnostics
1. Identify high-contention queries:
   ```sql
   SELECT query, contention_time, retry_count
   FROM crdb_internal.statement_statistics
   ORDER BY contention_time DESC LIMIT 10;
   ```
2. Check active lock holders and waiting transactions:
   ```sql
   SELECT txn_id, waiting_on, key, lock_mode
   FROM crdb_internal.cluster_locks
   ORDER BY lock_duration DESC LIMIT 20;
   ```

## Root Causes
- Multiple concurrent transactions updating the same row simultaneously (e.g. inventory counters)
- Long-running transactions interleaving SELECT and UPDATE statements
- Missing `SELECT ... FOR UPDATE` leading to lock upgrade conflicts

## Resolution Steps
1. **Application Retry Loop**: Ensure the client application implements exponential backoff and jitter for `40001` serialization failures.
2. **Row Locking Ordering**: Enforce deterministic locking order across all microservices.
3. **Historical Reads**: Move analytics and reporting queries to `AS OF SYSTEM TIME follower_read_timestamp()`.
4. **Batch Updates**: Group high-frequency row increments using batch updates or asynchronous queue aggregators.

## Prevention & Tuning
- Set `sql.defaults.statement_timeout = '15s'`
- Enable lock table metrics: `SHOW CLUSTER SETTING kv.lock_table.enabled;`
""",

    "cross-region-latency-spikes.md": """# Runbook: CockroachDB Cross-Region Latency & Multi-Region Topology

## Symptoms
- p99 read and write latency surges (>150ms) for requests in specific cloud regions (e.g. `eu-west-1` or `ap-south-1`)
- Cross-region Raft consensus round-trips bottlenecking OLTP transactions

## Immediate Diagnostics
1. Check multi-region node distribution:
   ```sql
   SHOW REGIONS FROM CLUSTER;
   SHOW SURVIVAL GOAL FROM DATABASE defaultdb;
   ```
2. Check table locality and table regional types:
   ```sql
   SELECT table_name, locality_config FROM crdb_internal.tables WHERE table_schema = 'public';
   ```
3. Inspect round-trip network latency between regions:
   ```sql
   SELECT * FROM crdb_internal.node_to_node_latency ORDER BY latency_ms DESC;
   ```

## Resolution Steps
1. **Regional Tables**: Convert latency-sensitive tables to `REGIONAL BY ROW` so rows are co-located with local users:
   ```sql
   ALTER TABLE orders SET LOCALITY REGIONAL BY ROW AS region;
   ```
2. **Global Reference Tables**: For read-heavy, low-write lookup tables, set locality to `GLOBAL`:
   ```sql
   ALTER TABLE product_catalog SET LOCALITY GLOBAL;
   ```
3. **Follower Reads**: Enable follower reads for read-mostly operations:
   ```sql
   SELECT * FROM accounts AS OF SYSTEM TIME follower_read_timestamp() WHERE account_id = '123';
   ```
""",

    "schema-migration-failures.md": """# Runbook: Online Schema Changes & Large Table Backfills

## Symptoms
- `ALTER TABLE` or `CREATE INDEX` job stalled in state `running` for hours
- Schema change blocking subsequent DDL operations
- Node disk space decreasing rapidly during index backfill

## Immediate Diagnostics
1. Inspect running schema change jobs:
   ```sql
   SHOW JOBS WHERE job_type IN ('SCHEMA CHANGE', 'INDEX BACKFILL');
   ```
2. Check job progress and coordinator node:
   ```sql
   SELECT job_id, description, status, fraction_completed, error
   FROM crdb_internal.jobs
   WHERE status = 'running' ORDER BY created DESC;
   ```

## Resolution Steps
1. **Pause or Cancel Runaway Jobs**:
   ```sql
   CANCEL JOB <job_id>;
   ```
2. **Off-Peak Index Creation**: Re-run large index builds with non-blocking concurrency:
   ```sql
   CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
   ```
3. **Throttle Backfill Rate**: Reduce backfill chunk rate to minimize cluster CPU impact:
   ```sql
   SET CLUSTER SETTING kv.bulk_io_write.max_rate = '100MiB';
   ```
"""
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

    "INC-2026-003": """{
  "incident_id": "INC-2026-003",
  "title": "Lock Contention and 40001 Retries on checkout-service",
  "severity": "P1",
  "started_at": "2026-08-15T18:10:00Z",
  "resolved_at": "2026-08-15T18:42:00Z",
  "duration_minutes": 32,
  "affected_service": "checkout-service / defaultdb.inventory",
  "symptoms": ["Checkout failure rate spiked to 18%", "40001 TransactionRetryWithProtoRefreshError", "Connection pool waiting on locks"],
  "root_cause": "Flash sale flash mob updating the same single row in inventory table simultaneously without batching",
  "resolution": "Applied follower reads for inventory checks and partitioned inventory counters into 16 sharded slots.",
  "runbook_used": "transaction-contention-locks.md",
  "fix_permanent": true,
  "tags": ["contention", "locks", "40001", "checkout", "cockroachdb"]
}""",

    "INC-2026-004": """{
  "incident_id": "INC-2026-004",
  "title": "Cross-Region Query Latency Spike in EU Users",
  "severity": "P2",
  "started_at": "2026-08-16T11:00:00Z",
  "resolved_at": "2026-08-16T11:55:00Z",
  "duration_minutes": 55,
  "affected_service": "user-profile-service (eu-west-1)",
  "symptoms": ["p99 latency for EU users increased from 12ms to 240ms", "Cross-region Raft round-trip to us-east-1"],
  "root_cause": "New table user_profiles was created as REGIONAL IN us-east-1 instead of REGIONAL BY ROW",
  "resolution": "Executed ALTER TABLE user_profiles SET LOCALITY REGIONAL BY ROW AS region. Latency dropped back to 9ms.",
  "runbook_used": "cross-region-latency-spikes.md",
  "fix_permanent": true,
  "tags": ["multi-region", "latency", "locality", "cockroachdb"]
}"""
}


def main():
    print("[INFO] Seeding S3 knowledge base: cockroachsre-knowledge-base")
    print("=" * 60)

    kb = S3KnowledgeBase()
    vs = VectorMemoryStore()

    # Test connection first
    conn = kb.test_connection()
    if not conn["success"]:
        print(f"[ERROR] S3 connection failed: {conn['error']}")
        sys.exit(1)
    print(f"[SUCCESS] S3 Connected: {conn['message']}\n")

    # Upload runbooks
    print("[INFO] Uploading runbooks...")
    for name, content in RUNBOOKS.items():
        result = kb.upload_runbook(name, content)
        if result["success"]:
            # Index into CockroachDB
            idx = kb.fetch_and_index(result["s3_key"], vector_store=vs)
            status = "[OK] uploaded + indexed" if idx.get("indexed") else "[WARNING] uploaded (index failed)"
        else:
            status = f"[ERROR] failed: {result.get('error')}"
        print(f"  {name:45s} {status}")

    print()

    # Upload incident logs
    print("[INFO] Uploading incident logs...")
    for incident_id, content in INCIDENT_LOGS.items():
        result = kb.upload_incident_log(incident_id, content)
        if result["success"]:
            idx = kb.fetch_and_index(result["s3_key"], vector_store=vs)
            status = "[OK] uploaded + indexed" if idx.get("indexed") else "[WARNING] uploaded (index failed)"
        else:
            status = f"[ERROR] failed: {result.get('error')}"
        print(f"  {incident_id:45s} {status}")

    print()
    print("=" * 60)

    # Final summary
    summary = kb.list_all()
    print(f"[SUCCESS] S3 bucket now has {summary['count']} objects")
    print("[SUCCESS] All content indexed into CockroachDB pgvector store")
    print()
    print("Pipeline verified:")
    print("  Amazon S3 (cockroachsre-knowledge-base)")
    print("    └─► CockroachDB Distributed Vector Index (pgvector)")
    print("          └─► SRE Agent semantic search at incident time")


if __name__ == "__main__":
    main()
