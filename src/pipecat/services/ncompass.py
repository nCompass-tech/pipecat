#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

from typing import Optional
from pipecat.services.openai import BaseOpenAILLMService

import websockets
from typing import cast

from pipecat.audio.filters.base_audio_filter import BaseAudioFilter
from pipecat.frames.frames import FilterControlFrame, FilterEnableFrame

from structlog import get_logger

logger = get_logger()

class NCompassFilter(BaseAudioFilter):
    """Audio filter that uses nCompass's denoising websocket API."""

    def __init__(self, *, api_key: str, chunk_size_ms: int = 100, out_frame_rate: int = 16000) -> None:
        self._api_key = api_key
        self._chunk_size_ms = chunk_size_ms
        self._out_frame_rate = out_frame_rate
        
        self._filtering = True
        self._sample_rate = 0
        self._bytes_per_sample = 2  # 16-bit audio (consistent with linear16 encoding)
        self._ws = None        

    def _get_url(self) -> str:
        """Construct the websocket URL for nCompass API."""
        return (f"wss://{self._api_key}.ncompass.tech/denoise/pcm/pcm/{self._api_key}"
                f"/{self._bytes_per_sample}/{self._sample_rate}/{self._out_frame_rate}")

    async def start(self, sample_rate: int):
        """Initialize the filter with the given sample rate."""
        self._sample_rate = sample_rate
        try:
            self._ws = await websockets.connect(self._get_url())
        except Exception as e:
            self._filtering = False

    async def stop(self):
        """Close the websocket connection when stopping."""
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def process_frame(self, frame: FilterControlFrame):
        """Process control frames to enable/disable filtering."""
        if isinstance(frame, FilterEnableFrame):
            self._filtering = frame.enable

    async def filter(self, audio: bytes) -> bytes:
        """Filter the audio using nCompass denoising API."""
        if not self._filtering or not self._ws:                    
            return audio

        try:
            # Send the audio chunk through websocket
            await self._ws.send(audio)
            # Receive denoised audio
            denoised_audio = cast(bytes, await self._ws.recv())
            return denoised_audio
            
        except Exception as e:
            self._filtering = False
            return audio

class NCompassLLMService(BaseOpenAILLMService):
    def __init__(self,
                 *,
                 api_key:Optional[str]=None,
                 model:str = "llama-3.1-70B",
                 base_url:str = "http://ncompass.tech"): # TODO: get this link
        super().__init__(model=model, base_url=base_url, api_key=api_key)
