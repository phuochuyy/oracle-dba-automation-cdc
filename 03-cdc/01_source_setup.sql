-- Debezium (LogMiner adapter) source on orcl3, PDB GGREPL — the same PDB GoldenGate GG_B captures,
-- so both CDC tools read the same changes. Run as SYSDBA in CDB$ROOT:
--   sqlplus / as sysdba @01_source_setup.sql "<c##dbzuser password>"
-- Least privilege: the Debezium docs grant SELECT/FLASHBACK/LOCK ANY TABLE; here only the captured table
-- gets object grants (the security lab's assessment flags ANY privileges).
whenever sqlerror exit failure
set echo on verify off
define pw = "&1"

-- 1. the captured table, on THIS side of the Active-Active pair (DDL is not replicated by GoldenGate:
--    the same table is created on orcl/ORCLPDB2 by 02_target_table.sql)
alter session set container = ggrepl;
create table app.cdc_events (
  site     varchar2(4)   not null,
  seq      number        not null,
  account  number(10)    not null,
  amount   number(18,2)  not null,
  note     varchar2(40),
  created  timestamp default systimestamp not null,
  constraint cdc_events_pk primary key (site, seq));
exec dbms_goldengate_adm.add_auto_cdr('APP', 'CDC_EVENTS')
-- Debezium needs before images of all columns for UPDATE/DELETE events. First run: ORA-32588 "already
-- exists" — GoldenGate's schema-level supplemental logging (ADD SCHEMATRANDATA ... ALLCOLS) covers new
-- APP tables already. Added only if missing:
declare n number;
begin
  select count(*) into n from dba_log_groups
   where owner = 'APP' and table_name = 'CDC_EVENTS' and log_group_type = 'ALL COLUMN LOGGING';
  if n = 0 then execute immediate 'alter table app.cdc_events add supplemental log data (all) columns'; end if;
end;
/

-- 2. a small tablespace for the connector's flush table (LOG_MINING_FLUSH), in the root
alter session set container = cdb$root;
create tablespace logminer_tbs datafile '/u02/oradata/ORCL3/logminer_tbs01.dbf' size 50m autoextend on next 10m maxsize 500m;

-- 3. the connector user: common, no ANY privileges on data
create user c##dbzuser identified by "&pw" container = all;
alter user c##dbzuser default tablespace logminer_tbs quota unlimited on logminer_tbs container = current;
grant create session, set container, logmining, select any transaction, create table, create sequence
  to c##dbzuser container = all;
grant select_catalog_role, execute_catalog_role to c##dbzuser container = all;
grant execute on sys.dbms_logmnr to c##dbzuser container = all;
grant execute on sys.dbms_logmnr_d to c##dbzuser container = all;
grant select on sys.v_$database to c##dbzuser container = all;
grant select on sys.v_$log to c##dbzuser container = all;
grant select on sys.v_$log_history to c##dbzuser container = all;
grant select on sys.v_$logmnr_logs to c##dbzuser container = all;
grant select on sys.v_$logmnr_contents to c##dbzuser container = all;
grant select on sys.v_$logmnr_parameters to c##dbzuser container = all;
grant select on sys.v_$logfile to c##dbzuser container = all;
grant select on sys.v_$archived_log to c##dbzuser container = all;
grant select on sys.v_$archive_dest_status to c##dbzuser container = all;
grant select on sys.v_$transaction to c##dbzuser container = all;
grant select on sys.v_$mystat to c##dbzuser container = all;
grant select on sys.v_$statname to c##dbzuser container = all;
-- only the captured table: SELECT for the snapshot, FLASHBACK for the consistent (AS OF SCN) snapshot read
alter session set container = ggrepl;
-- the connector creates its flush table LOG_MINING_FLUSH in the PDB, not in the root: first run failed with
-- ORA-01950 (no quota on USERS in GGREPL) — the same small tablespace is needed here
create tablespace logminer_tbs datafile '/u02/oradata/ORCL3/ggrepl_logminer_tbs01.dbf' size 20m autoextend on next 10m maxsize 200m;
alter user c##dbzuser default tablespace logminer_tbs quota unlimited on logminer_tbs;
grant select, flashback on app.cdc_events to c##dbzuser;
exit
