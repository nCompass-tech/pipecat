#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

from typing import Optional
from pipecat.services.openai import BaseOpenAILLMService

class NCompassLLMService(BaseOpenAILLMService):
    def __init__(self,
                 *,
                 api_key:Optional[str]=None,
                 model:str = "llama-3.1-70B",
                 base_url:str = "http://ncompass.tech"): # TODO: get this link
        super().__init__(model=model, base_url=base_url, api_key=api_key)
