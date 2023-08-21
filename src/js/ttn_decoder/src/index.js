const express = require('express');
const bodyParser = require('body-parser');
//const cors = require('cors');
//const helmet = require('helmet');
const morgan = require('morgan');
const fs = require('fs');
const client = require('prom-client');

// defining the Express app
const app = express();
const collectDefaultMetrics = client.collectDefaultMetrics;
collectDefaultMetrics({ prefix: 'ttn_decoder:' });

const httpRequestDurationMicroseconds = new client.Histogram({
  name: 'ttn_decoder:http_request_duration_seconds',
  help: 'Duration of HTTP requests in microseconds',
  labelNames: ['method', 'route', 'code'],
  buckets: [0.10, 5, 15, 50, 100, 200, 300, 400, 500],  // Buckets for response time (in milliseconds)
});


// adding Helmet to enhance your API's security
//app.use(helmet());

// using bodyParser to parse JSON bodies into JS objects
app.use(bodyParser.json());

// enabling CORS for all requests
//app.use(cors());

// adding morgan to log HTTP requests
app.use(morgan('combined'));

app.use((req, res, next) => {
  const responseTimeInMs = Date.now();
  res.on('finish', () => {
    const route = req.route ? req.route.path : 'unknown_route';
    const responseTime = Date.now() - responseTimeInMs;
    httpRequestDurationMicroseconds.labels(req.method, route, res.statusCode).observe(responseTime);
  });
  next();
});


app.post('/', (req, res) => {
    const data = req.body;
    const device = data.device;
    const ttnMsg = data.message;
    var decoderName = device.properties.ttn.ids.application_ids.application_id;
    if (device.source_ids.hasOwnProperty("decoder_name")) {
        decoderName = device.source_ids.decoder_name;
    }

    decoderFilename = `../ttn_formatters/uplink/${decoderName}.js`;
    try {
        fs.accessSync(decoderFilename, fs.constants.R_OK);
    } catch(err) {
        throw new Error(`Decoder not found: ${decoderFilename}`)
    }

    eval(fs.readFileSync(decoderFilename, 'utf8'));

    var msgOk = false;
    if (ttnMsg.hasOwnProperty("uplink_message")) {
        const uplink_message = ttnMsg.uplink_message;
        if (uplink_message.hasOwnProperty("frm_payload") && uplink_message.hasOwnProperty("f_port")) {
            port = uplink_message.f_port;
            payload_raw = uplink_message.frm_payload;
            msgOk = true;
        }
    }

    if (msgOk != true) {
        throw new Error('Did not find port and payload information in message.');
    }

    var input = {
        bytes: Buffer.from(payload_raw, 'base64'),
        fPort: port,
        device: device
    };

    var val = decodeUplink(input);
    res.send(val)
});


app.get('/metrics', async (req, res) => {
  try {
    let metrics = client.register.metrics();
    if (metrics instanceof Promise) {
      metrics = await metrics;
    }
    res.set('Content-Type', client.register.contentType);
    res.end(metrics);
  } catch (err) {
    res.status(500).send(err.message);
  }
});

app.listen(3001, () => {
  console.log('Listening on port 3001');
});
