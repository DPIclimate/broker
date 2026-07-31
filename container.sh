#!/usr/bin/env bash
set -euo pipefail

readonly PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly ENV_FILE="${PROJECT_ROOT}/compose/.env"
readonly NETWORK="iota_net"
readonly DB_VOLUME="iota_db_data"
readonly MQ_VOLUME="iota_mq_data"
readonly PLATFORM="linux/arm64"
readonly POSTGIS_IMAGE="postgis/postgis:17-3.5"

readonly ALL_SERVICES=(
    db mq restapi website ttn_webhook ttn_processor ydoc wombat dragino_json
    lm delivery pollers frred axistech test_runner
)

usage() {
    echo "Usage: $0 {build|up|down|restart|logs|status} [profile ...]"
    echo
    echo "Profiles: ttn ydoc wombat dragino_json ubidots pollers frred"
}

require_container_system() {
    if ! container system status >/dev/null 2>&1; then
        echo "Apple Container is not running. Start it with: container system start" >&2
        exit 1
    fi
}

require_env_file() {
    if [[ ! -f "${ENV_FILE}" ]]; then
        echo "Missing ${ENV_FILE}. Create it before starting the containers." >&2
        exit 1
    fi
}

container_exists() {
    container list --all --quiet | grep -Fxq "$1"
}

network_exists() {
    container network list --quiet | grep -Fxq "${NETWORK}"
}

volume_exists() {
    container volume list --quiet | grep -Fxq "$1"
}

delete_containers() {
    local service
    for service in "${ALL_SERVICES[@]}"; do
        if container_exists "${service}"; then
            container delete --force "${service}"
        fi
    done
}

delete_ephemeral_resources() {
    local volume
    for volume in "${DB_VOLUME}" "${MQ_VOLUME}"; do
        if volume_exists "${volume}"; then
            container volume delete "${volume}"
        fi
    done

    if network_exists; then
        container network delete "${NETWORK}"
    fi
}

down() {
    delete_containers
    delete_ephemeral_resources
}

build_images() {
    container build --platform "${PLATFORM}" --tag broker/python-base \
        --file "${PROJECT_ROOT}/images/restapi/Dockerfile" "${PROJECT_ROOT}"
    container build --platform "${PLATFORM}" --tag broker/mgmt-app \
        --file "${PROJECT_ROOT}/src/www/Dockerfile" "${PROJECT_ROOT}"
}

common_args() {
    COMMON_ARGS=(
        --detach
        --env-file "${ENV_FILE}"
        --network "${NETWORK}"
        --platform "${PLATFORM}"
        --init
    )
}

run_db() {
    container run "${COMMON_ARGS[@]}" \
        --name db \
        --env PGDATA=/var/lib/postgresql/data/pgdata \
        --publish 127.0.0.1:5432:5432 \
        --volume "${DB_VOLUME}:/var/lib/postgresql/data" \
        --volume "${PROJECT_ROOT}/db/init.d:/docker-entrypoint-initdb.d" \
        --volume "${PROJECT_ROOT}/db/upgrade:/upgrade" \
        "${POSTGIS_IMAGE}"
}

run_mq() {
    container run "${COMMON_ARGS[@]}" \
        --name mq \
        --volume "${MQ_VOLUME}:/var/lib/rabbitmq/mnesia/rabbit@mq" \
        --volume "${PROJECT_ROOT}/config/rabbitmq:/etc/rabbitmq" \
        rabbitmq:3.9-management
}

wait_for_db() {
    local attempt
    for attempt in {1..30}; do
        if container exec --env-file "${ENV_FILE}" db \
            sh -c 'pg_isready -q -d "$PGDATABASE" -U "$PGUSER"'; then
            return
        fi
        sleep 2
    done
    echo "Database did not become ready." >&2
    return 1
}

wait_for_mq() {
    local attempt
    for attempt in {1..45}; do
        if container exec mq rabbitmq-diagnostics -q check_port_connectivity; then
            return
        fi
        sleep 2
    done
    echo "RabbitMQ did not become ready." >&2
    return 1
}

run_python_service() {
    local name="$1"
    local workdir="$2"
    local entrypoint="$3"
    shift 3

    container run "${COMMON_ARGS[@]}" \
        --name "${name}" \
        --workdir "${workdir}" \
        --volume "${PROJECT_ROOT}/src/python:/home/broker/python" \
        --entrypoint "${entrypoint}" \
        broker/python-base "$@"
}

run_restapi() {
    container run "${COMMON_ARGS[@]}" \
        --name restapi \
        --workdir /home/broker/python/restapi \
        --publish 127.0.0.1:5687:5687 \
        --volume "${PROJECT_ROOT}/src/python:/home/broker/python" \
        --entrypoint /home/broker/.local/bin/uvicorn \
        broker/python-base \
        --proxy-headers --host 0.0.0.0 --port 5687 RestAPI:app
}

run_website() {
    container run "${COMMON_ARGS[@]}" \
        --name website \
        --env PYTHONPATH=/app:/iota \
        --publish 127.0.0.1:5000:5000 \
        --volume "${PROJECT_ROOT}/src/www:/app" \
        --volume "${PROJECT_ROOT}/src/python:/iota" \
        broker/mgmt-app
}

run_test_runner() {
    container run "${COMMON_ARGS[@]}" \
        --name test_runner \
        --env PYTHONPATH=/home/broker/broker/src/python:/home/broker/broker/test/python \
        --workdir /home/broker/broker \
        --volume "${PROJECT_ROOT}:/home/broker/broker" \
        --entrypoint ./forever.sh \
        broker/python-base
}

run_profile() {
    case "$1" in
        ttn)
            run_python_service ttn_webhook /home/broker/python/ttn \
                /home/broker/.local/bin/uvicorn \
                --proxy-headers --host 0.0.0.0 --port 5688 WebHook:app
            run_python_service ttn_processor /home/broker/python/ttn python AllMsgsWriter.py
            ;;
        ydoc)
            run_python_service ydoc /home/broker/python python -m ydoc.YDOC
            ;;
        wombat)
            run_python_service wombat /home/broker/python python -m ydoc.Wombat
            ;;
        dragino_json)
            run_python_service dragino_json /home/broker/python python -m ydoc.Dragino_JSON
            ;;
        ubidots)
            run_python_service delivery /home/broker/python python -m delivery.UbidotsWriter
            ;;
        pollers)
            run_python_service pollers /home/broker/python python -m pollers.ICT_EagleIO
            ;;
        frred)
            if [[ -z "${DATABOLT_SHARED_DIR:-}" ]]; then
                echo "The frred profile requires DATABOLT_SHARED_DIR." >&2
                return 1
            fi
            container run "${COMMON_ARGS[@]}" \
                --name frred \
                --workdir /home/broker/python \
                --volume "${PROJECT_ROOT}/src/python:/home/broker/python" \
                --volume "${DATABOLT_SHARED_DIR}/nectar_raw_data:/raw_data" \
                --entrypoint python \
                broker/python-base -m delivery.FRRED
            run_python_service axistech /home/broker/python python -m pollers.axistech
            ;;
        *)
            echo "Unknown profile: $1" >&2
            usage >&2
            return 1
            ;;
    esac
}

up() {
    require_env_file
    down

    container network create "${NETWORK}"
    container volume create "${DB_VOLUME}"
    container volume create "${MQ_VOLUME}"
    common_args

    run_db
    run_mq
    wait_for_db
    wait_for_mq

    run_restapi
    run_website
    run_python_service lm /home/broker/python python -m logical_mapper.LogicalMapper
    run_test_runner

    local profile
    for profile in "$@"; do
        run_profile "${profile}"
    done

    container list
}

logs() {
    local service
    for service in "${ALL_SERVICES[@]}"; do
        if container_exists "${service}"; then
            echo "==> ${service} <=="
            container logs "${service}"
        fi
    done
}

main() {
    case "${1:-}" in
        build)
            require_container_system
            build_images
            ;;
        up)
            require_container_system
            shift
            up "$@"
            ;;
        down)
            require_container_system
            down
            ;;
        restart)
            require_container_system
            shift
            up "$@"
            ;;
        logs)
            require_container_system
            logs
            ;;
        status)
            require_container_system
            container list --all
            ;;
        *)
            usage >&2
            exit 2
            ;;
    esac
}

main "$@"
