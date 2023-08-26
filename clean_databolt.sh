#!/usr/bin/env bash
set -euo pipefail

BROKER_ROOT=$(cd $(dirname $0); pwd)
cd $BROKER_ROOT

eval "$(grep DATABOLT_SHARED_DIR compose/.env)"

if [ ! -d "$DATABOLT_SHARED_DIR" ]; then
	log "Databolt shared directory does not exist: [$DATABOLT_SHARED_DIR]"
	exit 1
fi

RAW_DATA=$DATABOLT_SHARED_DIR/raw_data

if [ ! -d "$RAW_DATA" ]; then
	log "Databolt raw data directory does not exist: [$RAW_DATA]"
	exit 1
fi

log() {
	echo $(date -Iseconds) $*
}

log ============================================================================== 
log Starting
log ============================================================================== 

for a in $(find "$RAW_DATA" -name \*.json); do
	F_NAME=$(basename "$a")
	FQ_D_NAME=$(dirname "$a")
	UUID=$(basename $(dirname "$a"))

	COMPLETED_FILE=$FQ_D_NAME/databolt-collected.txt

	if [ -f "$COMPLETED_FILE" ]; then
		log Cleaning $a
		rm -rf "$FQ_D_NAME"
	else
		log $a not processed yet
	fi
done

log done
