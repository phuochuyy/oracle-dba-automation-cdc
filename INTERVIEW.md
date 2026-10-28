# Interview prep — DBA Automation & CDC

> Status: **done with evidence** — Ansible (health check, patch inventory, users as code), Python daily
> report, Debezium CDC measured against GoldenGate. Links below.

## What already exists (real evidence, in the other labs)

Automation I already wrote and use daily: `labctl.sh` (starts/stops lab scenarios, isolates Data Guard
regions safely), a role-aware GoldenGate controller for a host without Grid Infrastructure, a script that
re-points GoldenGate distribution paths after a role change, a FAN callout, systemd timers for RMAN
backups and archived-log housekeeping, and test harnesses that measure RTO and verify data. The bugs I
found in my own automation are documented (e.g. a `set -e` + empty `grep` that stopped a script half-way,
a `pgrep -f` that matched its own command line).

## Topics and short answers

**Why Ansible for DBA work?** Idempotent, agentless (SSH), inventory of all hosts in one file. Good for
health checks across many databases, user provisioning, patch inventory (`opatch lspatches`), and running
the same runbook everywhere. Secrets in Ansible Vault, never in the inventory.

**What would a daily health check contain?** Data Guard transport/apply lag and FSFO status, FRA usage on
primary **and** standby, last successful backup per database, GoldenGate process lag, tablespace usage,
invalid objects, failed logons. (Every one of these bit me at least once in the labs.)

**Python with Oracle?** `python-oracledb` in thin mode — no Oracle Client needed.

**CDC with Debezium vs GoldenGate.**

| | GoldenGate | Debezium Oracle connector |
|-|-----------|---------------------------|
| Capture | Integrated Extract (logmining server inside the DB) | LogMiner sessions from Kafka Connect |
| Target | any database, trails, Kafka (GoldenGate for Big Data) | Kafka topics |
| Active-Active, conflict resolution | yes (Auto-CDR) | no — one-way change stream |
| HA with Data Guard | `HANDLEDLFAILOVER`, deployment on DBFS/ACFS | connector restarts from its offset; must follow the new primary |
| License | separate GoldenGate license | open source (needs supplemental logging, LogMiner) |

**What does Debezium need on Oracle?** ARCHIVELOG, supplemental logging (database + table level), a capture
user with LogMiner privileges, and the archived logs kept long enough for the connector to catch up.

## What I built and what I would say about it

**Ansible health check.** One SQL script, key|value output, rated OK/WARN/CRIT per host, Markdown report.
Proof it works: I stopped redo apply on the standby — the check said CRIT (lag 68 s) **while FSFO still said
SYNCHRONIZED**. On the first runs it also found real things: Region B without TDE and without network
encryption, 7 invalid procedures left by an earlier lab, two stale homes in a central inventory.
Hosts that are off are reported as DOWN — the lab never runs all 8 VMs.

**Users as code.** Desired state in YAML, passwords in Ansible Vault, SQL on stdin with `no_log`. Second
run `changed=0`; a grant I revoked by hand came back alone. The report user sees PANs masked — the redaction
from the security lab applies.

**Bug I made in Ansible:** `-e lag_crit_s=30` crashed the rules (extra-vars are strings), and the failed run
left no new report, so my `ls -t` picked the previous one as "drill result". I noticed because it showed
lag 0 and the old threshold. Cast the thresholds, and the drill output is checked before it is saved.

**Python report and DPY-3001.** python-oracledb thin mode cannot do native network encryption; after the
security lab required it on orcl, thin clients were refused. Thick mode with Instant Client for the report;
the clean long-term fix is TLS (TCPS), which thin mode supports. A monitoring user with
`SELECT_CATALOG_ROLE`, `AUDIT_VIEWER`, `CONTAINER_DATA=ALL` — not `SELECT ANY DICTIONARY`.

**Debezium vs GoldenGate, measured on the same rows.** p50 2.4 s to Kafka vs 3.1–3.8 s to the other
database; shorter LogMiner polling sleep changed nothing (not the bottleneck). Restart: clean stop of Kafka
Connect lost nothing and duplicated nothing; `kill -9` lost nothing but re-sent **77 events** — at-least-once,
so consumers must upsert by key. GoldenGate's Replicat with its checkpoint table does not duplicate.
Least privilege worked: no `ANY TABLE` grants for the connector user, just the table.

**Two things I got wrong in CDC:** the connector creates its flush table in the PDB (I gave quota only in
the root → `ORA-01950`, while the REST status still said RUNNING); and my first CPU number was 0 because
LogMiner's work runs in background `MSnn` processes, not in the connector's session.
