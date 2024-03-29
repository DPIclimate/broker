# Reverse proxy configuration for nginx

Add these blocks to the site definition to define the reverse proxy rules for the TTN webhook and REST API.

If nginx is running on the host that is running the container stack, then localhost is correct. If nginx
is running inside a container in the container stack, so connected to the network set up by docker-compose,
then the hostnames should be changed as noted.

To connect to the RabbitMQ monitor web page, use `https://hostname/rabbitmq`

```
    location /ttn/webhook/ {
        # Use the hostname 'ttn_webhook' if nginx is running in a container.
        proxy_pass http://localhost:5688;
    }

    # Special handling for FastAPI docs URLs.
    location /broker/api/docs {
        # Use the hostname 'restapi' if nginx is running in a container.
        proxy_pass http://localhost:5687/docs;
    }

    location /openapi.json {
        # Use the hostname 'restapi' if nginx is running in a container.
        proxy_pass http://localhost:5687/openapi.json;
    }

    # Handler for REST API calls.
    location /broker/ {
        # Use the hostname 'restapi' if nginx is running in a container.
        proxy_pass http://localhost:5687/broker/;
    }

    location /rabbitmq/ {
        # Use the hostname 'mq' if nginx is running in a container.
        proxy_pass http://localhost:15672/;
    }

    # These are for the management web app.
    location /iota {
        return 301 $scheme://$host/iota/;
    }

    location ^~ /iota/ {
        # Timeout if the real server is dead
        proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;

        # Proxy Connection Settings
        proxy_buffers 32 4k;
        proxy_connect_timeout 240;
        proxy_headers_hash_bucket_size 128;
        proxy_headers_hash_max_size 1024;
        proxy_http_version 1.1;
        proxy_read_timeout 240;
        proxy_redirect http:// $scheme://;
        proxy_send_timeout 240;

        # Proxy Cache and Cookie Settings
        proxy_cache_bypass $cookie_session;
        proxy_no_cache $cookie_session;

        # Proxy Header Settings
        proxy_set_header Host $host;
        proxy_set_header Proxy "";
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Host $host:$server_port;
        proxy_set_header X-Forwarded-Method $request_method;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Server $host;
        proxy_set_header X-Forwarded-Ssl on;
        proxy_set_header X-Forwarded-Uri $request_uri;
        proxy_set_header X-Original-URL $scheme://$http_host$request_uri;
        proxy_set_header X-Real-IP $remote_addr;

        # Use the hostname 'webapp' if nginx is running in a container.
        set $upstream_app 127.0.0.1;
        set $upstream_port 5000;
        set $upstream_proto http;
        proxy_pass $upstream_proto://$upstream_app:$upstream_port;
    }
```

To reverse proxy a public MQTT port to RabbitMQ, create a file
`/etc/nginx/modules-enabled/60-mqtt-stream.conf` with the following content.

```
# Reverse proxy definition for the MQTT port of the RabbitMQ container.
stream {
    server {
        listen 1883;
        # Replace 127.0.0.1 with the hostname 'mq' if running in a container.
        proxy_pass 127.0.0.1:1884;
    }
}
```