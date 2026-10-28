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
