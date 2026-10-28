# Oracle DBA Automation & CDC — Ansible · Python · Debezium

> Status: **planned**. Automation of routine DBA work across the lab VMs, and change data capture
> out of Oracle as an alternative to GoldenGate.

Interview prep notes: [INTERVIEW.md](INTERVIEW.md).

## Goal

1. Automate routine DBA checks and tasks across all lab VMs with Ansible.
2. Produce a daily health report with Python.
3. Stream changes out of Oracle with CDC (Debezium) and compare it with GoldenGate.

## Parts

| Part | Work | Evidence |
|------|------|----------|
| A. Ansible | Playbooks: health check (DG lag, FRA, tablespaces, invalid objects), user provisioning, RU patch inventory (`opatch lspatches`) across all lab VMs | playbook output |
| B. Python | Daily report: DG/FSFO status, GG lag, backup age → HTML/Markdown | sample report |
| C. CDC | Debezium Oracle connector (LogMiner) → Kafka; compare with GoldenGate | events received for INSERT/UPDATE/DELETE |

## Deliverables checklist

- [ ] `01-ansible/` inventory (no secrets), roles, sample runs
- [ ] `02-python/` report script + example output
- [ ] `03-cdc/` docker-compose for Kafka + Debezium, connector config, test output
- [ ] Lessons learned per part in this README

## CV line (fill only with real results)

`Automated health checks across N VMs with Ansible; built a daily Data Guard/GoldenGate/backup report in Python; streamed Oracle changes to Kafka with Debezium.`
