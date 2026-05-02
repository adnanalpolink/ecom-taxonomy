"""API functions for the app."""
from __future__ import annotations

import concurrent.futures
from typing import List, Union

import numpy as np
from loguru import logger
from openai import OpenAI
from tenacity import (
    RetryError,
    retry,
    stop_after_attempt,
    wait_random_exponential,
)
from tqdm import tqdm

from taxonomyml import settings
from taxonomyml.exceptions import APIError, MissingAPIKeyError, OpenAIError


def _get_client(openai_api_key: str | None = None) -> OpenAI:
    """Create an OpenAI client instance."""
    api_key = openai_api_key or settings.OPENAI_API_KEY
    if not api_key:
        raise MissingAPIKeyError()
    return OpenAI(api_key=api_key)


@retry(
    wait=wait_random_exponential(min=5, max=60),
    stop=stop_after_attempt(settings.API_RETRY_ATTEMPTS),
)
def get_openai_response(
    messages: List[dict],
    model: str = "gpt-5.4-mini",
    openai_api_key: str | None = None,
) -> Union[str, None]:
    """Get a response from OpenAI's API."""

    client = _get_client(openai_api_key)

    try:
        chat_completion = client.chat.completions.create(
            model=model,
            messages=messages,
            timeout=settings.OPENAI_REQUEST_TIMEOUT,
            max_completion_tokens=4096,
            frequency_penalty=0.2,
            temperature=0.0,
            n=1,
        )

    except Exception as e:
        logger.error("OpenAI API Error: " + str(e))
        logger.info("Messages: " + str(messages))
        raise OpenAIError(str(e))

    return chat_completion.choices[0].message.content


def get_openai_response_chat(
    messages: List[dict] | str,
    model: str = settings.OPENAI_QUALITY_MODEL,
    system_message: dict | str = "You are an expert taxonomy creator.",
    openai_api_key: str | None = None,
) -> Union[str, None]:
    """Get a response from OpenAI's chat API."""

    system_message = {"role": "system", "content": system_message}

    if isinstance(messages, str):
        messages = [system_message, {"role": "user", "content": messages}]
    else:
        messages = [system_message] + messages

    try:
        return get_openai_response(messages, model=model, openai_api_key=openai_api_key)

    except RetryError as e:
        # Extract the actual error from the last retry attempt
        last_error = e.last_attempt.exception() if e.last_attempt else e
        error_msg = f"OpenAI API failed after {settings.API_RETRY_ATTEMPTS} retries. Model: '{model}'. Error: {last_error}"
        logger.error(error_msg)
        raise APIError(error_msg)


def get_openai_embeddings(
    texts: List[str],
    model: str = settings.OPENAI_EMBEDDING_MODEL,
    n_jobs: int = settings.MAX_WORKERS,
    openai_api_key: str | None = None,
) -> np.ndarray:
    """Get embeddings from OpenAI's API."""
    client = _get_client(openai_api_key)

    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(settings.API_RETRY_ATTEMPTS),
    )
    def get_single_embedding(text: str, model: str) -> np.ndarray:
        response = client.embeddings.create(input=[text], model=model)
        return np.asarray(response.data[0].embedding)

    # Multi-thread with concurrent.futures and return in same order as texts
    embeddings_lookup = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=n_jobs) as executor:
        futures = {
            executor.submit(get_single_embedding, text, model): text for text in texts
        }

        for future in tqdm(
            concurrent.futures.as_completed(futures),
            desc="Getting OpenAI Embeddings",
            total=len(futures),
        ):
            embeddings_lookup[futures[future]] = future.result()

    return np.asarray([embeddings_lookup[text] for text in texts])
