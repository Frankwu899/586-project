"""Use the macOS login Keychain without exposing credentials in process arguments."""
from __future__ import annotations

import ctypes
import sys

SERVICE = "dev.video-anatomy.openai"
ACCOUNT = "local-provider"
NOT_FOUND = -25300


class KeychainError(RuntimeError):
    """A safe, credential-free message suitable for the local settings screen."""


class MacKeychain:
    """Small Security.framework binding; the API key is never passed to a CLI.

    The default login Keychain controls encryption and access prompts. Imported
    dependencies and unsigned launchers do not change those macOS permissions.
    """

    def __init__(self):
        if sys.platform != "darwin":
            raise KeychainError("Remembering an API key requires macOS Keychain on this launcher.")
        self.security = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
        self.core = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        pointer, uint = ctypes.c_void_p, ctypes.c_uint32
        self.security.SecKeychainFindGenericPassword.argtypes = [
            pointer, uint, pointer, uint, pointer, ctypes.POINTER(uint),
            ctypes.POINTER(pointer), ctypes.POINTER(pointer),
        ]
        self.security.SecKeychainAddGenericPassword.argtypes = [
            pointer, uint, pointer, uint, pointer, uint, pointer, ctypes.POINTER(pointer),
        ]
        self.security.SecKeychainItemModifyAttributesAndData.argtypes = [pointer, pointer, uint, pointer]
        self.security.SecKeychainItemDelete.argtypes = [pointer]
        self.security.SecKeychainItemFreeContent.argtypes = [pointer, pointer]
        for name in ("SecKeychainFindGenericPassword", "SecKeychainAddGenericPassword",
                     "SecKeychainItemModifyAttributesAndData", "SecKeychainItemDelete",
                     "SecKeychainItemFreeContent"):
            getattr(self.security, name).restype = ctypes.c_int32
        self.core.CFRelease.argtypes = [pointer]
        self.core.CFRelease.restype = None

    @staticmethod
    def _check(status: int) -> None:
        if status:
            raise KeychainError(
                "macOS Keychain could not complete the request. Unlock the login Keychain "
                "and allow Video Anatomy access, or use the key for this session only."
            )

    def _find(self, *, read: bool):
        service, account = SERVICE.encode(), ACCOUNT.encode()
        size, data, item = ctypes.c_uint32(), ctypes.c_void_p(), ctypes.c_void_p()
        status = self.security.SecKeychainFindGenericPassword(
            None, len(service), service, len(account), account,
            ctypes.byref(size) if read else None,
            ctypes.byref(data) if read else None, ctypes.byref(item),
        )
        return status, size, data, item

    def get(self) -> str | None:
        status, size, data, item = self._find(read=True)
        try:
            if status == NOT_FOUND:
                return None
            self._check(status)
            try:
                return ctypes.string_at(data, size.value).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise KeychainError("The saved API key could not be read. Replace it in API settings.") from exc
        finally:
            if data:
                self.security.SecKeychainItemFreeContent(None, data)
            if item:
                self.core.CFRelease(item)

    def set(self, key: str) -> None:
        if not key or not key.isascii() or any(character.isspace() for character in key):
            raise KeychainError("Enter the complete API key without spaces.")
        encoded = key.encode()
        status, _, _, item = self._find(read=False)
        try:
            if status == NOT_FOUND:
                service, account = SERVICE.encode(), ACCOUNT.encode()
                self._check(self.security.SecKeychainAddGenericPassword(
                    None, len(service), service, len(account), account,
                    len(encoded), encoded, None,
                ))
            else:
                self._check(status)
                self._check(self.security.SecKeychainItemModifyAttributesAndData(
                    item, None, len(encoded), encoded,
                ))
        finally:
            if item:
                self.core.CFRelease(item)

    def delete(self) -> None:
        status, _, _, item = self._find(read=False)
        try:
            if status == NOT_FOUND:
                return
            self._check(status)
            self._check(self.security.SecKeychainItemDelete(item))
        finally:
            if item:
                self.core.CFRelease(item)
