#!/bin/bash

echo 'starting api (requires questdb running)'
uvicorn basic_api:app --reload

