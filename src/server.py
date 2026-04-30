import io
import os
import sys

import numpy as np
import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException, Request

sys.path.insert(0, os.path.dirname(__file__))

from transcription import create_local_model, transcribe_local
from utils import ConfigManager

app = FastAPI()
_model = None


@app.on_event("startup")
async def startup():
    global _model
    ConfigManager.initialize()
    _model = create_local_model()


@app.post("/transcribe")
async def transcribe_endpoint(request: Request):
    audio_bytes = await request.body()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="No audio data received")

    try:
        audio_data, _ = sf.read(io.BytesIO(audio_bytes), dtype="int16")
        text = transcribe_local(audio_data, _model)
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=47892)
