# Reverse proxy configuration for nginx

Add these blocks to the site definition to define the reverse proxy rules for the TTN webhook and REST API.

If nginx is running on the host that is running the container stack, then localhost is correct. If nginx
is running inside a container in the container stack, so connected to the network set up by docker-compose,
then the hostnames should be changed as noted.

To connect to the RabbitMQ monitor web page, use `https://hostname/rabbitmq`

```
    location /ttn/webhook/ {
        # Use the hostname ttn_webhook if nginx is running in a container.
        proxy_pass http://localhost:5688;
    }

    # Special handling for FastAPI docs URLs.
    location /broker/api/docs {
        # Use the hostname restapi if nginx is running in a container.
        proxy_pass http://localhost:5687/docs;
    }

    location /openapi.json {
        # Use the hostname restapi if nginx is running in a container.
        proxy_pass http://localhost:5687/openapi.json;
    }

    # Handler for REST API calls.
    location /broker/ {
        # Use the hostname restapi if nginx is running in a container.
        proxy_pass http://localhost:5687/broker/;
    }

    location /rabbitmq/ {
        # Use the hostname mq if nginx is running in a container.
        proxy_pass http://localhost:15672/;
    }
```

To reverse proxy a public MQTT port to RabbitMQ, create a file
`/etc/nginx/modules-enabled/60-mqtt-stream.conf` with the following content.

```
# Reverse proxy definition for the MQTT port of the RabbitMQ container.
stream {
    server {
        listen 1883;
        # Replace 127.0.0.1 with the hostname mq if running in a container.
        proxy_pass 127.0.0.1:1884;
    }
}
```