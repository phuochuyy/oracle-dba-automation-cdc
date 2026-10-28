# Interview prep — DBA Automation & CDC

> Status: **not built yet.** Preparation notes for the topics this lab will cover. Present them as
> "what I am building", not as finished work.

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

## Planned evidence

Ansible playbooks run against all lab VMs, a daily report generated from the lab, and a Debezium pipeline
streaming BANKDB transactions into Kafka with a comparison to GoldenGate latency.
