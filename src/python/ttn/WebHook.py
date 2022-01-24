from fastapi import FastAPI, Query, HTTPException, Response, status
from pydantic import BaseModel
from typing import Any, Dict

from pdmodels.Models import PhysicalDevice, Location
import BrokerAPI as broker
import TTNAPI as ttn

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
        "join_eui":"0000000000000001"},
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


@app.post("/ttn/webhook", status_code=204)
async def webhook_endpoint(msg: JSONObject) -> None:
    """
    Receive webhook calls from TTN.
    """

    ids = msg['end_device_ids']
    dev_id = ids['device_id']
    app_id = ids['application_ids']['application_id']

    print(f'Received webhook call from {app_id} / {dev_id}')

    if 'simulated' in msg and msg['simulated']:
        print('Ignoring simulated message.')

    try:
        dev = broker.get_physical_device(app_id, dev_id)
        print(f'Found device: {dev}')
    except:
        print('Device not found, creating physical device.')
        ttn_dev = ttn.get_device_details(app_id, dev_id)
        print(f'Device info from TTN: {ttn_dev}')

        dev_name = ttn_dev['name'] if 'name' in ttn_dev else dev_id
        dev_loc = None

        if 'locations' in ttn_dev and 'user' in ttn_dev['locations']:
            user_loc = ttn_dev['locations']['user']
            dev_lat = user_loc['latitude']
            dev_long = user_loc['longitude']
            dev_loc = Location(lat=dev_lat, long=dev_long)

        props = {}
        props["app_id"] = app_id
        props["dev_id"] = dev_id

        pd = PhysicalDevice(source_name='ttn', name=dev_name, location=dev_loc, properties=props)
        broker.create_physical_device(pd)

    return Response(status_code=204)
