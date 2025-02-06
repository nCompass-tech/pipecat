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
from pipecat.services.websocket_service import WebsocketService

logger = get_logger()


class NCompassFilter(BaseAudioFilter):
    """Audio filter that uses nCompass's denoising websocket API."""

    def __init__(
        self, *, api_key: str, chunk_size_ms: int = 100, out_frame_rate: int = 16000
    ) -> None:
        self._api_key = api_key
        self._chunk_size_ms = chunk_size_ms
        self._out_frame_rate = out_frame_rate

        self._filtering = True
        self._sample_rate = 0
        self._bytes_per_sample = 2  # 16-bit audio (consistent with linear16 encoding)
        self._ws = None

    def _get_url(self) -> str:
        """Construct the websocket URL for nCompass API."""
        return (
            f"wss://{self._api_key}.ncompass.tech/denoise/pcm/pcm/{self._api_key}"
            f"/{self._bytes_per_sample}/{self._sample_rate}/{self._out_frame_rate}"
        )

    async def start(self, sample_rate: int):
        """Initialize the filter with the given sample rate."""
        self._sample_rate = sample_rate
        try:
            if self._ws:
                return
            self._ws = await websockets.connect(self._get_url())
            logger.debug(f"Connecting to ncompass api: {self._get_url()}, {self._ws}")
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

        # Debug logging of input audio
        logger.debug(f"NCompassFilter in size={len(audio)}")

        try:
            # Send the audio chunk through websocket
            await self._ws.send(audio)
            # logger.debug("audio sent")

            # Receive denoised audio
            denoised_audio = await self._ws.recv()
            # logger.debug(f"NCompassFilter out size={len(audio)}")

            # return audio

            # # Debug logging of output audio
            # logger.debug(f"NCompassFilter out size={len(denoised_audio)}")
            return denoised_audio

        except Exception as e:
            logger.error(f"NCompassFilter exception: {e}")
            # Return the original audio to avoid blocking the VAD
            self._filtering = False
            return audio


class NCompassWebSocketService(WebsocketService):
    """
    Websocket-based service for streaming audio to nCompass's denoising API.
    Similar to ElevenLabsTTSService, but used for denoise processing.
    """

    def __init__(self, *, api_key: str, out_frame_rate: int = 16000, **kwargs):
        super().__init__()
        self._api_key = api_key
        self._out_frame_rate = out_frame_rate
        self._websocket = None
        self._receive_task = None
        self._sample_rate = 0
        self._bytes_per_sample = 2  # 16-bit linear PCM
        self._connected = False

    def _get_url(self) -> str:
        """Construct the nCompass denoise websocket URL."""
        # For example, using the same pattern as NCompassFilter:
        return (
            f"wss://{self._api_key}.ncompass.tech/denoise/pcm/pcm/{self._api_key}"
            f"/{self._bytes_per_sample}/{self._sample_rate}/{self._out_frame_rate}"
        )

    async def start(self, sample_rate: int):
        """Open the websocket connection."""
        self._sample_rate = sample_rate
        await self._connect()

    async def stop(self):
        """Close the websocket connection."""
        await self._disconnect()

    async def cancel(self, *args):
        """Cancel any ongoing operations."""
        await self._disconnect()

    async def _connect(self):
        """Establish WebSocket connection to nCompass API."""
        if self._connected:
            return
        try:
            url = self._get_url()
            logger.debug(f"Connecting to nCompass WS: {url}")
            self._websocket = await websockets.connect(url)
            self._connected = True
            # Start background task for receiving
            self._receive_task = self.create_task(self._receive_messages())
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self._websocket = None
            self._connected = False

    async def _disconnect(self):
        """Disconnect WebSocket and cancel the receive task."""
        if self._receive_task:
            await self.cancel_task(self._receive_task)
            self._receive_task = None
        if self._websocket:
            try:
                await self._websocket.close()
            except Exception as e:
                logger.error(f"Error closing nCompass WS: {e}")
            self._websocket = None
        self._connected = False

    async def _receive_messages(self):
        """Continuously receive denoised audio from nCompass."""
        try:
            async for msg in self._websocket:
                # If msg is raw audio, or base64, or something else:
                logger.debug(f"Received message of size {len(msg)} from nCompass.")
                # You can raise frames, store data, or do further processing here.
                # ...
        except Exception as e:
            logger.error(f"nCompass receiving error: {e}")

    async def run_denoise(self, audio_chunk: bytes) -> bytes:
        """
        Sends a chunk of raw audio to the server for denoising and
        returns the processed audio. Similar to 'filter' in NCompassFilter.
        """
        if not self._connected or not self._websocket:
            logger.warning("WebSocket not connected, returning original audio.")
            return audio_chunk

        try:
            await self._websocket.send(audio_chunk)
            denoised_audio = await self._websocket.recv()
            return denoised_audio
        except Exception as e:
            logger.error(f"nCompass run_denoise exception: {e}")
            return audio_chunk


class NCompassLLMService(BaseOpenAILLMService):
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: str = "llama-3.1-70B",
        base_url: str = "http://ncompass.tech",
    ):  # TODO: get this link
        super().__init__(model=model, base_url=base_url, api_key=api_key)
