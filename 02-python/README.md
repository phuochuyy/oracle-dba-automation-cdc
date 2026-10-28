# B. Python — daily report

[`daily_report.py`](daily_report.py) (run by [`run_report.sh`](run_report.sh)) connects to every database
of [`targets.yml`](targets.yml) as the read-only `C##MON`, asks each GoldenGate deployment for its processes,
rates findings with the **same thresholds as the Ansible health check**, and writes
`reports/report-<time>.md` and `.html`. Exit code = number of CRIT → usable from cron/systemd as an alert.

```
02-python/run_report.sh          # e.g. cron: 0 7 * * *  .../run_report.sh || mail -s "lab CRIT" ...
```

Sample: [`reports/report-20261028-2308.md`](reports/report-20261028-2308.md) — orcl and orcl_stb OK
(FSFO synchronized, target orcl_stb, observer obs-r1, keystore auto-login, AES256 connection), orcl3 CRIT
(standby destination deferred: Region B runs without its standby in this scenario) + WARN no TDE, 7 invalid
objects, unencrypted connection; orcl3_stb DOWN (VM off); GG_A on prm1 and GG_B on prm3: 4 processes
running, lag 0–3 s. The 24-hour failed-logon sources still show the observer storm from before the fix
(SYS ORA-01031 ~400 per database) and the open empty-user ORA-01017.

## Design choices

| Choice | Why |
|--------|-----|
| **thick mode** (Oracle Instant Client 23.26 in `~/opt`, `LD_LIBRARY_PATH`) | thin mode got `DPY-3001: Native Network Encryption and Data Integrity is only supported in python-oracledb thick mode` from orcl — the security lab requires native encryption on the server. orcl3 (not hardened) accepted thin. Long-term: TLS (TCPS) listener endpoints, which thin mode supports |
| `C##MON`: `CREATE SESSION`, `SELECT_CATALOG_ROLE`, `AUDIT_VIEWER`, `CONTAINER_DATA = ALL` | read-only; no `SELECT ANY DICTIONARY` (flagged by the security assessment). Created with the Ansible users-as-code role (common user in the root, so the standbys get it through redo) |
| passwords from the **Ansible Vault** of 01-ansible | one secret store for the repo; nothing in `targets.yml` |
| GoldenGate via REST on `127.0.0.1:9101` over SSH | the admin servers listen on localhost only (good); the node is found by asking every candidate, since GG_A moves with the Data Guard role. The REST password goes to curl as a config file on stdin (`-K`), never on a command line |
| RAC DSNs list both nodes (`host1,host2:1521/service`) | works with either node down; 3 s connect timeout, so a stopped VM costs 3 s and shows as DOWN |
| backups rated only where they run (`backups_here`) | orcl's own control file knows only backups from 5 days ago (125 h) — RAC A backs up on the standby (21 h) |

## Mistakes on the way

- `libclntsh` could not find `libnnz.so` from the Instant Client directory (`DPI-1047`) — it needs
  `LD_LIBRARY_PATH`; Debian 13 ships `libaio.so.1t64`, so a `libaio.so.1` symlink sits next to the client.
- GoldenGate REST through the ServiceManager port (9100) → `OGG-12031 resource does not exist`; the
  ServiceManager's own REST API told me the admin server port (9101, localhost only).
- First `C##MON` run: the change log cut `container = all` — only the display (sqlplus linesize 80); the
  statement was complete. Template sets `lines 400` now.
