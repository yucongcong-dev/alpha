"""Windows DPAPI helpers for current-user secret protection."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from typing import Any, cast

from ..exceptions import BrainAPIError

_CRYPTPROTECT_UI_FORBIDDEN = 0x01
_DPAPI_DESCRIPTION = "alpha local credentials key"


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _windows_libraries() -> tuple[Any, Any]:
    if os.name != "nt":
        raise BrainAPIError("Windows DPAPI is only available on Windows.")

    crypt32 = cast(Any, ctypes.WinDLL("crypt32", use_last_error=True))
    kernel32 = cast(Any, ctypes.WinDLL("kernel32", use_last_error=True))
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    return crypt32, kernel32


def _input_blob(data: bytes) -> tuple[_DataBlob, Any]:
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    blob = _DataBlob(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return blob, buffer


def _raise_dpapi_error(operation: str) -> None:
    error_code = ctypes.get_last_error()
    message = ctypes.FormatError(error_code).strip()
    raise BrainAPIError(
        f"Windows DPAPI failed to {operation} credentials key "
        f"(error {error_code}: {message})."
    )


def _copy_and_free_output(blob: _DataBlob, kernel32: Any) -> bytes:
    try:
        return bytes(ctypes.string_at(blob.pbData, blob.cbData))
    finally:
        if blob.pbData:
            kernel32.LocalFree(ctypes.cast(blob.pbData, ctypes.c_void_p))


def protect_for_current_user(secret: bytes) -> bytes:
    """Protect bytes with Windows DPAPI bound to the current user profile."""
    if not secret:
        raise BrainAPIError("Cannot protect an empty credentials key with Windows DPAPI.")

    crypt32, kernel32 = _windows_libraries()
    input_blob, input_buffer = _input_blob(secret)
    output_blob = _DataBlob()
    _ = input_buffer
    if not crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        _DPAPI_DESCRIPTION,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    ):
        _raise_dpapi_error("protect")
    return _copy_and_free_output(output_blob, kernel32)


def unprotect_for_current_user(protected_secret: bytes) -> bytes:
    """Unprotect DPAPI bytes for the current Windows user profile."""
    if not protected_secret:
        raise BrainAPIError("Windows DPAPI credentials key payload is empty.")

    crypt32, kernel32 = _windows_libraries()
    input_blob, input_buffer = _input_blob(protected_secret)
    output_blob = _DataBlob()
    _ = input_buffer
    if not crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    ):
        _raise_dpapi_error("unprotect")
    return _copy_and_free_output(output_blob, kernel32)
