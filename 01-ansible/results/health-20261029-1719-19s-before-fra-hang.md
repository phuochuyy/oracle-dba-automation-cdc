# Lab health — 2026-10-29 17:19

| Host | DB | Role / open mode | Status | Lag (apply/transport s) | FRA % | FSFO | Wallet | Backup age h | Net encryption | Reasons |
|------|----|------------------|--------|-------------------------|-------|------|--------|--------------|----------------|---------|
| prm3 | orcl3 | PRIMARY / READ WRITE | **CRIT** | -1 / -1 | 64 | DISABLED observer= | NOT_AVAILABLE/UNKNOWN | 4.3 | not required | standby dest DEFERRED; no TDE (no encrypted tablespace); network encryption not required |
| stb3 | - | - | DOWN | - | - | - | - | - | - | host not reachable (VM off in this scenario) |
| prm1 | orcl | PRIMARY / READ WRITE | **OK** | -1 / -1 | 16 | SYNCHRONIZED observer=YES | OPEN/AUTOLOGIN | - | REQUIRED | - |
| prm2 | - | - | DOWN | - | - | - | - | - | - | host not reachable (VM off in this scenario) |
| stb1 | orcl_stb | PHYSICAL STANDBY / READ ONLY WITH APPLY | **OK** | 0 / 0 | 22 | SYNCHRONIZED observer=YES | OPEN/AUTOLOGIN | 4.1 | REQUIRED | - |
| stb2 | - | - | DOWN | - | - | - | - | - | - | host not reachable (VM off in this scenario) |

Thresholds: FRA 80/90 %, lag 300 s, backup 26 h,
failed logons 10/hour. -1 = not applicable (e.g. no lag on a primary).
