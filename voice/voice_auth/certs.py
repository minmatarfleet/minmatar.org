"""Serve the Let's Encrypt certificate for voice.minmatar.org.

Loaded with Ice ``updateCertificate`` at start and whenever certbot renews
the files, so renewals need no deploy hook and drop no connections.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class CertWatcher:
    def __init__(self, ice, cert_file: str, key_file: str):
        self.ice = ice
        self.cert_file = cert_file
        self.key_file = key_file
        self._stamp = None

    def _current_stamp(self):
        try:
            return (
                os.stat(self.cert_file).st_mtime_ns,
                os.stat(self.key_file).st_mtime_ns,
            )
        except OSError:
            return None

    def check(self, force: bool = False) -> bool:
        """Load the certificate if it changed. True when it was loaded."""
        if not self.cert_file or not self.key_file:
            return False
        stamp = self._current_stamp()
        if stamp is None or (stamp == self._stamp and not force):
            return False
        with open(self.cert_file, encoding="ascii") as cert, open(
            self.key_file, encoding="ascii"
        ) as key:
            self.ice.update_certificate(cert.read(), key.read())
        self._stamp = stamp
        logger.info("Loaded the voice server certificate")
        return True
