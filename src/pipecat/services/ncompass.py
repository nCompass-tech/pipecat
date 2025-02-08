#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import copy
import asyncio
from typing import Optional
from dataclasses import dataclass
from pipecat.services.openai import BaseOpenAILLMService

import websockets
from typing import AsyncGenerator

from pipecat.audio.filters.base_audio_filter import BaseAudioFilter
from pipecat.frames.frames import (
    Frame,
    FilterControlFrame,
    FilterEnableFrame,
    StartFrame,
    EndFrame,
    CancelFrame,
    AudioRawFrame,
    OutputAudioRawFrame,
    STTMuteFrame,
)
from pipecat.processors.frame_processor import FrameDirection

from structlog import get_logger
from pipecat.services.ai_services import AIService
from pipecat.services.websocket_service import WebsocketService

logger = get_logger()


@dataclass
class STSMuteFrame(STTMuteFrame):
    mute: bool


class NCompassDenoiseService(AIService, WebsocketService):
    """
    Websocket-based service for streaming audio to nCompass's denoising API.
    """

    def __init__(self, *, api_key: str, out_frame_rate: int = 16000):
        super().__init__()
        self._api_key: str = api_key

        self._receive_task: Optional[asyncio.Task] = None
        self._websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._connected: bool = False

        self._out_frame_rate: int = out_frame_rate
        self._bytes_per_sample: int = 2  # 16-bit linear PCM
        self._muted: bool = False
        self._sample_rate: int = 16000
        self._audio_passthrough: bool = False
        self._num_channels: int = 1

        self._sent_message: bool = False

        self._accum_time: float = 0.14
        self._total_len: int = 0
        self._accum_audio: bytes = b""

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def muted(self) -> bool:
        return self._muted

    @property
    def audio_passthrough(self) -> bool:
        return self._audio_passthrough

    def _get_url(self) -> str:
        """Construct the nCompass denoise websocket URL."""
        return (
            f"wss://{self._api_key}.ncompass.tech/denoise/pcm/pcm/{self._api_key}"
            f"/{self._bytes_per_sample}/{self._sample_rate}/{self._out_frame_rate}"
        )

    # WebsocketService
    async def _connect(self):
        await self._connect_websocket()
        self._receive_task = self.create_task(self._receive_task_handler(self.push_error))
        # self._receive_task = self.create_task(self._receive_messages())

    async def _connect_websocket(self):
        """Establish WebSocket connection to nCompass API."""
        if self._connected:
            return
        try:
            url = self._get_url()
            logger.debug(f"Connecting to nCompass WS: {url}")
            self._websocket = await websockets.connect(url)
            self._connected = True
        except Exception as e:
            logger.error(f"{self} failed to connect with error: {e}")
            self._websocket = None
            self._connected = False

    async def _disconnect(self):
        if self._receive_task:
            await self.cancel_task(self._receive_task)
            self._receive_task = None

        await self._disconnect_websocket()

    async def _disconnect_websocket(self):
        """Disconnect WebSocket and cancel the receive task."""
        try:
            if self._websocket:
                await self._websocket.close()
                self._websocket = None
            self._started = False
            self._connected = False
        except Exception as e:
            logger.error(f"Error closing nCompass WS: {e}")

    async def _receive_messages(self):
        async for denoised_chunk in self._websocket:
            dframe = OutputAudioRawFrame(
                audio=denoised_chunk, sample_rate=self._sample_rate, num_channels=self._num_channels
            )
            await self.push_frame(dframe)

    async def start(self, frame: StartFrame):
        """Open the websocket connection."""
        await super().start(frame)
        await self._connect()
        self._sample_rate = (
            frame.audio_in_sample_rate if frame.audio_in_sample_rate > 0 else self._sample_rate
        )
        logger.debug(f"started: {frame}")

    async def stop(self, frame: EndFrame):
        """Close the websocket connection."""
        await super().stop(frame)
        await self._disconnect()

    async def cancel(self, frame: CancelFrame):
        """Cancel any ongoing operations."""
        await self._disconnect()

    async def await_denoised(self):
        while self._denoised == None:
            asyncio.sleep(0)
        return

    async def process_audio_frame(self, frame: AudioRawFrame):
        if not self.muted:
            assert self._sample_rate == frame.sample_rate
            assert self._num_channels == frame.num_channels
            await self.process_generator(self.run_denoise(frame.audio))

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, AudioRawFrame):
            if self.audio_passthrough:
                await self.push_frame(frame, direction)
            else:
                await self.process_audio_frame(frame)
        elif isinstance(frame, STSMuteFrame):
            self._muted = frame.mute
            logger.debug(f"STS service {'muted' if frame.mute else 'unmuted'}")
        else:
            await self.push_frame(frame, direction)

    @property
    def total_time(self) -> float:
        return self._total_len / (self._sample_rate * self._bytes_per_sample)

    async def accumulate_audio(self, audio_chunk: bytes):
        self._total_len += len(audio_chunk)
        self._accum_audio += audio_chunk

    async def run_denoise(self, audio_chunk: bytes) -> AsyncGenerator[Frame, None]:
        """
        Sends a chunk of raw audio to the server for denoising
        """
        try:
            if not self._websocket:
                await self._connect()

            try:
                await self.accumulate_audio(audio_chunk)
                if (self.total_time) > self._accum_time:
                    data = copy.deepcopy(self._accum_audio)
                    self._total_len = 0
                    self._accum_audio = b""
                    await self._websocket.send(data)
                    self._sent_message = True
                yield None
            except Exception as e:
                logger.error(f"{self} run-denoise send exception: {e}")
                yield None
        except Exception as e:
            logger.error(f"{self} run-denoise general exception: {e}")
            yield None
