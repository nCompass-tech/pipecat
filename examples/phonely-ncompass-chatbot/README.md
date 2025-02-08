# NCompass Denoise Service

The NCompassDenoiseService is a real-time audio denoising service that processes audio streams using nCompass's websocket-based API.

## Usage

```python
from pipecat.services.ncompass import NCompassDenoiseService

# Initialize the service
denoiser = NCompassDenoiseService(
    api_key="your_ncompass_api_key",  # Required
    out_frame_rate=15999              # Optional, defaults to 16000
)

# Add to your pipeline
pipeline = Pipeline([
    transport.input(),
    denoiser,          # Add the denoiser before STT for best results
    stt_service,
    # ... rest of pipeline
])
```

## Arguments

- `api_key` (str, required): Your nCompass API key
- `out_frame_rate` (int, optional): Output sample rate in Hz. Defaults to 16000.

## Features

- Real-time audio denoising via websocket streaming
- Automatic reconnection on connection drops
- Audio passthrough on errors to prevent pipeline blocking
- Configurable audio accumulation time for optimal processing (default 140ms)

## Environment Setup

Add your nCompass API key to your .env file:

```bash
NCOMPASS_API_KEY=your_api_key_here
```

## Notes

- The service expects 16-bit linear PCM audio input
- Default sample rate is 16kHz mono
- Processes audio in chunks for optimal latency/quality balance


# Translation Chatbot

<img src="image.png" width="420px">

This app listens for user speech, then translates that speech to Spanish and speaks the translation back to the user using text-to-speech. It's probably most useful with multiple users talking to each other, along with some manual track subscription management in the Daily call.

See a quick video walkthrough of the code here: https://www.loom.com/share/59fdddf129534dc2be4dde3cc6ebe8de

## Get started

```python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp env.example .env # and add your credentials

```

## Run the server

```bash
python server.py
```

Then, visit `http://localhost:7860/` in your browser to start a translatorbot session.

## Build and test the Docker image

```
docker build -t chatbot .
docker run --env-file .env -p 7860:7860 chatbot
```
