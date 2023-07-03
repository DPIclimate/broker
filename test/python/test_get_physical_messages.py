import datetime as dt
import json
import logging

import dateutil.parser
import pytest
from fastapi.testclient import TestClient

import test_utils as tu
import api.client.DAO as dao
from pdmodels.Models import PhysicalDevice
from restapi.RestAPI import app

ts: dt.datetime = tu.now() - dt.timedelta(days=683.0)
interval = dt.timedelta(minutes=15.0)

timestamps = []
msgs = []
max_msgs = 65536

pd: PhysicalDevice = PhysicalDevice(source_name='wombat', name='dummy', source_ids={'x': 1})


@pytest.fixture(scope='module')
def create_user():
    user = tu.create_test_user()
    logging.info(f'{user.username}, {user.auth_token}')
    yield user
    dao.user_rm(user.username)


@pytest.fixture(scope='module')
def create_msgs():
    global interval, msgs, pd, timestamps, ts

    logging.info('Generating messages')

    pd = dao.create_physical_device(pd)

    with open('/tmp/msgs.json', 'w') as f:
        for i in range(0, max_msgs + 1):
            timestamps.append(ts)
            msg = {'ts': ts.isoformat(), 'i': i}
            msgs.append(msg)
            s = f'{pd.uid}\t{ts.isoformat()}\t{json.dumps(msg)}'
            print(s, file=f)
            ts = ts + interval

    with open('/tmp/msgs.json', 'r') as f:
        with dao.get_connection() as conn, conn.cursor() as cursor:
            cursor.copy_from(f, 'physical_timeseries', columns=('physical_uid', 'ts', 'json_msg'))
            conn.commit()

    logging.info('Finished generating messages')


@pytest.fixture(scope='module')
def test_client(create_user, create_msgs):
    client = TestClient(app)
    client.headers = {
        'Authorization': f'Bearer {create_user.auth_token}'
    }
    yield client


def test_no_params_no_msgs(test_client):
    no_msg_pd: PhysicalDevice = dao.create_physical_device(PhysicalDevice(source_name='wombat', name='dummy', source_ids={'x': 1}))
    response = test_client.get(f'/broker/api/physical/messages/{no_msg_pd.uid}')
    assert response.status_code == 200
    assert response.json() == []


def test_no_params(test_client):
    # Confirm the default count parameter value is correct, so 65536 of the 65537 messages are returned.
    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}')
    assert response.status_code == 200
    assert response.json() == msgs[:-1]


def test_no_params_ts(test_client):
    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}', params={'only_timestamp': 1})
    assert response.status_code == 200
    for a, b in zip(response.json(), timestamps):
        if a is None:
            break

        assert dateutil.parser.isoparse(a) == b


def test_count(test_client):
    # Confirm the count parameter works.
    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}', params={'count': 50})
    assert response.status_code == 200
    assert response.json() == msgs[:50]


def test_count_ts(test_client):
    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}', params={'count': 50, 'only_timestamp': 1})
    assert response.status_code == 200
    for a, b in zip(response.json(), timestamps):
        if a is None:
            break

        assert dateutil.parser.isoparse(a) == b


def test_start_after_end(test_client):
    start_ts = ts + interval

    # Confirm no messages returned when a start timestamp at or after the last message is used.
    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}', params={'start': start_ts})
    assert response.status_code == 200
    assert response.json() == []

    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}', params={'start': timestamps[max_msgs]})
    assert response.status_code == 200
    assert response.json() == []


def test_start_gives_gt(test_client):
    # Confirm start time parameter gets the next message greater than, not greater than equal to.
    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}', params={'start': timestamps[max_msgs - 1]})
    assert response.status_code == 200
    assert response.json() == [msgs[max_msgs]]


def test_invalid_count(test_client):
    # Check the invalid count values.
    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}', params={'count': -1})
    assert response.status_code == 422

    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}', params={'count': 0})
    assert response.status_code == 422

    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}', params={'count': 65537})
    assert response.status_code == 422


def test_end(test_client):
    # Test the end parameter
    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}', params={'end': timestamps[0] - interval})
    assert response.status_code == 200
    assert response.json() == []

    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}', params={'end': timestamps[0]})
    assert response.status_code == 200
    assert response.json() == [msgs[0]]

    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}', params={'end': timestamps[9]})
    assert response.status_code == 200
    assert response.json() == msgs[:10]


def test_start_end(test_client):
    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}', params={'start': timestamps[5], 'end': timestamps[9]})
    assert response.status_code == 200
    assert response.json() == msgs[6:10]


def test_invalid_start_end(test_client):
    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}', params={'start': timestamps[5], 'end': timestamps[5]})
    assert response.status_code == 422

    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}', params={'start': timestamps[5], 'end': timestamps[4]})
    assert response.status_code == 422


def test_invalid_count_end(test_client):
    response = test_client.get(f'/broker/api/physical/messages/{pd.uid}', params={'count': 1, 'end': timestamps[4]})
    assert response.status_code == 422
