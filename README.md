# Oracle DBA Automation & CDC — Ansible · Python · Debezium

Routine DBA checks automated across the 8 lab VMs with Ansible, a daily health report in Python, and Debezium
CDC measured side by side with GoldenGate on the same source rows.

| Part | Work | Result |
|------|------|--------|
| [A. Ansible](01-ansible/) | health check (DG lag, FSFO, FRA, TDE keystore, backups, failed logons, network encryption), patch inventory of every Oracle home, users and grants as code with Ansible Vault | apply-off drill caught as CRIT while FSFO said SYNCHRONIZED; RU 23.26.1 everywhere, 2 stale inventory homes; idempotent runs (`changed=0`), drift repaired |
| [B. Python](02-python/) | daily report (Markdown + HTML, exit code = CRIT count): DG/FSFO, lag, FRA, backups, keystore, failed logons, encryption, GoldenGate REST | thick mode needed after the security lab (`DPY-3001`); read-only `C##MON` |
| [C. CDC](03-cdc/) | Debezium Oracle connector (LogMiner) → Kafka 4.3, next to GoldenGate on the same PDB | p50 2.4 s vs GoldenGate 3.1–3.8 s; `kill -9` of Connect: 0 lost, 77 duplicates (at-least-once); restart point lost after a quiet day → heartbeat |

Latest re-check: health playbook `failed=0` ([`health-20261103-2131.md`](01-ansible/results/health-20261103-2131.md)),
Debezium 2.44 s vs GoldenGate 3.64 s median, 0 lost — after a first run 63 s behind 3,807 MB of redo the connector
had to mine after 45 h stopped ([CDC re-check](03-cdc/README.md#check-2026-11-03-after-the-hadr-run-5-kafkaconnect-stopped-for-45-h)).

Tooling on the controller (the KVM host, no sudo): `ansible-core` and `python-oracledb` in a virtualenv, Oracle
Instant Client 23.26, JDK 21, Kafka 4.3.2, Debezium 3.7.0. Problems and fixes, including my own mistakes:
[`notes/worklog.md`](notes/worklog.md).
