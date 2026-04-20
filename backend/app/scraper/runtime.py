"""Runtime shared state for scraper package."""

import threading

sqlite_write_lock = threading.Lock()
