import datetime as dt
import json
import logging

import dateutil.parser
import pytest
from fastapi.testclient import TestClient

import BrokerConstants
import test_utils as tu
import api.client.DAO as dao
from pdmodels.Models import PhysicalDevice
from restapi.RestAPI import app

ts: dt.datetime = dateutil.parser.isoparse('2024-05-10T23:00:00Z')
latest_ts = ts
earliest_ts = ts

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
    global interval, msgs, pd, timestamps, ts, earliest_ts

    logging.info('Generating messages')

    pd = dao.create_physical_device(pd)

    with open('/tmp/msgs.json', 'w') as f:
        for i in range(0, max_msgs + 1):
            timestamps.append(ts)
            msg = {BrokerConstants.TIMESTAMP_KEY: ts.isoformat(), 'i': i}
            msgs.append(msg)
            s = f'{pd.uid}\t{ts.isoformat()}\t{json.dumps(msg)}'
            print(s, file=f)
            ts = ts - interval
            earliest_ts = ts

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


def _test_id_and_ts(response_msg, msgs_msg) -> None:
    """
    The change to the DAO that returns message timestamps in UTC causes the messages to be returned to be
    different from the messages used to generate them - there is a new utc_ts column. This means the returned
    messages cannot be directly compared to the dicts used to create them as used to be done by these tests.

    This function compares the important parts of the messages created by these tests to ensure they're
    correct.
    """
    assert response_msg['i'] == msgs_msg['i']
    assert dateutil.parser.isoparse(response_msg['ts_utc']) == dateutil.parser.isoparse(msgs_msg[BrokerConstants.TIMESTAMP_KEY])


def test_no_params_no_msgs(test_client):
    response = test_client.get(f'/broker/api/messages/')
    assert response.status_code == 404


def test_no_params(test_client):
    # Confirm the default count parameter value is correct, so 65536 of the 65537 messages are returned.
    response = test_client.get(f'/broker/api/messages', params={'p_uid': pd.uid})
    assert response.status_code == 200
    for a, b in zip(response.json(), msgs[:-1]):
        _test_id_and_ts(a, b)


def test_no_params_ts(test_client):
    response = test_client.get(f'/broker/api/messages', params={'p_uid': pd.uid, 'only_timestamp': 1})
    assert response.status_code == 200

    for a, b in zip(response.json(), timestamps):
        if a is None:
            break

        assert dateutil.parser.isoparse(a['ts_utc']) == b


def test_count(test_client):
    # Confirm the count parameter works.
    response = test_client.get(f'/broker/api/messages/', params={'p_uid': pd.uid, 'count': 50})
    assert response.status_code == 200
    #assert response.json() == msgs[:50]
    for a, b in zip(response.json(), msgs[:50]):
        _test_id_and_ts(a, b)


def test_count_ts(test_client):
    response = test_client.get(f'/broker/api/messages', params={'p_uid': pd.uid, 'count': 50, 'only_timestamp': 1})
    assert response.status_code == 200
    for a, b in zip(response.json(), timestamps):
        if a is None:
            break

        assert dateutil.parser.isoparse(a['ts_utc']) == b


def test_start_after_end(test_client):
    # Confirm no messages returned when a start timestamp at or after the last message is used.
    response = test_client.get(f'/broker/api/messages', params={'p_uid': pd.uid, 'start': latest_ts})
    assert response.status_code == 200
    assert response.json() == []

    response = test_client.get(f'/broker/api/messages', params={'p_uid': pd.uid, 'start': timestamps[0]})
    assert response.status_code == 200
    assert response.json() == []


def test_start_gives_gt(test_client):
    # Confirm start time parameter gets the next message greater than, not greater than equal to.
    response = test_client.get(f'/broker/api/messages', params={'p_uid': pd.uid, 'start': timestamps[1]})
    assert response.status_code == 200

    assert dateutil.parser.isoparse(response.json()[0]['ts_utc']) > timestamps[1]


def test_invalid_count(test_client):
    # Check the invalid count values.
    response = test_client.get(f'/broker/api/messages', params={'p_uid': pd.uid, 'count': -1})
    assert response.status_code == 422

    response = test_client.get(f'/broker/api/messages', params={'p_uid': pd.uid, 'count': 0})
    assert response.status_code == 422

    response = test_client.get(f'/broker/api/messages', params={'p_uid': pd.uid, 'count': 65537})
    assert response.status_code == 422


def test_end(test_client):
    # Test the end parameter
    response = test_client.get(f'/broker/api/messages', params={'p_uid': pd.uid, 'end': earliest_ts})
    assert response.status_code == 200
    assert response.json() == []

    response = test_client.get(f'/broker/api/messages', params={'p_uid': pd.uid, 'end': timestamps[-1]})
    assert response.status_code == 200
    _test_id_and_ts(response.json()[0], msgs[-1])

    response = test_client.get(f'/broker/api/messages', params={'p_uid': pd.uid, 'end': timestamps[-9]})
    assert response.status_code == 200
    for a, b in zip(response.json(), msgs[-9:]):
        _test_id_and_ts(a, b)


def test_start_end(test_client):
    response = test_client.get(f'/broker/api/messages/', params={'p_uid': pd.uid, 'start': timestamps[9], 'end': timestamps[5]})
    assert response.status_code == 200
    for a, b in zip(response.json(), msgs[5:9]):
        _test_id_and_ts(a, b)


def test_invalid_start_end(test_client):
    response = test_client.get(f'/broker/api/messages/', params={'p_uid': pd.uid, 'start': timestamps[5], 'end': timestamps[5]})
    assert response.status_code == 422

    response = test_client.get(f'/broker/api/messages/', params={'p_uid': pd.uid, 'start': timestamps[4], 'end': timestamps[5]})
    assert response.status_code == 422


def test_invalid_count_end(test_client):
    response = test_client.get(f'/broker/api/messages/', params={'p_uid': pd.uid, 'count': 1, 'end': timestamps[4]})
    assert response.status_code == 422
