#!/bin/bash
# Daily report: virtualenv with python-oracledb + ansible (for the vault), Instant Client for thick mode.
# Exit code = number of CRIT findings.
IC=${ORACLE_IC:-$HOME/work/tools/instantclient_23_26}
export LD_LIBRARY_PATH=$IC${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}   # libclntsh finds libnnz/libaio only this way
exec "${VENV:-$HOME/work/tools/venvs/dba}/bin/python" -I "$(dirname "$0")/daily_report.py" "$@"
