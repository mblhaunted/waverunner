"""
Event emission system for live dashboard updates.

Provides a singleton event emitter that broadcasts events to connected WebSocket clients.
Safe to call even when dashboard is disabled - no-op until enabled.
"""

import json
import time
import asyncio
from typing import Optional, Set, Any


class DashboardEventEmitter:
    """
    Singleton event emitter for WebSocket broadcast.

    Thread-safe event emission that broadcasts to all connected WebSocket clients.
    Disabled by default - enable with enable() when --dashboard flag is used.
    """
    _enabled: bool = False
    _clients: Set[Any] = set()
    _loop: Optional[asyncio.AbstractEventLoop] = None

    @classmethod
    def enable(cls, loop: Optional[asyncio.AbstractEventLoop] = None):
        """Enable dashboard event emission."""
        cls._enabled = True
        cls._loop = loop

    @classmethod
    def disable(cls):
        """Disable dashboard event emission."""
        cls._enabled = False
        cls._clients.clear()
        cls._loop = None

    @classmethod
    def add_client(cls, client: Any):
        """Register a WebSocket client for event broadcasts."""
        cls._clients.add(client)

    @classmethod
    def remove_client(cls, client: Any):
        """Unregister a WebSocket client."""
        cls._clients.discard(client)

    @classmethod
    def emit(cls, event_type: str, data: dict):
        """
        Emit event to all connected clients.

        No-op if dashboard is disabled or no clients connected.
        Thread-safe - can be called from any thread.

        Args:
            event_type: Type of event (e.g., "task_started", "wave_started")
            data: Event payload as dictionary
        """
        # Fast return if disabled or no clients
        if not cls._enabled or not cls._clients:
            return

        message = json.dumps({
            "type": event_type,
            "timestamp": time.time(),
            "data": data
        })

        # Broadcast to all clients (thread-safe via asyncio)
        if cls._loop and cls._clients:
            # Schedule broadcast on the event loop
            for client in list(cls._clients):  # Copy to avoid modification during iteration
                try:
                    asyncio.run_coroutine_threadsafe(
                        client.send(message),
                        cls._loop
                    )
                except Exception:
                    # Client disconnected or error - remove it
                    cls._clients.discard(client)
