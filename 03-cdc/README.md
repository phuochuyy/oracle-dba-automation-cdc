# C. CDC — Debezium next to GoldenGate, on the same source

**Source:** orcl3 / PDB GGREPL on prm3 — the PDB that GoldenGate GG_B already captures for the
Active-Active pair. **Debezium:** Oracle connector 3.7 (LogMiner adapter, no XStream/GoldenGate license)
in Kafka Connect, Kafka 4.3 in KRaft mode, all on the lab host from tarballs ([`cdc.sh`](cdc.sh), no
containers, no sudo). **GoldenGate:** GG_B Extract → distribution path → GG_A Replicat into orcl / ORCLPDB2.

## Setup

| Step | File | Notes |
|------|------|-------|
| captured table on both A-A sides (DDL is not replicated) | [`01_source_setup.sql`](01_source_setup.sql), [`02_target_table.sql`](02_target_table.sql) | supplemental logging ALL COLUMNS already there — GoldenGate's schema-level `ALLCOLS` covers new APP tables (`ORA-32588` on my first run) |
| connector user `C##DBZUSER` | same | **no `SELECT/FLASHBACK/LOCK ANY TABLE`** (the Debezium docs' example grants them): `SELECT, FLASHBACK` on the one table, LogMiner privileges, `V$` views. Worked — snapshot with `snapshot.locking.mode=none` |
| Kafka + Connect | [`config/`](config/) | one KRaft node (`controller.quorum.bootstrap.servers`, dynamic quorum), Connect distributed with one worker, JSON events without schemas, password through Kafka's `FileConfigProvider` from a file outside git |
| connector | [`config/orcl3-connector.json`](config/orcl3-connector.json) | `online_catalog` mining, `table.include.list=APP.CDC_EVENTS` |
| test users | [`../01-ansible/group_vars/all/users.yml`](../01-ansible/group_vars/all/users.yml) | `cdc_writer` (source) and `cdc_reader` (GG target) provisioned by the Ansible users-as-code role |

Events for one INSERT, UPDATE and DELETE ([`results/01-events.txt`](results/01-events.txt)): `op=c` (after
only), `op=u` (before 250.00 → after 300.00), `op=d` (before only), then a tombstone; each with SCN and
commit SCN.

## Latency — the same 300 rows, 10 per second, one row per transaction

[`measure.py`](measure.py) commits each row and notes the time; Debezium's latency is the Kafka record time
minus commit time, GoldenGate's the first time the row is visible on the target (polled every 50 ms). All
times from the host clock.

| Run | Debezium p50 / p95 / max (commit → Kafka) | GoldenGate p50 / p95 / max (commit → row in the other database) | lost |
|-----|------|------|------|
| default LogMiner polling ([json](results/latency-300x10-default.json)) | 2.36 / 3.75 / 4.24 s | 3.33 / 4.03 / 4.83 s | 0 / 0 |
| polling sleep 100–500 ms instead of up to 3 s ([json](results/latency-300x10-lowlatency.json)) | 2.40 / 3.75 / 4.25 s | 3.81 / 4.61 / 5.30 s | 0 / 0 |
| connector paused ([json](results/latency-300x10-paused.json)) | — | 3.07 / 4.28 / 4.63 s | — |

- Comparable but not equal paths: Debezium stops at Kafka, GoldenGate includes trail, network hop and the
  apply into a second database. Both ~2–4 s here on small VMs.
- **Shorter polling sleep changed nothing** (setting confirmed in the Connect log) → the sleep is not the
  bottleneck; each LogMiner round itself is. Next step would be the connector's JMX metrics
  (`LastDurationOfFetchQueryInMilliseconds`), not done.
- DB-side cost: **my first CPU measurement was wrong** — `V$SESSTAT` of the connector user showed ~0,
  because LogMiner works in background `MSnn` processes. Whole-VM busy CPU instead: 0.10–0.12 cores in
  every run, i.e. within noise at 10 rows/s.

## Restart — Kafka Connect stopped 10 s into a 30 s run, started at 20 s

| Stop | Debezium received / lost / **duplicates** | Debezium max | GoldenGate |
|------|-------------------------------------------|--------------|------------|
| `SIGTERM` (clean) ([json](results/restart-term.json)) | 300 / 0 / **0** | 21.6 s | 300, p95 4.76 s |
| `SIGKILL` (crash) ([json](results/restart-kill.json)) | 300 / 0 / **77** | 22.4 s | 300, p95 4.27 s |

No change lost either way (the offset is an SCN, LogMiner reads from there). After a crash Debezium
re-sends what it had produced since the last committed offset: **at-least-once** — consumers must be
idempotent (upsert by key; the primary key is the Kafka key). A clean stop commits the offset first.

## GoldenGate vs Debezium — what I would tell a team

| | GoldenGate 23ai | Debezium Oracle connector |
|-|-----------------|---------------------------|
| License | GoldenGate license (per core) | open source; LogMiner adapter needs no extra Oracle license (XStream adapter would) |
| Target | databases (Oracle and others), Kafka via GG for Big Data | Kafka topics (or Debezium Server sinks) |
| Delivery | exactly-once into a database (checkpoints + apply in transactions) | at-least-once (77 duplicates after a crash here) |
| Active-Active / CDR | built in (Auto-CDR, loop prevention with tags) | not its job |
| Operations in this lab | Microservices, deployments, XAG/HA, trail encryption, HANDLEDLFAILOVER with Data Guard | Kafka + Connect + one JSON config; offsets/history in Kafka topics |
| DB requirements | supplemental logging, integrated capture | supplemental logging (ALL columns), LogMiner privileges, flush table |
| Latency here | 3.1–3.8 s p50 to the other database | 2.4 s p50 to Kafka |

## Mistakes on the way

- `ORA-32588` on `ADD SUPPLEMENTAL LOG DATA (ALL)`: already set by GoldenGate; the step is conditional now.
- **Task FAILED although REST said RUNNING** right after registering: `ORA-01950 no quota on tablespace
  USERS` — the connector creates its flush table in the **PDB**; I had created the LogMiner tablespace in
  the root only. Tablespace + quota in GGREPL, dropped the misplaced flush table, restarted the task.
- Kafka 4: `controller.quorum.voters` is refused with `format --standalone`; console consumer wants
  `--formatter-property` (the old `--property` only printed a deprecation note and my parser failed on it).
- `archive.apache.org` unreachable from the host → Kafka 4.3.2 (same 4.3 line Debezium 3.7 is built on,
  4.3.1) from `dlcdn.apache.org`, checksum verified.

Clean-up: test rows deleted at the source and replicated (0 rows on both sides); table, users, connector
kept for a re-run. Stop the stack with `./cdc.sh stop` (Kafka + Connect use ~1.5 GB RAM).
