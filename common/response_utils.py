"""
response_utils.py

This module provides helper functions for processing JSON responses, decompressing and decoding 
response bodies, and normalizing text. It is designed to handle various response formats 
and handle errors gracefully by catching specific exceptions.

Main Features:
- Decompression of response bodies with support for gzip, Brotli, and deflate encodings.
- Decoding of response bodies into strings using detected or fallback encodings.
- Dumping JSON data to files with proper error handling for parsing and file operations.
- Text normalization to ensure consistent UTF-8 encoding.

Functions:
- decompress_response_body(body: Union[str, bytes], encoding: str) -> bytes:
    Decompresses a response body based on the specified encoding.

- decode_response_body(body: Union[bytes, str]) -> str:
    Decodes a response body into a string, handling different encodings and errors.

- dump_response_body_to_json(response_body: str, filename: str) -> None:
    Dumps the response body (expected to be a JSON string) into a specified file.

- clean_text(text: str) -> str:
    Normalizes and ensures the input text is properly encoded in UTF-8.

Usage:
This module is used in web scraping or API response handling scenarios where 
data needs to be processed and saved in a consistent and reliable manner.
"""

import gzip
import json
import logging
import unicodedata
import zlib
from typing import Union

import brotli
import chardet


def decompress_response_body(body: Union[str, bytes], encoding: str) -> bytes:
    """
    Decompress the response body based on the specified encoding.

    Catches more specific exceptions instead of a broad `Exception`.
    """
    if isinstance(body, str):
        body = body.encode("utf-8")
    try:
        if encoding == "gzip":
            return gzip.decompress(body)
        if encoding == "br":
            return brotli.decompress(body)
        if encoding == "deflate":
            return zlib.decompress(body)
        return body
    except (OSError, zlib.error, brotli.error, gzip.BadGzipFile) as e:
        logging.error("Error decompressing body with encoding='%s': %s", encoding, e)
        return body


def decode_response_body(body: Union[bytes, str]) -> str:
    """
    Decode the response body to a string using detected encoding, if in bytes format.

    Catches more specific exceptions instead of a broad `Exception`.
    """
    if isinstance(body, bytes):
        try:
            charset = chardet.detect(body)
            encoding = charset.get("encoding") or "utf-8"
            return body.decode(encoding, errors="replace")
        except (UnicodeDecodeError, LookupError) as e:
            logging.error("Error decoding body with auto-detected encoding: %s", e)
            # fallback to utf-8 with 'replace'
            return body.decode("utf-8", errors="replace")
    return body


def dump_response_body_to_json(response_body: str, filename: str) -> None:
    """
    Dump the response body to a JSON file.

    Catches more specific exceptions instead of a broad `Exception`.
    """
    try:
        data = json.loads(response_body)  # might raise json.JSONDecodeError
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        logging.info("Response body dumped to %s", filename)
    except json.JSONDecodeError as e:
        logging.error("Failed to parse response body as JSON: %s", e)
    except OSError as e:
        logging.error("Failed to write JSON to '%s': %s", filename, e)


def clean_text(text: str) -> str:
    """
    Ensure text is properly normalized and encoded in UTF-8.
    """
    normalized_text = unicodedata.normalize("NFC", text)
    return normalized_text
