"""
WebSocket server + HTTP file server for live dashboard.

Serves static HTML/CSS/JS files and provides WebSocket endpoint for real-time updates.
Runs in background threads to not block main execution.
"""

import asyncio
import websockets
import threading
import os
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from . import dashboard_events
DashboardEventEmitter = dashboard_events.DashboardEventEmitter


class DashboardServer:
    """
    Dual server for dashboard: HTTP for static files + WebSocket for events.

    Runs both servers in background threads, non-blocking to main execution.
    """

    def __init__(self, http_port: int = 3000, ws_port: int = 3001):
        """
        Initialize dashboard server.

        Args:
            http_port: Port for HTTP static file server (default: 3000)
            ws_port: Port for WebSocket event server (default: 3001)
        """
        self.http_port = http_port
        self.ws_port = ws_port
        self.running = False
        self.ws_server = None
        self.http_server = None
        self.loop = None

    async def websocket_handler(self, websocket, path):
        """
        Handle WebSocket connection.

        Registers client with event emitter and keeps connection alive.
        """
        # Register this client for event broadcasts
        DashboardEventEmitter.add_client(websocket)

        try:
            # Keep connection alive until client disconnects
            await websocket.wait_closed()
        finally:
            # Cleanup on disconnect
            DashboardEventEmitter.remove_client(websocket)

    def start(self):
        """Start both HTTP and WebSocket servers in background threads."""
        if self.running:
            return

        self.running = True

        # Start HTTP server for static files
        http_thread = threading.Thread(target=self._run_http_server, daemon=True)
        http_thread.start()

        # Start WebSocket server for events
        ws_thread = threading.Thread(target=self._run_ws_server, daemon=True)
        ws_thread.start()

        print(f"🌊 Dashboard running at http://localhost:{self.http_port}")
        print(f"🔌 WebSocket at ws://localhost:{self.ws_port}")

    def _run_http_server(self):
        """Run HTTP server for static files (blocks in thread)."""
        # Change to dashboard directory to serve files
        dashboard_dir = Path(__file__).parent / "dashboard"
        dashboard_dir.mkdir(exist_ok=True)
        os.chdir(dashboard_dir)

        # Start HTTP server
        self.http_server = HTTPServer(("localhost", self.http_port), SimpleHTTPRequestHandler)
        self.http_server.serve_forever()

    def _run_ws_server(self):
        """Run WebSocket server for events (blocks in thread)."""
        # Create new event loop for this thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Enable event emitter with this loop
        DashboardEventEmitter.enable(self.loop)

        # Start WebSocket server
        start_server = websockets.serve(
            self.websocket_handler,
            "localhost",
            self.ws_port
        )

        self.loop.run_until_complete(start_server)
        self.loop.run_forever()

    def stop(self):
        """Stop both servers."""
        self.running = False

        if self.http_server:
            self.http_server.shutdown()

        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)

        DashboardEventEmitter.disable()
