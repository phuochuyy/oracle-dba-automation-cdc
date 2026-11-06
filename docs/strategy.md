# Strategy: automation and change data capture

The plan behind this lab, written as I would for a real system. Results: [Ansible](../01-ansible/README.md), [Python](../02-python/README.md), [CDC](../03-cdc/README.md).

## Goal

Stop doing by hand what is repeated, so that a person only looks when something is wrong, without letting a script make a risky change by surprise.

## What is automated, and what stays with a person

| Task | Automated | Stays with a person |
|------|-----------|--------------------|
| Health check | Ansible playbook and report; every check exists because the problem happened in a lab | Reading a CRIT and deciding |
| Patches | Inventory of every Oracle home, compared across hosts | Applying them: not done here, no support contract |
| Users and grants | Declared in a file with secrets in Vault; adds what is missing and revokes what is not listed | Reviewing `--check` output before applying: a revoke can break a service |
| Backups | Timers and a health check in the [backup lab](https://github.com/phuochuyy/oracle-backup-recovery-drills) | Restores |
| Failover | Done by Data Guard, not by these scripts | Failover without zero data loss |

## Rules for scripts

- Safe to run twice, and `--check` before a change.
- Exit code means something: the report's exit code is its number of critical findings.
- Passwords on stdin or in a wallet, never on a command line, checked with `ps`.
- Read-only account for reading: `C##MON` has no access to business data.
- A failed step stops the run. I learned this from a script whose `grep` hid SQL errors.

## How it runs

An hourly health check on each database writes when something changes (backup lab). The Ansible check and the Python report run when the lab is up, by hand: **they are not scheduled**, because the lab is off most of the time. On a real system they would run from a scheduler, with the exit code driving an alert.

## Choosing CDC: GoldenGate or Debezium

| Need | I would choose | Because |
|------|----------------|---------|
| Database to database, two-way, conflict handling | GoldenGate | Exactly-once into a database, conflict resolution built in, works with Data Guard role changes |
| Events to Kafka for other teams, no GoldenGate licence | Debezium | Simple to run, but consumers must handle duplicates after a crash |

Measured [side by side](../03-cdc/README.md): both within seconds here. Delay was not what separated them; delivery guarantees and operations were. A quiet source can lose Debezium's restart point unless a heartbeat keeps it moving.

## Limits

Lab scale, one operator, no alert delivery, no patching. Ansible runs from my own machine.
