from fastapi import FastAPI, Query, HTTPException, status
import json
from typing import Dict, List, Optional

from pdmodels.Models import PhysicalDevice
import db.DAO as dao

app = FastAPI()


@app.post("/ttn/webhook/", status=status.204_NO_CONTENT)
async def webhook_endpoint():
    """
    Receive webhook calls from TTN.
    """
    pass