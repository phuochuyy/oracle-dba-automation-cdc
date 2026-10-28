#!/bin/bash
# Start/stop the CDC stack on the lab host (no containers, no sudo): Kafka 4.3 KRaft + Kafka Connect with
# the Debezium Oracle connector, from tarballs in ~/opt/cdc.
#   ./cdc.sh start | stop | status | register | delete
set -eu
D=${CDC_HOME:-$HOME/opt/cdc}
CFG=$(cd "$(dirname "$0")" && pwd)/config
export JAVA_HOME=$(ls -d $D/jdk-21*)
K=$(ls -d $D/kafka_2.13-*)
LOGS=$D/logs; mkdir -p $LOGS $D/data
case ${1:?mode} in
start)
  if [ ! -f $D/data/kafka/meta.properties ]; then
    $K/bin/kafka-storage.sh format --standalone -t "$($K/bin/kafka-storage.sh random-uuid)" -c $CFG/server.properties
  fi
  # idempotent: the restart test starts Connect again while Kafka keeps running. Small host: 512/768 MB heap
  if ! ss -ltn | grep -q '127.0.0.1\]*:9092 '; then
    KAFKA_HEAP_OPTS="-Xms256m -Xmx512m" LOG_DIR=$LOGS/kafka $K/bin/kafka-server-start.sh -daemon $CFG/server.properties
    for i in $(seq 1 30); do $K/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1 && break; sleep 2; done
  fi
  pgrep -f org.apache.kafka.connect.cli.ConnectDistributed >/dev/null ||
    KAFKA_HEAP_OPTS="-Xms256m -Xmx768m" LOG_DIR=$LOGS/connect $K/bin/connect-distributed.sh -daemon $CFG/connect-distributed.properties
  for i in $(seq 1 60); do curl -sf localhost:8083/ >/dev/null && break; sleep 2; done
  curl -s localhost:8083/ ; echo ;;
stop)
  pkill -f "org.apache.kafka.connect.cli.ConnectDistributed" || true
  sleep 5; $K/bin/kafka-server-stop.sh || true ;;
status)
  curl -s localhost:8083/connectors?expand=status | $HOME/.venvs/dba/bin/python -m json.tool ;;
register)
  curl -s -X PUT -H 'Content-Type: application/json' --data @$CFG/orcl3-connector.json localhost:8083/connectors/orcl3-cdc/config; echo ;;
delete)
  curl -s -X DELETE localhost:8083/connectors/orcl3-cdc; echo ;;
esac
