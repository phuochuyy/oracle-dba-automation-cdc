# Oracle DBA Automation & CDC — Ansible · Python · Debezium

> Status: **done** — Ansible across the 8 lab VMs (health check, patch inventory, users as code), a
> Python daily report, and Debezium CDC measured side by side with GoldenGate on the same source rows.

Interview prep notes: [INTERVIEW.md](INTERVIEW.md).

## Goal

1. Automate routine DBA checks and tasks across all lab VMs with Ansible.
2. Produce a daily health report with Python.
3. Stream changes out of Oracle with CDC (Debezium) and compare it with GoldenGate.

## Parts

| Part | Work | Evidence |
|------|------|----------|
| [A. Ansible](01-ansible/) | health check (DG lag, FSFO, FRA, TDE keystore, backups, failed logons, network encryption), patch inventory of every Oracle home, roles/users as code with Ansible Vault | apply-off drill caught as CRIT while FSFO said SYNCHRONIZED; RU 23.26.1 everywhere, 2 stale inventory homes; idempotent runs (`changed=0`), drift repaired |
| [B. Python](02-python/) | daily report (Markdown + HTML, exit code = CRIT count): DG/FSFO, lag, FRA, backups, keystore, failed logons, encryption, GoldenGate REST | thick mode needed after the security lab (`DPY-3001`); read-only `C##MON` |
| [C. CDC](03-cdc/) | Debezium Oracle connector (LogMiner) → Kafka 4.3, next to GoldenGate on the same PDB | INSERT/UPDATE/DELETE events; p50 2.4 s vs GG 3.1–3.8 s; `kill -9` of Connect: 0 lost, 77 duplicates (at-least-once) |

## Deliverables checklist

- [x] `01-ansible/` inventory (no secrets), roles, sample runs
- [x] `02-python/` report script + example output
- [x] `03-cdc/` Kafka + Debezium from tarballs (no containers on this host), connector config, test output
- [x] Lessons learned per part (each part's README, [`notes/worklog.md`](notes/worklog.md))

Tooling on the controller (the KVM host, no sudo): `ansible-core` and `python-oracledb` in a virtualenv,
Oracle Instant Client 23.26, JDK 21, Kafka 4.3.2, Debezium 3.7.0 — all downloaded from public sources.

## CV line (fill only with real results)

`Automated health checks, patch inventory and user provisioning across 8 lab VMs with Ansible (caught a
stopped redo apply that FSFO reported as synchronized); built a daily Data Guard/GoldenGate/backup report in
Python; streamed Oracle changes to Kafka with Debezium and measured it against GoldenGate (latency,
at-least-once duplicates after a crash).`
