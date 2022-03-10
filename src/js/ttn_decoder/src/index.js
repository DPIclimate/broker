const express = require('express');
const bodyParser = require('body-parser');
//const cors = require('cors');
//const helmet = require('helmet');
const morgan = require('morgan');
const fs = require('fs');

// defining the Express app
const app = express();

// adding Helmet to enhance your API's security
//app.use(helmet());

// using bodyParser to parse JSON bodies into JS objects
app.use(bodyParser.json());

// enabling CORS for all requests
//app.use(cors());

// adding morgan to log HTTP requests
app.use(morgan('combined'));

app.post('/', (req, res) => {
    const data = req.body;
    const device = data.device;
    const ttnMsg = data.message;
    var decoderName = device.properties.ttn.ids.application_ids.application_id;
    if (device.properties.hasOwnProperty("decoder_name")) {
        decoderName = device.properties.decoder_name;
    }

    eval(fs.readFileSync(`../ttn_formatters/uplink/${decoderName}.js`, 'utf8'));

    var msgOk = false;
    if (ttnMsg.hasOwnProperty("uplink_message")) {
        const uplink_message = ttnMsg.uplink_message;
        if (uplink_message.hasOwnProperty("frm_payload") && uplink_message.hasOwnProperty("f_port") && uplink_message.hasOwnProperty("received_at")) {
            port = uplink_message.f_port;
            payload_raw = uplink_message.frm_payload;
            msgOk = true;
        }
    }

    if (msgOk != true) {
        throw new Error('Invalid message.');
    }

    var input = {
        bytes: Buffer.from(payload_raw, 'base64'),
        fPort: port
    };

    var val = decodeUplink(input);
    res.send(val)
});

app.listen(3001, () => {
  console.log('Listening on port 3001');
});
