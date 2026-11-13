#!/bin/bash
# measure.py with the virtualenv and the Instant Client (thick mode: orcl requires native encryption)
export LD_LIBRARY_PATH=${ORACLE_IC:-$HOME/work/tools/instantclient_23_26}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
exec "${VENV:-$HOME/work/tools/venvs/dba}/bin/python" -I "$(dirname "$0")/measure.py" "$@"
