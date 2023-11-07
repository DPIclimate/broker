import atexit
import time
from typing import Tuple

from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory

import folium
import paho.mqtt.client as mqtt
import os
from datetime import timedelta, datetime, timezone
import re

from utils.api import *

from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Response

from pdmodels.Models import PhysicalDevice, LogicalDevice, PhysicalToLogicalMapping, Location

from logging.config import dictConfig

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

app = Flask(__name__, static_url_path='/static')

app.wsgi_app = DispatcherMiddleware(
    Response('Not Found', status=404),
    {'/iota': app.wsgi_app}
)

_location_re = re.compile(r'([+-]?\d+\.?\d*)\s*,\s*([+-]?\d+\.?\d*)')

_mqtt_host = os.getenv('RABBITMQ_HOST')
_mqtt_user = os.getenv('RABBITMQ_DEFAULT_USER')
_mqtt_pass = os.getenv('RABBITMQ_DEFAULT_PASS')


def parse_location(loc_str: str) -> Tuple[bool, Location | None]:
    """
    Parse a Location object from string. If a non-empty string is provided it must be of
    the form of two floats separated by a comma. Whitespace is ignored.

    if loc_str is None or empty then (True, None) is returned. If loc_str conforms to the format
    above, (True, Location) is returned. Otherwise (False, None) is returned.
    """
    if loc_str is None or len(loc_str.strip()) == 0:
        return True, None

    loc_str = loc_str.strip()
    m: re.Match = _location_re.fullmatch(loc_str)
    if m is None:
        return False, None

    groups = m.groups()
    if len(groups) != 2:
        return False, None

    location: Location = Location(lat=float(groups[0]), long=float(groups[1]))
    return True, location


def time_since(date: datetime) -> str:
    now = datetime.now(timezone.utc)
    date_utc = date.astimezone(timezone.utc)
    delta = now - date_utc
    days = delta.days
    hours = int(delta.seconds / 3600)
    minutes = int((delta.seconds % 3600) / 60)
    seconds = int(delta.seconds % 60)
    if days > 0:
        return f'{days} days ago'
    elif hours > 0:
        return f'{hours} hours ago'
    elif minutes > 0:
        return f'{minutes} minutes ago'

    return f'{seconds} seconds ago'


#-------------
# MQTT section
#-------------

_mqtt_client = None
_wombat_config_msgs = {}

def mqtt_on_connect(client, userdata, flags, rc):
    global _mqtt_client
    app.logger.info('MQTT connected')
    _mqtt_client.subscribe(f'wombat/+')

def mqtt_on_message(client, userdata, msg):
    tp = msg.topic.split('/')
    if len(tp) == 2:
        sn = tp[1]
        if len(msg.payload) > 0:
            script = str(msg.payload, encoding='UTF-8')
            _wombat_config_msgs[sn] = script
        else:
            _wombat_config_msgs[sn] = None


def _send_mqtt_msg_via_sn(serial_nos: List[str], msg: str | None) -> None:
    """
    Publish a config script to a list of Wombats.

    Params:
        serial_nos: A list of Wombat serial numbers.
        msg: The config script to send, use None to clear the script.
    """
    if _mqtt_client.is_connected():
        for sn in serial_nos:
            _mqtt_client.publish(f'wombat/{sn}', msg, 1, True)


def _send_mqtt_msg_via_uids(p_uids: str | List[int], msg: str | None) -> None:
    """
    Publish a config script to a list of Wombats.

    Params:
        p_uids: A list of integer physical device ids or a string of the form "1,2,3".
        msg: The config script to send, use None to clear the script.
    """
    if _mqtt_client.is_connected():
        if isinstance(p_uids, str):
            p_uids = list(map(lambda i: int(i), p_uids.split(',')))

        serial_nos = []
        for p_uid in p_uids:
            pd = get_physical_device(p_uid, session.get('token'))
            if pd is not None and pd.source_ids.get('serial_no', None) is not None:
                serial_nos.append(pd.source_ids['serial_no'])

        _send_mqtt_msg_via_sn(serial_nos, msg)



"""
Session cookie config
"""
# Secret key changes every time server starts up
app.secret_key = os.urandom(32).hex()
app.permanent_session_lifetime = timedelta(hours=2)


@app.before_request
def check_user_logged_in():
    """
        Check user session is valid, if not redirect to /login
    """
    if not session.get('token'):
        if request.path != '/login' and request.path != '/static/main.css':
            # Stores the url user tried to go to in session so when they log in, we take them back to it
            session['original_url'] = request.url
            return redirect(url_for('login'), code=302)


@app.route('/', methods=['GET'])
def index():
    return redirect(url_for('logical_device_table'))


@app.route('/login', methods=["GET", "POST"])
def login():

    try:
        if request.method == "POST":
            username: str = request.form['username']
            password: str = request.form['password']

            user_token = get_user_token(username=username, password=password)
            session['user'] = username
            session['token'] = user_token

            if 'original_url' in session:
                return redirect(session.pop('original_url'))

            return redirect(url_for('index'))
        return render_template("login.html")

    except requests.exceptions.HTTPError as e:
        # Probs not best way to detecting incorrect password
        return render_template('login.html', failed=True)


@app.route('/signout', methods=["GET"])
def signout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/account', methods=["GET", "POST"])
def account():
    if request.method == "POST":
        try:
            password: str = request.form['password']
            password_conf: str = request.form['confirm-password']

            if not re.match(r".{8,}", password):
                return render_template('account.html', failed=True, reason="Invalid password, password must be at least 8 characters long")

            if password != password_conf:
                return render_template('account.html', failed=True, reason="Passwords do not match")

            new_token = change_user_password(
                password=password, token=session['token'])
            session['token'] = new_token

            return render_template('account.html', success=True)
        except requests.exceptions.HTTPError as e:
            return render_template('account.html', failed=True, reason=f"Exception occured {e.response.status_code}")

    return render_template('account.html')


@app.route('/wombats/config/logs', methods=['GET'])
def get_wombat_logs():
    _send_mqtt_msg_via_uids(request.args['uids'], 'ftp login\nupload log.txt\nftp logout\n')
    return "OK"


@app.route('/wombats/config/ota', methods=['GET'])
def wombat_ota():
    _send_mqtt_msg_via_uids(request.args['uids'], 'config ota 1\nconfig reboot\n')
    return "OK"


@app.route('/wombats/config/clear')
def clear_wombat_config_script():
    """
    Clear the config scripts for the Wombats identified by the sn request parameter.

    If the id request parameter is "uid" then sn must contain a list of phyiscal device ids. If id is "sn"
    then sn must contain a list of Wombat serial numbers.
    """
    sn = request.args['sn']
    if sn is not None:
        id_type = request.args.get('id', 'id')
        app.logger.info(f'Clearing config script for {sn}, id={id_type}')

        # Publish an empty retained message to clear the config script message from the topic.
        if id_type == 'uid':
            ids = list(map(lambda i: int(i), sn.split(',')))
            app.logger.info(ids)
            _send_mqtt_msg_via_uids(ids, None)
        else:
            ids = sn.split(',')
            app.logger.info(ids)
            _send_mqtt_msg_via_sn(ids, None)

    return "OK"


@app.route('/wombats', methods=['GET'])
def wombats():
    try:
        physical_devices = get_physical_devices(session.get('token'), source_name='wombat', include_properties=True)

        if physical_devices is None:
            return render_template('error_page.html')

        logical_devices: List[LogicalDevice] = []
        if len(physical_devices) > 0:
            logical_devices = get_logical_devices(session.get('token'), include_properties=True)

        mappings = get_current_mappings(session.get('token'))

        for dev in physical_devices:
            sn = dev.source_ids["serial_no"]
            ccid = dev.source_ids.get('ccid', None)
            fw_version: str = dev.source_ids.get('firmware', None)
            config_script: str | None = _wombat_config_msgs.get(dev.source_ids["serial_no"], None)

            if ccid is not None:
                setattr(dev, 'ccid', ccid)

            if fw_version is not None:
                setattr(dev, 'fw', fw_version)

            if config_script is not None:
                setattr(dev, 'script', config_script)

            setattr(dev, 'sn', sn)

            setattr(dev, 'ts_sort', dev.last_seen.timestamp())
            dev.last_seen = time_since(dev.last_seen)

            for mapping in mappings:
                if dev.uid != mapping.pd:
                    continue

                # Replace the logical device id in the mapping with the logical device object.
                mapping.ld = next(filter(lambda ld: ld.uid == mapping.ld, logical_devices), None)
                setattr(dev, 'mapping', mapping)

                link: str = generate_link(mapping.ld)
                if link is not None and len(link.strip()) > 0:
                    setattr(dev, 'ubidots_link', link)

                break

        return render_template('wombats.html', title='Wombats', physicalDevices=physical_devices)

    except requests.exceptions.HTTPError as e:
        return render_template('error_page.html', reason=e), e.response.status_code


@app.route('/physical-devices', methods=['GET'])
def physical_device_table():
    try:
        physical_devices = get_physical_devices(session.get('token'))
        if physical_devices is None:
            return render_template('error_page.html')

        logical_devices = []
        if len(physical_devices) > 0:
            logical_devices = get_logical_devices(session.get('token'))

        mappings = get_current_mappings(session.get('token'))

        mapping_obj: List[PhysicalToLogicalMapping] = []

        for dev in physical_devices:
            for mapping in mappings:
                if dev.uid != mapping.pd:
                    continue

                # Replace the logical device id in the mapping with the logical device object.
                mapping.ld = next(filter(lambda ld: ld.uid == mapping.ld, logical_devices), None)
                mapping_obj.append(mapping)
                break

        return render_template('physical_device_table.html', title='Physical Devices', physicalDevices=physical_devices, dev_mappings=mapping_obj)

    except requests.exceptions.HTTPError as e:
        return render_template('error_page.html', reason=e), e.response.status_code


@app.route('/physical-device/<uid>', methods=['GET'])
def physical_device_form(uid):

    try:
        device: PhysicalDevice = get_physical_device(uid, session.get('token'))

        device.location = format_location_string(device.location)
        device.last_seen = format_time_stamp(device.last_seen)
        properties_formatted = format_json(device.properties)
        ttn_link = generate_link(device)
        sources = get_sources(session.get('token'))
        mappings = get_all_mappings_for_physical_device(uid, session.get('token'))

        logical_devices = get_logical_devices(session.get('token'))

        notes = get_physical_notes(uid, session.get('token'))

        currentDeviceMapping = []

        if mappings is not None:
            for m in mappings:
                if m.start_time is not None:
                    m.start_time = m.start_time.isoformat(' ', 'seconds')

                if m.end_time is not None:
                    m.end_time = m.end_time.isoformat(' ', 'seconds')

                currentDeviceMapping.append(m)

        title = 'Physical Device ' + str(uid) + ' - ' + str(device.name)
        return render_template('physical_device_form.html',
                               title=title,
                               pd_data=device,
                               ld_data=logical_devices,
                               sources=sources,
                               properties=properties_formatted,
                               ttn_link=ttn_link,
                               currentMappings=currentDeviceMapping,
                               deviceNotes=notes)

    except requests.exceptions.HTTPError as e:
        return render_template('error_page.html', reason=e), e.response.status_code


@app.route('/logical-devices', methods=['GET'])
def logical_device_table():
    try:
        logical_devices: List[LogicalDevice] = get_logical_devices(session.get('token'))
        if logical_devices is None:
            return render_template('error_page.html')

        physical_devices = []
        if len(logical_devices) > 0:
            physical_devices = get_physical_devices(session.get('token'))

        mappings = get_current_mappings(session.get('token'))

        mapping_obj: List[PhysicalToLogicalMapping] = []

        for dev in logical_devices:
            dev.location = format_location_string(dev.location)
            for mapping in mappings:
                if dev.uid != mapping.ld:
                    continue

                # Replace the physical device id in the mapping with the physical device object.
                mapping.pd = next(filter(lambda pd: pd.uid == mapping.pd, physical_devices), None)

                mapping_obj.append(mapping)
                break

        return render_template('logical_device_table.html', title='Logical Devices', logicalDevices=logical_devices, dev_mappings=mapping_obj)
    except requests.exceptions.HTTPError as e:
        return render_template('error_page.html', reason=e), e.response.status_code


@app.route('/logical-device/<uid>', methods=['GET'])
def logical_device_form(uid):
    try:
        device = get_logical_device(uid, session.get('token'))
        properties_formatted = format_json(device.properties)
        device_location = format_location_string(device.location)
        device_last_seen = format_time_stamp(device.last_seen)
        ubidots_link = generate_link(device)
        title = f'Logical Device {device.uid} - {device.name}'
        mappings = get_all_mappings_for_logical_device(uid, session.get('token'))

        for m in mappings:
            if m.start_time is not None:
                m.start_time = m.start_time.isoformat(' ', 'seconds')

            if m.end_time is not None:
                m.end_time = m.end_time.isoformat(' ', 'seconds')

        # The physical_devices list is used in the dialog shown when mapping a logical device.
        physical_devices = get_physical_devices(session.get('token'))

        return render_template('logical_device_form.html',
                               title=title,
                               ld_data=device,
                               pd_data=physical_devices,
                               deviceLocation=device_location,
                               deviceLastSeen=device_last_seen,
                               ubidots_link=ubidots_link,
                               properties=properties_formatted,
                               deviceMappings=mappings)
    except requests.exceptions.HTTPError as e:
        return render_template('error_page.html', reason=e), e.response.status_code


@app.route('/map', methods=['GET'])
def show_map():
    try:
        center_map = folium.Map(location=[-32.2400951991083, 148.6324743348766], title='PhysicalDeviceMap', zoom_start=10)
        # folium.Marker([-31.956194913619864, 115.85911692112582], popup="<i>Mt. Hood Meadows</i>", tooltip='click me').add_to(center_map)
        data: List[LogicalDevice] = get_logical_devices(session.get('token'), include_properties=True)
        for dev in data:
            if dev.location is not None:
                color = 'blue'

                if dev.last_seen is None:
                    last_seen_desc = 'Never'
                else:
                    last_seen_desc = time_since(dev.last_seen)

                popup_str = f'<span style="white-space: nowrap;">Device: {dev.uid} / {dev.name}<br>Last seen: {last_seen_desc}'

                # Avoid undesirable linebreaks in the popup by replacing spaces and hypens.
                popup_str = popup_str.replace(' ', '&nbsp;')
                popup_str = popup_str.replace('-', '&#8209;')
                ubidots_link = generate_link(dev)
                if ubidots_link != '':
                    popup_str = f'{popup_str}<br><a target="_blank" href="{ubidots_link}">Ubidots</a>'

                popup_str = popup_str + '</span>'

                folium.Marker([dev.location.lat, dev.location.long],
                              popup=popup_str,
                              icon=folium.Icon(color=color, icon='cloud'),
                              tooltip=dev.name).add_to(center_map)

        return center_map._repr_html_()
        # center_map
        # return render_template('map.html')
    except requests.exceptions.HTTPError as e:
        return render_template('error_page.html', reason=e), e.response.status_code


@app.route('/create-mapping', methods=['GET'])
def CreateMapping():
    try:
        uid = request.args['uid']
        token = session.get('token')
        physical_device = get_physical_device(uid, token)
        new_ld_uid = create_logical_device(physical_device, token)
        insert_device_mapping(physical_device.uid, new_ld_uid, token)

        return 'Success', 200
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            return f"You do not have sufficient permissions to make this change", e.response.status_code

        return f"HTTP request with RestAPI failed with error {e.response.status_code}", e.response.status_code


@app.route('/create-note/<noteText>/<uid>', methods=['GET'])
def CreateNote(noteText, uid):
    try:

        insert_note(noteText=noteText, uid=uid,
                    token=session.get('token'))
        return 'Success', 200
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            return f"You do not have sufficient permissions to make this change", e.response.status_code

        return f"HTTP request with RestAPI failed with error {e.response.status_code}", e.response.status_code


@app.route('/delete-note/<noteUID>', methods=['DELETE'])
def DeleteNote(noteUID):
    try:
        delete_note(uid=noteUID, token=session.get('token'))
        return 'Success', 200
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            return f"You do not have sufficient permissions to make this change", e.response.status_code

        return f"HTTP request with RestAPI failed with error {e.response.status_code}", e.response.status_code


@app.route('/edit-note/<noteText>/<uid>', methods=['PATCH'])
def EditNote(noteText, uid):
    try:
        edit_note(noteText=noteText, uid=uid, token=session.get("token"))

        return 'Success', 200
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            return f"You do not have sufficient permissions to make this change", e.response.status_code

        return f"HTTP request with RestAPI failed with error {e.response.status_code}", e.response.status_code


@app.route('/update-physical-device', methods=['PATCH'])
def UpdatePhysicalDevice():
    uid = request.form.get("form_uid")
    token = session.get('token')

    try:
        update_loc, location = parse_location(request.form.get('form_location'))
        if not update_loc:
            device = get_physical_device(uid, token)
            location = device.location

        new_name: str = request.form.get("form_name")
        if new_name is None or len(new_name.strip()) < 1:
            new_name = device.name

        update_physical_device(uid, new_name, location, token)

        return 'Success', 200

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            return f"You do not have sufficient permissions to make this change", e.response.status_code

        return f"HTTP request with RestAPI failed with error {e.response.status_code}", e.response.status_code


@app.route('/update-mappings', methods=['GET'])
def UpdateMappings():
    try:
        insert_device_mapping(request.args['physicalDevice_mapping'], request.args['logicalDevice_mapping'], session.get('token'))
        return 'Success', 200
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            return f"You do not have sufficient permissions to make this change", e.response.status_code

        return f"HTTP request with RestAPI failed with error {e.response.status_code}", e.response.status_code


@app.route('/end-ld-mapping', methods=['GET'])
def EndLogicalDeviceMapping():
    uid = request.args['uid']
    end_logical_mapping(uid, session.get('token'))
    return 'Success', 200


@app.route('/end-pd-mapping', methods=['GET'])
def EndPhysicalDeviceMapping():
    uid = request.args['uid']
    end_physical_mapping(uid, session.get('token'))
    return 'Success', 200


@app.route('/toggle-mapping', methods=['PATCH'])
def ToggleDeviceMapping():
    """
        Toggle the mapping of a device to temporarily stop messages from being passed at the logical mapper
    """
    dev_type = request.args['dev_type']
    uid = int(request.args['uid'])
    is_active = request.args['is_active']

    toggle_device_mapping(uid=uid, dev_type=dev_type, is_active=is_active, token=session.get('token'))

    return 'Success', 200


@app.route('/update-logical-device', methods=['PATCH'])
def UpdateLogicalDevice():
    uid = request.form.get("form_uid")
    token = session.get('token')

    try:
        device = get_logical_device(uid, token)
        update_loc, location = parse_location(request.form.get('form_location'))

        if not update_loc:
            location = device.location

        new_name: str = request.form.get("form_name")
        if new_name is None or len(new_name.strip()) < 1:
            new_name = device.name

        update_logical_device(uid, new_name, location, token)
        return 'Success', 200

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            return f"You do not have sufficient permissions to make this change", e.response.status_code

        return f"HTTP request with RestAPI failed with error {e.response.status_code}", e.response.status_code


@app.route('/static/<filename>')
def get_file(filename: str):
    return send_from_directory('static', filename)


def format_time_stamp(unformatted_time: datetime) -> str:
    if unformatted_time is None:
        return ''

    if isinstance(unformatted_time, datetime):
        return unformatted_time.isoformat(sep=' ', timespec='seconds')

    return ''


def format_location_string(location: Location) -> str:
    formatted_location = ''
    if location is not None:
        formatted_location = f'{location.lat:.5f}, {location.long:.5f}'

    return formatted_location


def generate_link(data):
    link = ''

    if isinstance(data, LogicalDevice):
        if 'ubidots' in data.properties and 'id' in data.properties['ubidots']:
            link = 'https://industrial.ubidots.com.au/app/devices/'
            link += data.properties['ubidots']['id']
    elif isinstance(data, PhysicalDevice):
        if data.source_name == 'ttn' and 'app_id' in data.properties and 'dev_id' in data.properties:
            link = 'https://au1.cloud.thethings.network/console/applications/'
            link += data.source_ids['app_id']
            link += '/devices/'
            link += data.source_ids['dev_id']

    return link


def exit_handler():
    global _mqtt_client

    app.logger.info('Stopping')
    _mqtt_client.disconnect()

    while _mqtt_client.is_connected():
        time.sleep(0.5)

    _mqtt_client.loop_stop()
    app.logger.info('Done')


if __name__ == '__main__':
    app.logger.info('Starting')
    _mqtt_client = mqtt.Client()
    _mqtt_client.username_pw_set(_mqtt_user, _mqtt_pass)
    _mqtt_client.on_connect = mqtt_on_connect
    _mqtt_client.on_message = mqtt_on_message

    app.logger.info('Connecting to MQTT broker')
    _mqtt_client.connect_async(_mqtt_host)
    app.logger.info('Starting MQTT thread')
    _mqtt_client.loop_start()

    atexit.register(exit_handler)

    app.run(port='5000', host='0.0.0.0')
