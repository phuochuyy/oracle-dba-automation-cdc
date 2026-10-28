# A. Ansible — health check across the lab

Controller: the KVM host, `ansible-core` in a virtualenv (`~/.venvs/dba`, no system pip/sudo needed).
Inventory: the 8 VMs by region and role ([`inventory.ini`](inventory.ini)), host aliases and host keys from
`~/.ssh/config`. No secrets in the inventory. The lab never runs all 8 VMs (23 GB host), so hosts that are
off are reported as **DOWN**, not as failures.

```
cd 01-ansible && ansible-playbook playbooks/health.yml        # report in results/health-<time>.md
ansible-playbook playbooks/health.yml -e lag_crit_s=30         # thresholds from group_vars, overridable
```

## Health check — [`roles/oracle_health`](roles/oracle_health)

One SQL script ([`health.sql`](roles/oracle_health/files/health.sql)) prints `key|value` lines; the role turns
them into facts, rates each host **OK / WARN / CRIT** against [`group_vars/all/main.yml`](group_vars/all/main.yml),
and the controller writes one Markdown table. Every check is there because it went wrong in one of the labs:

| Check | Rule | Where it bit me |
|-------|------|-----------------|
| apply / transport lag (standby) | CRIT ≥ 300 s | ORA-28374 drill: apply stopped while FSFO said SYNCHRONIZED |
| standby destination (primary) | CRIT if not VALID | Region B transport off |
| FRA % | WARN 80, CRIT 90 | standby FRA full twice (performance lab) |
| TDE keystore | CRIT if encrypted tablespaces and not `OPEN/AUTOLOGIN`; WARN if no TDE | password-opened standby keystore broke a switchover |
| last backup (hosts that hold the backup records) | CRIT > 26 h | RAC backups run on the standby |
| server requires network encryption | WARN if not | security lab |
| tablespaces > 85 %, invalid objects, failed logons per hour | WARN | observer failed-logon storm |

## Results

**Normal run** — [`results/health-20261028-2255.md`](results/health-20261028-2255.md):

| Host | Status | Why |
|------|--------|-----|
| prm1, stb1 (RAC A primary + standby) | OK | lag 0, FSFO synchronized, keystore auto-login, encryption required |
| prm3 (orcl3) | **CRIT** | standby destination `DEFERRED` — true: Region B runs without its standby in this scenario. Also WARN: **no TDE and no network encryption** (Region B was never hardened, the security lab ran on Region A), and **7 invalid procedures** `BANK.WL_*` left in PDB PERF by the tuning lab |
| prm2, stb2, stb3 | DOWN | VMs off |

**Drill** — apply stopped on the standby for ~1 min, run with `-e lag_crit_s=30`
([`results/health-drill-apply-off.md`](results/health-drill-apply-off.md)):
stb1 **CRIT, apply lag 68 s**, open mode `READ ONLY` (no `WITH APPLY`) — while FSFO still said
`SYNCHRONIZED` and transport lag was 0. Back to lag 0 after `APPLY-ON`
([`results/health-20261028-2259.md`](results/health-20261028-2259.md); its WARN is 11 failed logons in the
hour: the open ORA-01017 finding of the security lab).

## Patch inventory — [`playbooks/patches.yml`](playbooks/patches.yml)

Reads every home from the central inventory (`inventory.xml`), checks it exists, and runs
`opatch lspatches` as the user that owns `OPatch` (a second play connects as `grid` for the grid homes).
Result ([`results/`](results/), `patches-*.md`):

- database, grid and client homes on all running hosts: **RU 23.26.1** (`38743669`, OCW `38743688`); grid
  homes also ACFS/RHP/Micronaut updates — **no drift** between hosts
- GoldenGate homes: no OPatch patches (GoldenGate 23ai MA is upgraded by installing a new home)
- **prm1: two stale inventory entries** — `/u01/app/oracle/goldengate` and `/u02/ogg_shared/gg_software`
  are registered but no longer on disk (old GoldenGate installs). Left as they are; cleanup is
  `runInstaller -detachHome ORACLE_HOME=<path>` as the inventory owner, after checking nothing uses them.

## Mistakes on the way

- First run counted failed logons over 24 h: 488–1,034 per host, nearly all from before the observer fix
  (security lab). Changed to the last hour.
- First rule made a missing keystore CRIT on a database without TDE (prm3). Now CRIT only with encrypted
  tablespaces; no TDE is a WARN.
- Hosts that were off ended as `failed=1` — the role now pings first and ends the host.
- **`-e lag_crit_s=30` crashed the evaluation** (`'>=' not supported between float and str`): values from
  the command line are strings. And my first "drill report" was the previous normal report, picked by
  `ls -t` after the failed run — caught because it showed lag 0 and the 300 s threshold. Thresholds are cast
  now, and the drill file is only saved if it shows the drill threshold.
- Patch inventory, first run: the grid homes showed "owned by root" (the top directory of a grid home
  belongs to root — the owner of `OPatch/opatch` is what counts), and the grid play overwrote the oracle
  play's fact on the same host. Owner from the opatch binary now, one fact per user, merged in the report.
- Side effect: the run at 22:19 lined up with the security lab's open ORA-01017 finding — bisected my SQL
  (not the cause) and found the failures come with standby→primary connection bursts; written up there.
