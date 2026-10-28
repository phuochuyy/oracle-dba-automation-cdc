#!/bin/bash
# measure.py with the virtualenv and the Instant Client (thick mode: orcl requires native encryption)
export LD_LIBRARY_PATH=${ORACLE_IC:-$HOME/opt/instantclient_23_26}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
exec "${VENV:-$HOME/.venvs/dba}/bin/python" -I "$(dirname "$0")/measure.py" "$@"
