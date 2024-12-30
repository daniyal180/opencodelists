#!/bin/bash

set -euo pipefail

JOB_NAME="$1"

# no username if running inside container
if whoami;
then
    # running outside container
    BIN_PATH="/var/lib/dokku/data/storage/opencodelists/deploy/bin/"
    CRONSOURCE="${BIN_PATH}import_latest_${JOB_NAME}_cronfile"
    BIN_PATH+="import_latest_release.sh ${JOB_NAME}"
    SENTRY_DSN=$(dokku config:get opencodelists SENTRY_DSN)
else
    # running inside container
    BIN_PATH="/app/deploy/bin/backup.sh"
    CRONSOURCE="/app/app.json"
    # sentry_dsn env var is available inside container
fi

CRONTAB=$(grep -oP "([\*\d]+ )+" "$CRONSOURCE")

# modify the DSN to point it at the cron endpoint
ARR_DSN=("${SENTRY_DSN//\// }")
SENTRY_DSN="${SENTRY_DSN/"${ARR_DSN[-1]}"/"api/${ARR_DSN[-1]}"}"
SENTRY_CRONS="${SENTRY_DSN}/cron/${JOB_NAME}/"

function sentry_cron_start() {
curl -X POST "${SENTRY_CRONS}" \
    --header 'Content-Type: application/json' \
    --data-raw "{\"monitor_config\": {\"schedule\": {\"type\": \"crontab\", \"value\": \"$CRONTAB\"}}, \"status\": \"in_progress\"}"
}
function sentry_cron_ok() {
    curl "${SENTRY_CRONS}?status=ok"
}
function sentry_cron_error() {
    curl "${SENTRY_CRONS}?status=error"
}

sentry_cron_start
RESULT=0
$BIN_PATH || RESULT=$?;
if [ $RESULT == 0  ];
then
    sentry_cron_ok
else
    sentry_cron_error
fi
