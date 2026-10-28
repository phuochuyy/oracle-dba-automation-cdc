-- The same table on the other side of the Active-Active pair (orcl / ORCLPDB2): GoldenGate replicates
-- the rows written at Region B here, which is how the GoldenGate latency is measured.
-- Run as SYSDBA on prm1:  sqlplus / as sysdba @02_target_table.sql
whenever sqlerror exit failure
alter session set container = orclpdb2;
create table app.cdc_events (
  site     varchar2(4)   not null,
  seq      number        not null,
  account  number(10)    not null,
  amount   number(18,2)  not null,
  note     varchar2(40),
  created  timestamp default systimestamp not null,
  constraint cdc_events_pk primary key (site, seq));
exec dbms_goldengate_adm.add_auto_cdr('APP', 'CDC_EVENTS')
exit
