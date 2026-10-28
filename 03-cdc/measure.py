#!/usr/bin/env python3
"""Debezium vs GoldenGate on the same source rows.

A writer inserts rows into orcl3 / GGREPL APP.CDC_EVENTS, one row per transaction, and notes the commit
time. Two readers note when each row shows up:
  - Debezium: the Kafka record timestamp (CreateTime, set when Kafka Connect produced the event)
  - GoldenGate: first time the row is seen on orcl / ORCLPDB2 (polled every 50 ms) — GG_B Extract ->
    distribution path -> GG_A Replicat
All times are the lab host's clock, so the VMs' clocks do not matter.

  latency  N rows at a steady rate, latency percentiles for both paths
  restart  the same while Kafka Connect is stopped (SIGTERM or SIGKILL) and started again mid-run:
           are events lost or duplicated?
usage: ./run.sh latency [rows] [rows_per_s] | restart [term|kill]
"""
import json
import os
import pathlib
import signal
import statistics
import subprocess
import sys
import threading
import time

import oracledb
import yaml

HERE = pathlib.Path(__file__).resolve().parent
CDC = pathlib.Path(os.environ.get("CDC_HOME", "~/opt/cdc")).expanduser()
KAFKA = next(CDC.glob("kafka_2.13-*"))
TOPIC = "orcl3.APP.CDC_EVENTS"
SRC = "192.168.106.10:1521/ggrepl.rac"
TGT = "192.168.104.10,192.168.104.11:1521/orclpdb2.rac"


def secrets():
    vault = HERE.parent / "01-ansible/group_vars/all/vault.yml"
    out = subprocess.run([str(pathlib.Path(sys.executable).parent / "ansible-vault"), "view",
                          "--vault-password-file", str(pathlib.Path("~/.vault_pass_dba").expanduser()), str(vault)],
                         check=True, capture_output=True, text=True).stdout
    return yaml.safe_load(out)["vault_user_passwords"]


class KafkaReader(threading.Thread):
    """kafka-console-consumer from the end of the topic; keeps every create event's SEQ and timestamp"""
    def __init__(self, lo, hi):
        super().__init__(daemon=True)
        self.lo, self.hi, self.seen = lo, hi, {}          # seq -> [kafka create times]
        env = dict(os.environ, JAVA_HOME=str(next(CDC.glob("jdk-21*"))), KAFKA_HEAP_OPTS="-Xmx256m")
        self.p = subprocess.Popen([str(KAFKA / "bin/kafka-console-consumer.sh"), "--bootstrap-server",
                                   "localhost:9092", "--topic", TOPIC, "--formatter-property", "print.timestamp=true"],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env)

    def run(self):
        for line in self.p.stdout:
            if "\t" not in line:
                continue
            ts, v = line.rstrip("\n").split("\t", 1)
            if v == "null":
                continue
            e = json.loads(v)
            if e["op"] != "c":
                continue
            seq = int(e["after"]["SEQ"])
            if self.lo <= seq < self.hi:
                self.seen.setdefault(seq, []).append(int(ts.split(":")[1]) / 1000)

    def stop(self):
        self.p.terminate()


class TargetPoller(threading.Thread):
    """first time each row is visible on the GoldenGate target"""
    def __init__(self, con, lo, hi):
        super().__init__(daemon=True)
        self.con, self.lo, self.hi, self.seen, self.done = con, lo, hi, {}, False

    def run(self):
        cur = self.con.cursor()
        while not self.done:
            now = time.time()
            cur.execute("select seq from app.cdc_events where site = 'B' and seq >= :1 and seq < :2", [self.lo, self.hi])
            for (s,) in cur:
                self.seen.setdefault(int(s), now)
            time.sleep(0.05)


def connect_worker(action):
    """stop/start Kafka Connect; returns the pid that was signalled"""
    if action in ("term", "kill"):
        pid = int(subprocess.run(["pgrep", "-f", "org.apache.kafka.connect.cli.ConnectDistributed"],
                                 capture_output=True, text=True).stdout.split()[0])
        os.kill(pid, signal.SIGTERM if action == "term" else signal.SIGKILL)
        return pid
    subprocess.run([str(HERE / "cdc.sh"), "start"], capture_output=True, text=True)


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "latency"
    rows = int(sys.argv[2]) if mode == "latency" and len(sys.argv) > 2 else 300
    rate = float(sys.argv[3]) if mode == "latency" and len(sys.argv) > 3 else 10.0
    action = sys.argv[2] if mode == "restart" and len(sys.argv) > 2 else "term"
    pw = secrets()
    oracledb.init_oracle_client(lib_dir=str(pathlib.Path("~/opt/instantclient_23_26").expanduser()))
    src = oracledb.connect(user="cdc_writer", password=pw["cdc_writer"], dsn=SRC)
    tgt = oracledb.connect(user="cdc_reader", password=pw["cdc_reader"], dsn=TGT)
    lo = int(time.time()) % 100000 * 1000            # this run's SEQ range
    hi = lo + rows
    kr, tp = KafkaReader(lo, hi), TargetPoller(tgt, lo, hi)
    kr.start(); tp.start()
    time.sleep(8)                                    # consumer joined, positioned at the end
    commit_t, events = {}, []
    cur = src.cursor()
    t0 = time.time()
    for i in range(rows):
        seq = lo + i
        cur.execute("insert into app.cdc_events (site, seq, account, amount, note) values ('B', :1, :2, :3, :4)",
                    [seq, 1000 + i % 50, round(10 + i * 0.5, 2), mode])
        src.commit()
        commit_t[seq] = time.time()
        if mode == "restart" and i == rows // 3:
            events.append(f"{time.time() - t0:5.1f} s  Kafka Connect {action.upper()} (pid {connect_worker(action)})")
        if mode == "restart" and i == 2 * rows // 3:
            events.append(f"{time.time() - t0:5.1f} s  Kafka Connect start")
            threading.Thread(target=connect_worker, args=("start",), daemon=True).start()
        time.sleep(max(0.0, t0 + (i + 1) / rate - time.time()))
    deadline = time.time() + (240 if mode == "restart" else 90)
    while time.time() < deadline and (len(kr.seen) < rows or len(tp.seen) < rows):
        time.sleep(1)
    tp.done = True
    kr.stop()
    dbz = [kr.seen[s][0] - commit_t[s] for s in kr.seen]
    gg = [tp.seen[s] - commit_t[s] for s in tp.seen]
    dup = {s: len(v) for s, v in kr.seen.items() if len(v) > 1}
    res = {"mode": mode, "action": action if mode == "restart" else None, "rows": rows, "rate_per_s": rate,
           "seq_range": [lo, hi], "events": events,
           "debezium": {"received": len(kr.seen), "missing": rows - len(kr.seen), "duplicated_rows": len(dup),
                        "extra_events": sum(v - 1 for v in dup.values())},
           "goldengate": {"received": len(tp.seen), "missing": rows - len(tp.seen)}}
    for name, xs in (("debezium", dbz), ("goldengate", gg)):
        if xs:
            res[name].update({f"p{p}_ms": round(pct(xs, p) * 1000) for p in (50, 95, 99)})
            res[name]["max_ms"] = round(max(xs) * 1000)
            res[name]["mean_ms"] = round(statistics.mean(xs) * 1000)
    out = HERE / "results" / (f"latency-{rows}x{rate:g}.json" if mode == "latency" else f"restart-{action}.json")
    out.write_text(json.dumps(res, indent=2) + "\n")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
