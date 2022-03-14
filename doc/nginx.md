# Reverse proxy configuration for nginx

Add these blocks to the site definition to define the reverse proxy rules for the TTN webhook and REST API.

```
    location /ttn/webhook/ {
        proxy_pass http://localhost:5688;
    }

    location /api/ {
        proxy_pass http://localhost:5687;
    }
```
