# Reverse proxy configuration for nginx

Add these blocks to the site definition to define the reverse proxy rules for the TTN webhook and REST API.

To connect to the RabbitMQ monitor web page, use `https://hostname/rabbitmq`

```
    location /ttn/webhook/ {
        proxy_pass http://localhost:5688;
    }

    location /api/ {
        proxy_pass http://localhost:5687;
    }

    location /rabbitmq/ {
        proxy_pass http://localhost:15672/;
    }
```
