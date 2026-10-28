#!/bin/bash
# Daily report: virtualenv with python-oracledb + ansible (for the vault), Instant Client for thick mode.
# Exit code = number of CRIT findings.
IC=${ORACLE_IC:-$HOME/opt/instantclient_23_26}
export LD_LIBRARY_PATH=$IC${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}   # libclntsh finds libnnz/libaio only this way
exec "${VENV:-$HOME/.venvs/dba}/bin/python" -I "$(dirname "$0")/daily_report.py" "$@"
