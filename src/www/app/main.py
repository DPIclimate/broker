from flask import Flask, render_template, request, make_response, redirect, url_for, session
import folium
import os
from datetime import timedelta
import re

from utils.types import *
from utils.api import *

from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Response

app = Flask(__name__)

debug_enabled = False

app.wsgi_app = DispatcherMiddleware(
    Response('Not Found', status=404),
    {'/iota': app.wsgi_app}
)

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
                last_seen=formatTimeStamp(data[i]['last_seen'])
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


@app.route('/singout', methods=["GET"])
def singout():
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

        pd_data['location'] = formatLocationString(pd_data['location'])
        pd_data['last_seen'] = formatTimeStamp(pd_data['last_seen'])
        properties_formatted = format_json(pd_data['properties'])
        sources = get_sources(token=session.get('token'))
        mappings = get_current_mappings(uid=uid, token=session.get('token'))
        notes = get_physical_notes(uid=uid, token=session.get('token'))
        currentDeviceMapping = []
        deviceNotes = []
        if mappings is not None:
            currentDeviceMapping.append(DeviceMapping(
                pd_uid=mappings['pd']['uid'],
                pd_name=mappings['pd']['name'],
                ld_uid=mappings['ld']['uid'],
                ld_name=mappings['ld']['name'],
                start_time=formatTimeStamp(mappings['start_time']),
                end_time=formatTimeStamp(mappings['end_time'])))
        if notes is not None:
            for i in range(len(notes)):
                deviceNotes.append(DeviceNote(
                    note=notes[i]['note'],
                    uid=notes[i]['uid'],
                    ts=formatTimeStamp(notes[i]['ts'])
                ))

        logicalDevices = []
        ld_data = get_logical_devices(token=session.get('token'))
        for i in range(len(ld_data)):
            logicalDevices.append(LogicalDevice(
                uid=ld_data[i]['uid'],
                name=ld_data[i]['name'],
                location=formatLocationString(ld_data[i]['location']),
                last_seen=formatTimeStamp(ld_data[i]['last_seen'])
            ))

        title = 'Physical Device ' + str(uid) + ' - ' + str(pd_data['name'])
        return render_template('physical_device_form.html',
                               title=title,
                               pd_data=pd_data,
                               ld_data=ld_data,
                               sources=sources,
                               properties=properties_formatted,
                               currentMappings=currentDeviceMapping,
                               deviceNotes=deviceNotes)

    except requests.exceptions.HTTPError as e:
        return render_template('error_page.html', reason=e), e.response.status_code


@app.route('/logical-devices', methods=['GET'])
def logical_device_table():
    try:

        logicalDevices = []
        ld_data = get_logical_devices(token=session.get('token'))
        for i in range(len(ld_data)):
            logicalDevices.append(LogicalDevice(
                uid=ld_data[i]['uid'],
                name=ld_data[i]['name'],
                location=formatLocationString(ld_data[i]['location']),
                last_seen=formatTimeStamp(ld_data[i]['last_seen'])
            ))
        return render_template('logical_device_table.html', title='Logical Devices', logicalDevices=logicalDevices)
    except requests.exceptions.HTTPError as e:
        return render_template('error_page.html', reason=e), e.response.status_code


@app.route('/logical-device/<uid>', methods=['GET'])
def logical_device_form(uid):
    try:
        ld_data = get_logical_device(uid=uid, token=session.get('token'))
        properties_formatted = format_json(ld_data['properties'])
        deviceName = ld_data['name']
        deviceLocation = formatLocationString(ld_data['location'])
        deviceLastSeen = formatTimeStamp(ld_data['last_seen'])
        title = 'Logical Device ' + str(uid) + ' - ' + str(deviceName)
        mappings = get_device_mappings(uid=uid, token=session.get('token'))
        deviceMappings = []
        if mappings is not None:
            for i in range(len(mappings)):
                deviceMappings.append(DeviceMapping(
                    pd_uid=mappings[i]['pd']['uid'],
                    pd_name=mappings[i]['pd']['name'],
                    ld_uid=mappings[i]['ld']['uid'],
                    ld_name=mappings[i]['ld']['name'],
                    start_time=formatTimeStamp(mappings[i]['start_time']),
                    end_time=formatTimeStamp(mappings[i]['end_time'])))

        physicalDevices = []
        data = get_physical_devices(token=session.get('token'))
        for i in range(len(data)):
            physicalDevices.append(PhysicalDevice(
                uid=data[i]['uid'],
                name=data[i]['name'],
                source_name=data[i]['source_name'],
                last_seen=formatTimeStamp(data[i]['last_seen'])
            ))

        return render_template('logical_device_form.html',
                               title=title,
                               ld_data=ld_data,
                               pd_data=physicalDevices,
                               deviceLocation=deviceLocation,
                               deviceLastSeen=deviceLastSeen,
                               properties=properties_formatted,
                               deviceMappings=deviceMappings)
    except requests.exceptions.HTTPError as e:
        return render_template('error_page.html', reason=e), e.response.status_code


@app.route('/map', methods=['GET'])
def map():
    try:

        center_map = folium.Map(
            location=[-32.2400951991083, 148.6324743348766], title='PhysicalDeviceMap', zoom_start=10)
        # folium.Marker([-31.956194913619864, 115.85911692112582], popup="<i>Mt. Hood Meadows</i>", tooltip='click me').add_to(center_map)
        data = get_physical_devices(token=session.get('token'))
        for i in range(len(data)):
            if (data[i]['location'] is not None):
                if (data[i]['source_name'] == "greenbrain"):
                    color = 'green'
                elif (data[i]['source_name'] == "ttn"):
                    color = 'red'
                else:
                    color = 'blue'
                folium.Marker([data[i]['location']['lat'], data[i]['location']['long']],
                              popup=data[i]['uid'],
                              icon=folium.Icon(color=color, icon='cloud'),
                              tooltip=data[i]['name']).add_to(center_map)

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
        return 'Success', 200

    except requests.exceptions.HTTPError as e:
        return f"Failed with http error {e.response.status_code}", e.response.status_code


def formatTimeStamp(unformattedTime):
    if unformattedTime:
        formattedLastSeen = unformattedTime[0:19]
        formattedLastSeen = formattedLastSeen.replace('T', ' ')
        return formattedLastSeen


def formatLocationString(locationJson):
    if locationJson is not None:
        formattedLocation = str(locationJson['lat'])
        formattedLocation += ', '
        formattedLocation += str(locationJson['long'])
    else:
        formattedLocation = None
    return formattedLocation


if __name__ == '__main__':

    app.run(debug=debug_enabled, port='5000', host='0.0.0.0')
