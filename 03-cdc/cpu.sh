#!/bin/bash
# Busy CPU seconds of the whole prm3 VM so far (/proc/stat, USER_HZ=100). Run before and after a test.
# Not V$SESSTAT of the connector user: LogMiner's work runs in background MSnn processes, the connector's
# own sessions showed ~0 CPU (first attempt).
ssh -o BatchMode=yes oracle@prm3 "awk '/^cpu /{print (\$2+\$3+\$4+\$7+\$8+\$9)/100}' /proc/stat"
