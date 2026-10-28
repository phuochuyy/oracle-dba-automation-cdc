#!/usr/bin/env python3
"""Daily DBA report for the lab: Data Guard / FSFO, FRA, backups, failed logons, TDE, network encryption
for every database, and GoldenGate process status. Writes reports/report-<time>.md and .html.
Exit code = number of CRIT findings (for cron/systemd).

Passwords come from the Ansible Vault of 01-ansible (one secret store for the whole repo).
Thick mode (Oracle Instant Client): thin mode cannot talk to orcl, which requires native network
encryption since the security lab (DPY-3001).

usage: ./run_report.sh            (sets LD_LIBRARY_PATH and the virtualenv)
"""
import datetime as dt
import html
import os
import pathlib
import subprocess
import sys

import oracledb
import yaml

HERE = pathlib.Path(__file__).resolve().parent
VAULT = HERE.parent / "01-ansible/group_vars/all/vault.yml"
VAULT_PASS = pathlib.Path(os.environ.get("VAULT_PASS_FILE", "~/.vault_pass_dba")).expanduser()
IC = pathlib.Path(os.environ.get("ORACLE_IC", "~/opt/instantclient_23_26")).expanduser()

DB_SQL = {
    "db": "select db_unique_name, database_role, open_mode, protection_mode, fs_failover_status, "
          "fs_failover_current_target, fs_failover_observer_host from v$database",
    "lag": "select name, value from v$dataguard_stats where name in ('apply lag', 'transport lag')",
    "dest": "select nvl(max(status || decode(error, null, '', ' ' || error)), 'none') from v$archive_dest "
            "where dest_id > 1 and destination is not null and status <> 'INACTIVE' and target = 'STANDBY'",
    "fra": "select round(space_used / nullif(space_limit, 0) * 100) from v$recovery_file_dest",
    "backup": "select round((sysdate - max(end_time)) * 24, 1) from v$rman_backup_job_details "
              "where status like 'COMPLETED%' and input_type in ('DB FULL', 'DB INCR')",
    "wallet": "select status || '/' || wallet_type from v$encryption_wallet where con_id = 1",
    "enc_ts": "select count(*) from v$encrypted_tablespaces",
    "ts85": "select listagg(c.name || ':' || tablespace_name || ' ' || round(used_percent) || '%', ', ') "
            "within group (order by used_percent desc) from cdb_tablespace_usage_metrics m "
            "join v$containers c on c.con_id = m.con_id where used_percent > 85",
    "invalid": "select count(*) from cdb_objects where status = 'INVALID'",
    "failed_1h": "select count(*) from unified_audit_trail where action_name = 'LOGON' and return_code <> 0 "
                 "and event_timestamp > systimestamp - interval '1' hour",
    "failed_top": "select * from (select return_code || ' ' || nvl(dbusername, '(empty)') || ' from ' || "
                  "nvl(userhost, '?') || ': ' || count(*) from unified_audit_trail where action_name = 'LOGON' "
                  "and return_code <> 0 and event_timestamp > systimestamp - interval '1' day "
                  "group by return_code, dbusername, userhost order by count(*) desc) where rownum <= 3",
    # this very session: is it encrypted? (the report's own connection is a sample of what clients get)
    "net": "select count(*) from v$session_connect_info where sid = sys_context('userenv', 'sid') "
           "and network_service_banner like 'AES256 Encryption service adapter%'",
}


def vault():
    out = subprocess.run([str(pathlib.Path(sys.executable).parent / "ansible-vault"), "view",
                          "--vault-password-file", str(VAULT_PASS), str(VAULT)],
                         check=True, capture_output=True, text=True).stdout
    return yaml.safe_load(out)


def interval_s(v):
    """'+00 00:01:08' -> 68.0"""
    if not v:
        return None
    d, t = v.lstrip("+").split(" ")
    h, m, s = t.split(":")
    return int(d) * 86400 + int(h) * 3600 + int(m) * 60 + float(s)


def check_db(t, password, th):
    r = {"name": t["name"], "region": t["region"], "crit": [], "warn": []}
    try:
        con = oracledb.connect(user="c##mon", password=password, dsn=t["dsn"])
    except oracledb.Error as e:
        r["down"] = str(e).splitlines()[0][:90]
        return r
    with con:
        cur = con.cursor()
        one = lambda q: (cur.execute(q).fetchone() or [None])[0]
        (r["unique"], r["role"], r["open_mode"], r["prot"], r["fsfo"], r["fsfo_target"],
         r["observer"]) = cur.execute(DB_SQL["db"]).fetchone()
        lags = {n: interval_s(v) for n, v in cur.execute(DB_SQL["lag"]).fetchall()}
        r["apply_lag"], r["transport_lag"] = lags.get("apply lag"), lags.get("transport lag")
        for k in ("dest", "fra", "backup", "wallet", "enc_ts", "ts85", "invalid", "failed_1h", "net"):
            r[k] = one(DB_SQL[k])
        r["failed_top"] = [x[0] for x in cur.execute(DB_SQL["failed_top"]).fetchall()]
    standby = "STANDBY" in r["role"]
    lag = max(x for x in (r["apply_lag"], r["transport_lag"], -1) if x is not None)
    if r["fra"] is not None and r["fra"] >= th["fra_crit_pct"]:
        r["crit"].append(f"FRA {r['fra']} %")
    elif r["fra"] is not None and r["fra"] >= th["fra_warn_pct"]:
        r["warn"].append(f"FRA {r['fra']} %")
    if standby and lag >= th["lag_crit_s"]:
        r["crit"].append(f"lag {lag:.0f} s")
    if not standby and r["dest"] not in ("none", "VALID"):
        r["crit"].append(f"standby destination {r['dest']}")
    if r["enc_ts"] and not str(r["wallet"]).startswith("OPEN/AUTOLOGIN"):
        r["crit"].append(f"keystore {r['wallet']} with {r['enc_ts']} encrypted tablespaces")
    if not r["enc_ts"]:
        r["warn"].append("no TDE")
    if t["backups_here"] and (r["backup"] is None or r["backup"] > th["backup_max_h"]):
        r["crit"].append(f"last backup {r['backup']} h ago")
    if r["ts85"]:
        r["warn"].append(f"tablespaces > 85 %: {r['ts85']}")
    if r["invalid"]:
        r["warn"].append(f"{r['invalid']} invalid objects")
    if r["failed_1h"] > th["failed_logons_warn"]:
        r["warn"].append(f"{r['failed_1h']} failed logons in 1 h")
    if not r["net"]:
        r["warn"].append("connection not encrypted")
    return r


def check_gg(g, password):
    """status of every Extract/Replicat of a deployment, from the node where it runs"""
    # the password goes over SSH on stdin into a private temp file used as curl config (-K): never on a
    # command line, so not visible in ps on the node
    cfg = f'user = "oggadmin:{password}"\n'
    for node in g["nodes"]:
        remote = ("umask 077; f=$(mktemp); cat > $f; "
                  "for t in extracts replicats; do for n in $(curl -s -K $f "
                  "http://127.0.0.1:9101/services/v2/$t | python3 -c 'import sys,json; "
                  "[print(i[\"name\"]) for i in json.load(sys.stdin)[\"response\"][\"items\"]]'); do "
                  "printf '%s %s ' $t $n; curl -s -K $f http://127.0.0.1:9101/services/v2/$t/$n/info/status; "
                  "echo; done; done; rm -f $f")
        p = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3", f"oracle@{node}", remote],
                           input=cfg, capture_output=True, text=True, timeout=60)
        rows = []
        for line in p.stdout.splitlines():
            kind, name, js = line.split(" ", 2)
            try:
                s = yaml.safe_load(js)["response"]
            except Exception:
                continue
            rows.append({"type": kind[:-1], "name": name, "status": s.get("status"), "lag": s.get("lag")})
        if rows:
            return {"deployment": g["deployment"], "node": node, "processes": rows}
    return {"deployment": g["deployment"], "node": None, "processes": []}


def fmt(v, unit=""):
    return "-" if v is None else f"{v}{unit}"


def render(dbs, ggs, th, now):
    crit = sum(len(d["crit"]) for d in dbs) + sum(
        1 for g in ggs for p in g["processes"] if p["status"] != "running") + sum(1 for g in ggs if not g["node"])
    md = [f"# Lab daily report — {now:%Y-%m-%d %H:%M}", "",
          f"**{crit} CRIT**, {sum(len(d['warn']) for d in dbs)} WARN. Thresholds: FRA {th['fra_warn_pct']}/"
          f"{th['fra_crit_pct']} %, lag {th['lag_crit_s']} s, backup {th['backup_max_h']} h, failed logons "
          f"{th['failed_logons_warn']}/h (from 01-ansible).", "", "## Databases", "",
          "| DB | Region | Role / open mode | FSFO (target, observer) | Lag apply/transport s | FRA % | "
          "Backup age h | Keystore | Encrypted conn | Status |",
          "|----|--------|------------------|-------------------------|------------------------|-------|"
          "--------------|----------|----------------|--------|"]
    for d in dbs:
        if "down" in d:
            md.append(f"| {d['name']} | {d['region']} | **DOWN** | - | - | - | - | - | - | {d['down']} |")
            continue
        st = "CRIT" if d["crit"] else ("WARN" if d["warn"] else "OK")
        md.append(f"| {d['unique']} | {d['region']} | {d['role']} / {d['open_mode']} | {d['fsfo']} "
                  f"({fmt(d['fsfo_target'])}, {fmt(d['observer'])}) | {fmt(d['apply_lag'])} / "
                  f"{fmt(d['transport_lag'])} | {fmt(d['fra'])} | {fmt(d['backup'])} | {d['wallet']} | "
                  f"{'AES256' if d['net'] else 'no'} | **{st}** |")
    md += ["", "## Findings", ""]
    for d in dbs:
        for lvl in ("crit", "warn"):
            for f in d.get(lvl, []):
                md.append(f"- **{lvl.upper()}** {d.get('unique', d['name'])}: {f}")
    md += ["", "## Failed logons, last 24 h (top sources)", ""]
    for d in dbs:
        if d.get("failed_top"):
            md.append(f"- {d['unique']}: " + "; ".join(d["failed_top"]))
    md += ["", "## GoldenGate", "", "| Deployment | Node | Process | Status | Lag s |",
           "|------------|------|---------|--------|-------|"]
    for g in ggs:
        if not g["node"]:
            md.append(f"| {g['deployment']} | - | - | **not running on any node** | - |")
        for p in g["processes"]:
            md.append(f"| {g['deployment']} | {g['node']} | {p['type']} {p['name']} | "
                      f"{p['status'] if p['status'] == 'running' else '**' + str(p['status']) + '**'} | {fmt(p['lag'])} |")
    return "\n".join(md) + "\n", crit


def to_html(md):
    """small Markdown subset (headings, tables, bullets, bold) -> one self-contained HTML page"""
    out, in_table = [], False
    for line in md.splitlines():
        esc = html.escape(line)
        esc = __import__("re").sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc)
        if line.startswith("|"):
            cells = [c.strip() for c in esc.strip("|").split("|")]
            if set(line) <= set("|- "):
                continue
            tag = "th" if not in_table else "td"
            if not in_table:
                out.append("<table>")
                in_table = True
            out.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
        if line.startswith("# "):
            out.append(f"<h1>{esc[2:]}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{esc[3:]}</h2>")
        elif line.startswith("- "):
            out.append(f"<li>{esc[2:]}</li>")
        elif line:
            out.append(f"<p>{esc}</p>")
    if in_table:
        out.append("</table>")
    css = ("body{font-family:sans-serif;margin:24px;color:#222}table{border-collapse:collapse;margin:8px 0}"
           "td,th{border:1px solid #ccc;padding:4px 8px;font-size:13px}th{background:#f2f2f2}")
    return f"<!doctype html><meta charset='utf-8'><title>Lab daily report</title><style>{css}</style>" + "\n".join(out)


def main():
    cfg = yaml.safe_load((HERE / "targets.yml").read_text())
    th = yaml.safe_load((HERE / cfg["thresholds"]).read_text())
    secrets = vault()
    oracledb.init_oracle_client(lib_dir=str(IC))
    now = dt.datetime.now()
    dbs = [check_db(t, secrets["vault_user_passwords"]["c##mon"], th) for t in cfg["databases"]]
    ggs = [check_gg(g, secrets["vault_ogg_admin_password"]) for g in cfg["goldengate"]]
    md, crit = render(dbs, ggs, th, now)
    out = HERE / "reports" / f"report-{now:%Y%m%d-%H%M}"
    out.with_suffix(".md").write_text(md)
    out.with_suffix(".html").write_text(to_html(md))
    print(md)
    print(f"written: {out}.md / .html")
    return crit


if __name__ == "__main__":
    sys.exit(main())
