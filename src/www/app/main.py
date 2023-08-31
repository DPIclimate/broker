from flask import Flask, render_template, request, make_response, redirect, url_for, session, send_from_directory
import folium
import os
from datetime import timedelta, datetime, timezone
import re

from utils.api import *

from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Response

from pdmodels.Models import PhysicalDevice, LogicalDevice, PhysicalToLogicalMapping

app = Flask(__name__, static_url_path='/static')

debug_enabled = True

app.wsgi_app = DispatcherMiddleware(
    Response('Not Found', status=404),
    {'/iota': app.wsgi_app}
)


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
    return redirect(url_for('physical_device_table'))


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


@app.route('/wombats', methods=['GET'])
def wombats():
    try:
        physical_devices = get_physical_devices(session.get('token'), source_name='wombat', include_properties=True)

        if physical_devices is None:
            return render_template('error_page.html')

        logical_devices = []
        if len(physical_devices) > 0:
            logical_devices = get_logical_devices(session.get('token'))

        mappings = get_current_mappings(session.get('token'))

        mapping_obj: List[PhysicalToLogicalMapping] = []

        for dev in physical_devices:
            ccid = dev.source_ids.get('ccid', None)
            fw_version = dev.source_ids.get('firmware', None)

            if ccid is not None:
                setattr(dev, 'ccid', ccid)

            if fw_version is not None:
                setattr(dev, 'fw', fw_version)

            for mapping in mappings:
                if dev.uid != mapping.pd:
                    continue

                # Replace the logical device id in the mapping with the logical device object.
                mapping.ld = next(filter(lambda ld: ld.uid == mapping.ld, logical_devices), None)
                setattr(dev, 'mapping', mapping)

                #mapping_obj.append(mapping)
                break

        return render_template('wombats.html', title='Wombats', physicalDevices=physical_devices, dev_mappings=mapping_obj)

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
        pd_data = get_physical_device(uid, session.get('token'))

        pd_data['location'] = format_location_string(pd_data['location'])
        pd_data['last_seen'] = format_time_stamp(pd_data['last_seen'])
        properties_formatted = format_json(pd_data['properties'])
        ttn_link = generate_link(pd_data)
        sources = get_sources(session.get('token'))
        mappings = get_all_mappings_for_physical_device(uid, session.get('token'))

        logical_devices = get_logical_devices(session.get('token'))

        notes = get_physical_notes(uid, session.get('token'))

        currentDeviceMapping = []

        if mappings is not None:
            for m in mappings:
                currentDeviceMapping.append(m)

        title = 'Physical Device ' + str(uid) + ' - ' + str(pd_data['name'])
        return render_template('physical_device_form.html',
                               title=title,
                               pd_data=pd_data,
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
        logical_devices = get_logical_devices(session.get('token'))
        if logical_devices is None:
            return render_template('error_page.html')

        physical_devices = []
        if len(logical_devices) > 0:
            physical_devices = get_physical_devices(session.get('token'))

        mappings = get_current_mappings(session.get('token'))

        mapping_obj: List[PhysicalToLogicalMapping] = []

        for dev in logical_devices:
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
        ld_data = get_logical_device(uid=uid, token=session.get('token'))
        properties_formatted = format_json(ld_data['properties'])
        device_name = ld_data['name']
        device_location = format_location_string(ld_data['location'])
        device_last_seen = format_time_stamp(ld_data['last_seen'])
        ubidots_link = generate_link(ld_data)
        title = f'Logical Device {uid} - {device_name}'
        mappings = get_all_mappings_for_logical_device(uid=uid, token=session.get('token'))

        # The physical_devices list is used in the dialog shown when mapping a logical device.
        physical_devices = get_physical_devices(session.get('token'))

        return render_template('logical_device_form.html',
                               title=title,
                               ld_data=ld_data,
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
        center_map = folium.Map(
            location=[-32.2400951991083, 148.6324743348766], title='PhysicalDeviceMap', zoom_start=10)
        # folium.Marker([-31.956194913619864, 115.85911692112582], popup="<i>Mt. Hood Meadows</i>", tooltip='click me').add_to(center_map)
        data = get_logical_devices(session.get('token'), include_properties=True)
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
        physical_device = get_physical_device(uid=uid, token=session.get('token'))
        new_ld_uid = create_logical_device(physical_device=physical_device, token=session.get('token'))
        insert_device_mapping(physicalUid=uid, logicalUid=new_ld_uid, token=session.get('token'))

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

    try:
        if request.form.get("form_location") != 'None':
            location = request.form.get('form_location').split(',')
            locationJson = {
                "lat": location[0].replace(' ', ''),
                "long": location[1].replace(' ', ''),
            }
        else:
            locationJson = None

        update_physical_device(uid=request.form.get("form_uid"), name=request.form.get("form_name"), location=locationJson, token=session.get('token'))
        
        return 'Success', 200
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            return f"You do not have sufficient permissions to make this change", e.response.status_code
        
        return f"HTTP request with RestAPI failed with error {e.response.status_code}", e.response.status_code


@app.route('/update-mappings', methods=['GET'])
def UpdateMappings():
    try:
        insert_device_mapping(
            physicalUid=request.args['physicalDevice_mapping'], logicalUid=request.args['logicalDevice_mapping'], token=session.get('token'))
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
    uid = request.args['uid']
    is_active = request.args['is_active']

    toggle_device_mapping(uid=uid, dev_type=dev_type, is_active=is_active, token=session.get('token'))
    
    return 'Success', 200

@app.route('/update-logical-device', methods=['PATCH'])
def UpdateLogicalDevice():

    try:
        if request.form.get("form_location") != 'None':
            location = request.form.get('form_location').split(',')
            locationJson = {
                "lat": location[0].replace(' ', ''),
                "long": location[1].replace(' ', ''),
            }
        else:
            locationJson = None

        update_logical_device(uid=request.form.get("form_uid"), name=request.form.get("form_name"), location=locationJson, token=session.get('token'))
        return 'Success', 200
        

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            return f"You do not have sufficient permissions to make this change", e.response.status_code
        
        return f"HTTP request with RestAPI failed with error {e.response.status_code}", e.response.status_code


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
