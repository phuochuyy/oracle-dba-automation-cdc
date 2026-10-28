# Worklog — problems hit while building this lab

## Ansible health check (branches `ansible/inventory`, `ansible/health-check`)

- Host has no pip and no sudo: `python3 -m venv` failed (no ensurepip) → `--without-pip` + `get-pip.py`.
- 4 of 8 VMs up (scenario dg-a): the others `UNREACHABLE`, then `failed=1` → ping + `meta: end_host`.
- Rules too strict / wrong window (wallet without TDE, failed logons over 24 h) — fixed.
- `-e` values are strings → template crash; the failed run left no new report and my `mv $(ls -t ...)`
  picked the previous one. Noticed from its content (lag 0, threshold 300), renamed back, re-ran the drill.
- Apply-off drill: FSFO kept saying SYNCHRONIZED — only the lag check shows apply has stopped.
- The 22:19 run coincided with ORA-01017 bursts on Region A: bisected the health SQL on the standby
  (0 new failures per statement and for the whole script); documented in the security lab (finding 1b).

## Patch inventory (branch `ansible/patch-inventory`)

- Grid home top directory is owned by root → my owner check said "not mine" for grid. Owner of the
  `OPatch/opatch` file instead.
- Same fact name in the oracle play and the grid play → the grid play replaced the oracle results on RAC
  hosts. One fact per connecting user.
- Found two stale homes in prm1's inventory (old GoldenGate paths) — documented, not detached.

## Users as code (branch `ansible/user-provisioning`)

- Kept the vault encrypted *and* git-ignored; the vault password file is `~/.vault_pass_dba` (600).
- Checked idempotency the hard way: second run `changed=0`, then a grant revoked by hand came back alone.

## Python daily report (branch `python/daily-report`)

- python-oracledb **thin mode refused by orcl**: `DPY-3001` (native network encryption is thick-only) —
  a direct consequence of the security lab's `SQLNET.ENCRYPTION_SERVER = REQUIRED`. Instant Client
  (basic lite, downloaded without login) + thick mode; TLS would be the long-term answer.
- `DPI-1047 libnnz.so` → `LD_LIBRARY_PATH` in a wrapper.
- GG REST: 9100 is the ServiceManager; the admin server is on 127.0.0.1:9101.

## CDC (branches `cdc/source-setup`, `cdc/kafka-debezium`, `cdc/latency`)

- `ORA-32588`: GoldenGate's schema-level supplemental logging already covered the new table.
- `archive.apache.org` unreachable → Kafka 4.3.2 from the CDN; all downloads checksum-verified.
- Kafka 4: `controller.quorum.voters` refused with `--standalone`; `--property` → `--formatter-property`.
- Connector status RUNNING, task actually failed: `ORA-01950` — flush table goes into the PDB.
- Low-latency polling: no effect. CPU via `V$SESSTAT` of the connector user: 0 (wrong place — MSnn
  background processes); measured whole-VM CPU instead.
- `kill -9` of Connect: 77 duplicate events, 0 lost.
- My leak check printed `leaks=1` after the push: the regex `"[^"]{8,}"` also matched the vault *key*
  `"c##dbzuser"`, which of course is in the SQL/JSON. Re-checked each password value alone (and the git
  history for the connector password): 0. The check now reads the vault as YAML and tests values only.

## Review before interviews (branch `fix/vault-password-file`)

- Dry-running the demos: `ansible-playbook playbooks/health.yml` failed with "Attempting to decrypt but no
  vault secrets found". The vault I added for users-as-code lives in `group_vars/all`, so every playbook
  loads it. `vault_password_file` in `ansible.cfg` (path to a file outside the repo). The README command
  had been broken since the users playbook — only found because I re-ran every demo.
