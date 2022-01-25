import dateutil.parser

from fastapi import BackgroundTasks, FastAPI, Response
from typing import Any, Dict

from pdmodels.Models import PhysicalDevice, Location
import api.client.BrokerAPI as broker
import api.client.TTNAPI as ttn


app = FastAPI()

"""
POST /ttn/webhook HTTP/1.1
Host: 110.150.19.96:5688
User-Agent: TheThingsStack/3.17.0-SNAPSHOT-d76af1e33 (linux/amd64)
Content-Length: 580
Content-Type: application/json
X-Tts-Domain: au1.cloud.thethings.network
Accept-Encoding: gzip

{
    "end_device_ids": {
        "device_id":"atmega328-v1",
        "application_ids": {
            "application_id":"oai-test-devices"
        },
        "dev_eui":"70B3D57ED0044DE8",
        "join_eui":"0000000000000001"
    },
    "correlation_ids":["as:up:01FT4AHT6SRP56671NE45SSW0M","rpc:/ttn.lorawan.v3.AppAs/SimulateUplink:00f7e79c-8658-4ecc-877d-eb0fad6c0b31"],
    "received_at":"2022-01-23T20:37:58.107539052Z",
    "uplink_message": {
        "f_port":1,
        "frm_payload":"BQ==",
        "rx_metadata":[{"gateway_ids":{"gateway_id":"test"},"rssi":42,"channel_rssi":42,"snr":4.2}],
        "settings":{"data_rate":{"lora":{"bandwidth":125000,"spreading_factor":7}}}
    },
    "simulated":true
}
"""

JSONObject = Dict[str, Any]


@app.post("/ttn/webhook/{app_id}/up/{dev_id}")
async def webhook_endpoint(app_id: str, dev_id: str, msg: JSONObject, background_tasks: BackgroundTasks) -> None:
    """
    Receive webhook calls from TTN.
    """

    # Process the message later and return an empty response to TTN as soon as
    # possible to free up the resources there.
    background_tasks.add_task(process_message, app_id, dev_id, msg)

    # Doing an explicit return of a Response object with the 204 code to avoid
    # the default FastAPI behaviour of always sending a response body. Even if
    # a path method returns None, FastAPI will return a body containing "null"
    # or similar. TTN does nothing with the response, so there is no pointing
    # sending it one.
    return Response(status_code=204)


def process_message(app_id: str, dev_id: str, msg: JSONObject) -> None:
    #if 'simulated' in msg and msg['simulated']:
    #    print('Ignoring simulated message.')
    #    return

    last_seen = None

    if 'received_at' in msg:
        last_seen = dateutil.parser.isoparse(msg['received_at'])
    else:
        print('No received_at field in TTN message.')

    try:
        dev = broker.get_physical_device(app_id, dev_id)
        print(f'Found device: {dev}')

        if last_seen is not None:
            dev.last_seen = last_seen
            dev = broker.update_physical_device(dev)
            print(f'Updated device: {dev}')

    except:
        print('Device not found, creating physical device.')
        ttn_dev = ttn.get_device_details(app_id, dev_id)
        print(f'Device info from TTN: {ttn_dev}')

        dev_name = ttn_dev['name'] if 'name' in ttn_dev else dev_id
        dev_loc = Location.from_ttn_device(ttn_dev)
        props = {'app_id': app_id, 'dev_id': dev_id }

        dev = PhysicalDevice(source_name='ttn', name=dev_name, location=dev_loc, last_seen=last_seen, properties=props)
        broker.create_physical_device(dev)
