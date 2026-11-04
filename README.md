# Oracle DBA Automation & CDC

Routine DBA work automated across the lab servers, and change data capture with Debezium compared side by side with GoldenGate on the same source rows.

## What is in it

- **Ansible**: a health check, a patch inventory of every Oracle home (inventory only, no patching), and database users and grants managed as code with Ansible Vault.
- **Python**: a health report across all databases, whose exit code can drive an alert. It can be scheduled; in the lab it runs when the lab is up.
- **CDC**: Debezium to Kafka next to GoldenGate, with delay, crash behaviour and restart problems measured.

## Where to look

- [Ansible](01-ansible/README.md)
- [Python report](02-python/README.md)
- [CDC](03-cdc/README.md)
- [Worklog, including my mistakes](notes/worklog.md)
