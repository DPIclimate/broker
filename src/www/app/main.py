from flask import Flask, render_template, request, make_response, redirect, url_for, session, send_from_directory
import folium
import os
from datetime import timedelta, datetime, timezone
import re

from utils.types import *
from utils.api import *

from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Response

app = Flask(__name__, static_url_path='/static')

debug_enabled = False

app.wsgi_app = DispatcherMiddleware(
    Response('Not Found', status=404),
    {'/iota': app.wsgi_app}
)


def time_since(date):
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
    else:
        return f'{seconds} seconds ago'


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
            return redirect(url_for('login'), code=302)


@app.route('/', methods=['GET', 'POST'])
def index():

    try:
        physicalDevices = []
        data = get_physical_devices(session.get('token'))
        if data is None:
            return render_template('error_page.html')

        for i in range(len(data)):
            physicalDevices.append(PhysicalDevice(
                uid=data[i]['uid'],
                name=data[i]['name'],
                source_name=data[i]['source_name'],
                last_seen=format_time_stamp(data[i]['last_seen'])
            ))
        return render_template('physical_device_table.html', title='Physical Devices', physicalDevices=physicalDevices)

    except requests.exceptions.HTTPError as e:
        return render_template('error_page.html', reason=e), e.response.status_code


@app.route('/login', methods=["GET", "POST"])
def login():

    try:
        if request.method == "POST":
            username: str = request.form['username']
            password: str = request.form['password']

            user_token = get_user_token(username=username, password=password)
            session['user'] = username
            session['token'] = user_token

            return redirect(url_for('index'))

        return render_template("login.html")

    except requests.exceptions.HTTPError as e:
        # Probs not best way to detecting incorect password
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


@app.route('/physical-device/<uid>', methods=['GET'])
def physical_device_form(uid):

    try:
        pd_data = get_physical_device(uid=uid, token=session.get('token'))

        pd_data['location'] = format_location_string(pd_data['location'])
        pd_data['last_seen'] = format_time_stamp(pd_data['last_seen'])
        properties_formatted = format_json(pd_data['properties'])
        ttn_link = generate_link(pd_data)
        sources = get_sources(token=session.get('token'))
        mappings = get_current_mapping_from_physical_device(uid=uid, token=session.get('token'))
        notes = get_physical_notes(uid=uid, token=session.get('token'))
        currentDeviceMapping = []
        deviceNotes = []
        if mappings is not None:
            currentDeviceMapping.append(DeviceMapping(
                pd_uid=mappings['pd']['uid'],
                pd_name=mappings['pd']['name'],
                ld_uid=mappings['ld']['uid'],
                ld_name=mappings['ld']['name'],
                start_time=format_time_stamp(mappings['start_time']),
                end_time=format_time_stamp(mappings['end_time'])))
        if notes is not None:
            for i in range(len(notes)):
                deviceNotes.append(DeviceNote(
                    note=notes[i]['note'],
                    uid=notes[i]['uid'],
                    ts=format_time_stamp(notes[i]['ts'])
                ))

        logical_devices = []
        ld_data = get_logical_devices(token=session.get('token'))
        for i in range(len(ld_data)):
            logical_devices.append(LogicalDevice(
                uid=ld_data[i]['uid'],
                name=ld_data[i]['name'],
                location=format_location_string(ld_data[i]['location']),
                last_seen=format_time_stamp(ld_data[i]['last_seen'])
            ))

        title = 'Physical Device ' + str(uid) + ' - ' + str(pd_data['name'])
        return render_template('physical_device_form.html',
                               title=title,
                               pd_data=pd_data,
                               ld_data=ld_data,
                               sources=sources,
                               properties=properties_formatted,
                               ttn_link=ttn_link,
                               currentMappings=currentDeviceMapping,
                               deviceNotes=deviceNotes)

    except requests.exceptions.HTTPError as e:
        return render_template('error_page.html', reason=e), e.response.status_code


@app.route('/logical-devices', methods=['GET'])
def logical_device_table():
    try:
        logical_devices = []
        ld_data = get_logical_devices(token=session.get('token'))
        for dev in ld_data:
            logical_devices.append(LogicalDevice(
                uid=dev['uid'],
                name=dev['name'],
                location=format_location_string(dev['location']),
                last_seen=format_time_stamp(dev['last_seen'])
            ))
        return render_template('logical_device_table.html', title='Logical Devices', logicalDevices=logical_devices)
    except requests.exceptions.HTTPError as e:
        return render_template('error_page.html', reason=e), e.response.status_code


@app.route('/logical-device/<uid>', methods=['GET'])
def logical_device_form(uid):
    try:
        ld_data = get_logical_device(uid=uid, token=session.get('token'))
        properties_formatted = format_json(ld_data['properties'])
        device_name = ld_data['name']
        device_location = format_location_string(ld_data['location'])
        device_last_seen = format_time_stamp(ld_data['last_seen'])
        ubidots_link = generate_link(ld_data)
        title = f'Logical Device {uid} - {device_name}'
        mappings = get_all_mappings_for_logical_device(uid=uid, token=session.get('token'))
        device_mappings = []
        if mappings is not None:
            for m in mappings:
                device_mappings.append(DeviceMapping(
                    pd_uid=m['pd']['uid'],
                    pd_name=m['pd']['name'],
                    ld_uid=m['ld']['uid'],
                    ld_name=m['ld']['name'],
                    start_time=format_time_stamp(m['start_time']),
                    end_time=format_time_stamp(m['end_time'])))

        # The physical_devices list is used in the dialog shown when mapping a logical device.
        physical_devices = []
        for pd in get_physical_devices(token=session.get('token')):
            physical_devices.append(PhysicalDevice(
                uid=pd['uid'],
                name=pd['name'],
                source_name=pd['source_name'],
                last_seen=format_time_stamp(pd['last_seen'])
            ))

        return render_template('logical_device_form.html',
                               title=title,
                               ld_data=ld_data,
                               pd_data=physical_devices,
                               deviceLocation=device_location,
                               deviceLastSeen=device_last_seen,
                               ubidots_link=ubidots_link,
                               properties=properties_formatted,
                               deviceMappings=device_mappings)
    except requests.exceptions.HTTPError as e:
        return render_template('error_page.html', reason=e), e.response.status_code


@app.route('/map', methods=['GET'])
def map():
    try:

        center_map = folium.Map(
            location=[-32.2400951991083, 148.6324743348766], title='PhysicalDeviceMap', zoom_start=10)
        # folium.Marker([-31.956194913619864, 115.85911692112582], popup="<i>Mt. Hood Meadows</i>", tooltip='click me').add_to(center_map)
        data = get_logical_devices(token=session.get('token'), include_properties=True)
        for dev in data:
            if dev['location'] is not None:
                color = 'blue'

                last_seen = dev['last_seen']
                last_seen_obj = datetime.fromisoformat(last_seen)

                popup_str = f'<span style="white-space: nowrap;">Device: {dev["uid"]} / {dev["name"]}<br>Last seen: {time_since(last_seen_obj)}'
                # Avoid undesirable linebreaks in the popup by replacing spaces and hypens.
                popup_str = popup_str.replace(' ', '&nbsp;')
                popup_str = popup_str.replace('-', '&#8209;')
                ubidots_link = generate_link(dev)
                if ubidots_link != '':
                    popup_str = f'{popup_str}<br><a target="_blank" href="{ubidots_link}">Ubidots</a>'

                popup_str = popup_str + '</span>'

                folium.Marker([dev['location']['lat'], dev['location']['long']],
                              popup=popup_str,
                              icon=folium.Icon(color=color, icon='cloud'),
                              tooltip=dev['name']).add_to(center_map)
        return center_map._repr_html_()
        # center_map
        # return render_template('map.html')
    except requests.exceptions.HTTPError as e:
        return render_template('error_page.html', reason=e), e.response.status_code


@app.route('/create-mapping', methods=['GET'])
def CreateMapping():
    try:

        uid = request.args['uid']
        physical_devie = get_physical_device(
            uid=uid, token=session.get('token'))
        new_ld_uid = create_logical_device(
            physical_device=physical_devie, token=session.get('token'))
        insert_device_mapping(
            physicalUid=uid, logicalUid=new_ld_uid, token=session.get('token'))

        return 'Success', 200
    except requests.exceptions.HTTPError as e:
        return f"Failed with http error {e.response.status_code}", e.response.status_code


@app.route('/create-note/<noteText>/<uid>', methods=['GET'])
def CreateNote(noteText, uid):
    try:

        insert_note(noteText=noteText, uid=uid,
                    token=session.get('token'))
        return 'Success', 200
    except requests.exceptions.HTTPError as e:
        return f"Failed with http error {e.response.status_code}", e.response.status_code


@app.route('/delete-note/<noteUID>', methods=['DELETE'])
def DeleteNote(noteUID):
    try:
        delete_note(uid=noteUID, token=session.get('token'))
        return 'Success', 200
    except requests.exceptions.HTTPError as e:
        return f"Failed with http error {e.response.status_code}", e.response.status_code


@app.route('/edit-note/<noteText>/<uid>', methods=['PATCH'])
def EditNote(noteText, uid):
    try:
        edit_note(noteText=noteText, uid=uid, token=session.get("token"))

        return 'Success', 200
    except requests.exceptions.HTTPError as e:
        return f"Failed with http error {e.response.status_code}", e.response.status_code


@app.route('/update-physical-device', methods=['GET'])
def UpdatePhysicalDevice():
    try:
        if request.args['form_location'] != None and request.args['form_location'] != '' and request.args['form_location'] != 'None':
            location = request.args['form_location'].split(',')
            locationJson = {
                "lat": location[0].replace(' ', ''),
                "long": location[1].replace(' ', ''),
            }
        else:
            locationJson = None

        update_physical_device(
            uid=request.args['form_uid'], name=request.args['form_name'], location=locationJson, token=session.get('token'))
        return 'Success', 200
    except requests.exceptions.HTTPError as e:
        return f"Failed with http error {e.response.status_code}", e.response.status_code


@app.route('/update-mappings', methods=['GET'])
def UpdateMappings():
    try:
        insert_device_mapping(
            physicalUid=request.args['physicalDevice_mapping'], logicalUid=request.args['logicalDevice_mapping'], token=session.get('token'))
        return 'Success', 200
    except requests.exceptions.HTTPError as e:
        return f"Failed with http error {e.response.status_code}", e.response.status_code


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


@app.route('/update-logical-device', methods=['GET'])
def UpdateLogicalDevice():
    try:
        if request.args['form_location'] != None and request.args['form_location'] != '' and request.args['form_location'] != 'None':
            location = request.args['form_location'].split(',')
            locationJson = {
                "lat": location[0].replace(' ', ''),
                "long": location[1].replace(' ', ''),
            }
        else:
            locationJson = None

        update_logical_device(uid=request.args['form_uid'], name=request.args['form_name'],
                              location=locationJson, token=session.get('token'))
        #return 'Success', 200
        return logical_device_form(request.args['form_uid'])

    except requests.exceptions.HTTPError as e:
        return f"Failed with http error {e.response.status_code}", e.response.status_code


@app.route('/static/<filename>')
def get_file(filename):
    return send_from_directory('static', filename)


def format_time_stamp(unformattedTime):
    if unformattedTime:
        formattedLastSeen = unformattedTime[0:19]
        formattedLastSeen = formattedLastSeen.replace('T', ' ')
        return formattedLastSeen


def format_location_string(location_json) -> str:
    formatted_location = None
    if location_json is not None:
        formatted_location = f'{str(location_json["lat"])}, {str(location_json["long"])}'

    return formatted_location


def generate_link(data):
    link = ''
    if 'source_name' in data and 'source_ids' in data and 'app_id' in data['source_ids'] and 'dev_id' in data['source_ids']:
        link = 'https://au1.cloud.thethings.network/console/applications/'
        link += data['source_ids']['app_id']
        link += '/devices/'
        link += data['source_ids']['dev_id']
    elif 'properties' in data and 'ubidots' in data['properties'] and 'id' in data['properties']['ubidots']:
        link = 'https://industrial.ubidots.com.au/app/devices/'
        link+= data['properties']['ubidots']['id']
    return link


if __name__ == '__main__':

    app.run(debug=debug_enabled, port='5000', host='0.0.0.0')
