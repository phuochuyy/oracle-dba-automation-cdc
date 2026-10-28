-- One line per value: key|value. Runs in CDB$ROOT as SYSDBA on a primary or a (mounted/ADG) standby.
-- Every check is here because the problem happened in one of the labs (see the README).
set heading off feedback off pages 0 lines 400 trimspool on verify off
whenever sqlerror continue
select 'db_unique_name|' || db_unique_name from v$database;
select 'role|' || database_role from v$database;
select 'open_mode|' || open_mode from v$database;
select 'protection_mode|' || protection_mode from v$database;
select 'fsfo|' || fs_failover_status || ' observer=' || fs_failover_observer_present from v$database;
-- lag in seconds, only on a standby
select 'apply_lag_s|' || nvl(max(case when name = 'apply lag' then
         extract(day from to_dsinterval(value)) * 86400 + extract(hour from to_dsinterval(value)) * 3600
       + extract(minute from to_dsinterval(value)) * 60 + extract(second from to_dsinterval(value)) end), -1)
  from v$dataguard_stats where name = 'apply lag' and value is not null;
select 'transport_lag_s|' || nvl(max(
         extract(day from to_dsinterval(value)) * 86400 + extract(hour from to_dsinterval(value)) * 3600
       + extract(minute from to_dsinterval(value)) * 60 + extract(second from to_dsinterval(value))), -1)
  from v$dataguard_stats where name = 'transport lag' and value is not null;
-- primary: the standby destination
select 'standby_dest|' || nvl(max(status || decode(error, null, '', ' ' || error)), 'none')
  from v$archive_dest where dest_id > 1 and destination is not null and status <> 'INACTIVE' and target = 'STANDBY';
-- FRA: filled up twice on a standby in the performance lab
select 'fra_pct|' || nvl(round(max(space_used / nullif(space_limit, 0)) * 100), -1) from v$recovery_file_dest;
select 'ts_over_85|' || count(*) || ' ' || listagg(c.name || ':' || tablespace_name, ',') within group (order by 1)
  from cdb_tablespace_usage_metrics m join v$containers c on c.con_id = m.con_id where used_percent > 85;
select 'invalid_objects|' || count(*) from cdb_objects where status = 'INVALID';
-- TDE: a password-opened keystore on a standby broke the switchover in the security lab
select 'wallet|' || status || '/' || wallet_type from v$encryption_wallet where con_id = 1;
select 'encrypted_ts|' || count(*) from v$encrypted_tablespaces;
-- backups this database's control file knows about (RAC A backs up on the standby)
select 'backup_age_h|' || nvl(round((sysdate - max(end_time)) * 24, 1), -1)
  from v$rman_backup_job_details where status like 'COMPLETED%' and input_type in ('DB FULL', 'DB INCR');
-- last hour, not 24 h: the first run was dominated by failures from before the observer fix
select 'failed_logons_1h|' || count(*) from unified_audit_trail
 where action_name = 'LOGON' and return_code <> 0 and event_timestamp > systimestamp - interval '1' hour;
exit
