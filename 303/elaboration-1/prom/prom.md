# Prometheus TSDB Reference 

## Installation
- Prometheus is available on docker, under prom/prometheus. Binaries are also available on the website.
- Additionally, the json_exporter tool built by the prometheus community is available on quay.io.

## Usage 
- Prometheus differs a lot from other timeseries database solutions. Whereas QuestDB and TimescaleDB are able to be controlled via HTTP commands sent through a Python file, Prometheus (as far as I have seen) utilises an entirely different approach.
  - Prometheus almost exclusively gathers data (or metrics) by scrubbing data from various HTTP endpoints.
  - For this reason, an additional Python server had to be run alongside the docker containers for Prometheus and the json_exporter. This server's task was to host the json file so the data could be uploaded.
- The scrubbing is handled by Prometheus internally, and every target is spelled out in YAML configuration files. 
  - These files are prometheus.yml (configuration for the Promtheus instance) and config.yml (configuration for the json_exporter instance).

## Commands 
- To start the Prometheus docker instance.
```bash
docker run -d --rm --name json_exporter -p 7979:7979 -v $PWD/config/config.yml:/config.yml quay.io/prometheuscommunity/json-exporter --config.file=/config.yml 
```
- To start the json_exporter docker instance.
```bash
docker run -d --rm --name prometheus -p 9090:9090 -v $PWD/config/prometheus.yml:/etc/prometheus/prometheus.yml prom/prometheus 
```