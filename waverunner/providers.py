"""
LLM provider abstraction for waverunner.

Allows swapping between different LLM backends (Claude Code CLI, Anthropic API, OpenAI, etc.)
"""

from abc import ABC, abstractmethod
from typing import Optional
import subprocess
import sys
import os
import time
import fcntl
import select


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def run(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[int] = None,
        mcps: Optional[list[str]] = None,
        show_spinner: bool = True,
        verbose: bool = False,
        task=None,  # Optional Task being executed (for Reaper monitoring)
        persona=None,  # Optional Persona executing (for Reaper monitoring)
        progress_callback=None,  # Optional callback(progress_pct, output_line) for live updates
    ) -> str:
        """
        Run the LLM with a prompt and return the response.

        Args:
            prompt: The user prompt to send
            system_prompt: Optional system prompt
            timeout: Timeout in seconds
            mcps: List of MCP config strings/paths to inject
            show_spinner: Show spinner during execution
            verbose: Show detailed output
            progress_callback: Optional callback for progress updates

        Returns:
            The LLM's response as a string
        """
        pass


class ClaudeCodeProvider(LLMProvider):
    """Provider for Claude Code CLI."""

    def run(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[int] = None,
        mcps: Optional[list[str]] = None,
        show_spinner: bool = True,
        verbose: bool = False,
        task=None,
        persona=None,
        progress_callback=None,
    ) -> str:
        """Run Claude Code CLI with a prompt."""
        cmd = ["claude", "-p", "--dangerously-skip-permissions"]

        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])

        # Inject MCPs if provided
        if mcps:
            for mcp in mcps:
                cmd.extend(["--mcp-config", mcp])

        # Don't append prompt to cmd - we'll pipe it via stdin to avoid ARG_MAX limits

        # Debug: show command being run
        if verbose:
            from . import ui
            ui.console.print(f"[{ui.DIM}]Running: {' '.join(cmd)} (prompt via stdin)[/]")

        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=os.getcwd(),
                bufsize=1,
            )

            # Write prompt to stdin immediately and close it
            process.stdin.write(prompt)
            process.stdin.close()

            output_lines = []
            start_time = time.time()
            last_output_time = start_time
            last_reaper_check = start_time
            spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
            spinner_idx = 0

            # Set stdout to non-blocking and save original flags for restoration
            fd = process.stdout.fileno()
            original_fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, original_fl | os.O_NONBLOCK)

            while True:
                now = time.time()
                elapsed = int(now - start_time)

                # Check timeout (if set)
                if timeout and now - start_time > timeout:
                    process.kill()
                    print(f"\n[Timeout after {timeout}s - killed process]")
                    break

                # Reaper monitoring (if task/persona provided)
                # CRITICAL: Check if process is still alive BEFORE calling Reaper
                # If process finished, don't invoke Reaper on a dead process
                if task and persona and now - last_reaper_check >= 30:  # Check every 30s
                    # Check if process is still running
                    if process.poll() is None:  # None = still running
                        from . import agent
                        silence_seconds = int(now - last_output_time)
                        elapsed_seconds = int(now - start_time)

                        # Pass recent output and process PID for hybrid detection
                        action, reason = agent.reaper_monitor_task(
                            task, persona, silence_seconds, elapsed_seconds,
                            recent_output=output_lines,  # Pass output for context
                            process_pid=process.pid  # For CPU monitoring
                        )
                        last_reaper_check = now

                        if action == "KILL":
                            process.kill()
                            print(f"\n\033[91m⚰ THE REAPER HAS TERMINATED THIS TASK ⚰\033[0m")
                            print(f"\033[91m{reason}\033[0m\n")

                            # Let persona give death cry
                            death_cry = agent.agent_generate_death_cry(persona, task, reason)
                            print(f"\033[2m{persona.name}: {death_cry}\033[0m\n")
                            raise RuntimeError(f"Task killed by Reaper: {reason}")
                    else:
                        # Process finished - update last check time to avoid triggering on next iteration
                        last_reaper_check = now

                # Check if process is done
                retcode = process.poll()

                # Try to read available output
                got_output = False
                try:
                    ready, _, _ = select.select([process.stdout], [], [], 0.5)
                    if ready:
                        line = process.stdout.readline()
                        if line:
                            output_lines.append(line)
                            got_output = True
                            last_output_time = now
                            # Only print live output in verbose mode
                            if verbose:
                                print(f"\r\033[K{line}", end='', flush=True)

                            # Call progress callback with output
                            if progress_callback:
                                # Estimate progress based on time elapsed and output activity
                                # Simple heuristic: more output = more progress
                                progress_estimate = min(90, int((elapsed / 60) * 30 + len(output_lines) * 2))
                                progress_callback(progress_estimate, line.strip())
                except (IOError, OSError):
                    pass

                # Update progress even without output (heartbeat every 2 seconds)
                if progress_callback and not got_output and int(elapsed) % 2 == 0:
                    # Base progress on time: start at 10%, grow slowly to max 85%
                    base_progress = min(85, 10 + int(elapsed / 10))
                    # Add bonus for any output we've seen
                    output_bonus = min(20, len(output_lines))
                    progress_estimate = min(90, base_progress + output_bonus)
                    progress_callback(progress_estimate, "")

                # Show spinner based on mode
                if not got_output and retcode is None:
                    if verbose or show_spinner:
                        spinner = spinner_chars[spinner_idx % len(spinner_chars)]
                        silence = int(now - last_output_time)

                        # Color code by silence duration (helps spot hung agents)
                        if silence > 120:  # 2+ min silence - might be hung
                            status_color = '\033[91m'  # Red
                            status = '⚠ QUIET'
                        elif silence > 60:  # 1+ min silence - concerning
                            status_color = '\033[93m'  # Yellow
                            status = '⚠'
                        else:  # Normal activity
                            status_color = '\033[0m'  # Normal
                            status = ''

                        if verbose:
                            print(f"\r{spinner} Working... ({elapsed}s elapsed, {silence}s since last output) {status_color}{status}\033[0m", end='', flush=True)
                        else:
                            # Non-verbose now shows silence time too
                            print(f"\r{spinner} Working... ({elapsed}s, {silence}s quiet) {status_color}{status}\033[0m", end='', flush=True)
                        spinner_idx += 1

                # Exit if process is done and no more output
                if retcode is not None:
                    if verbose or show_spinner:
                        print("\r\033[K", end='')  # Clear spinner line
                    # Drain remaining output
                    try:
                        remaining = process.stdout.read()
                        if remaining:
                            output_lines.append(remaining)
                            if verbose:
                                print(remaining, end='', flush=True)
                    except Exception:
                        pass
                    break

            # Restore original file descriptor flags
            try:
                fcntl.fcntl(fd, fcntl.F_SETFL, original_fl)
            except Exception:
                pass  # Process might be closed, ignore

            if process.returncode and process.returncode != 0:
                print(f"\n[Claude exited with code {process.returncode}]")

                if process.returncode == -9:
                    print("\n" + "="*60)
                    print("CRITICAL: Process killed by system (SIGKILL)")
                    print("="*60)
                    print("\nThis usually means:")
                    print("  • Out of Memory (OOM) - System ran out of RAM")
                    print("  • Too many parallel processes consuming resources")
                    print("  • System resource limits hit (ulimit)")
                    print("\nDiagnostic commands:")
                    print("  free -h                    # Check available memory")
                    print("  dmesg | grep -i killed     # Check if OOM killer ran")
                    print("  ulimit -a                  # Check resource limits")
                    print("\nSolutions:")
                    print("  1. Reduce parallelism: Add --max-parallel 1")
                    print("  2. Increase system memory")
                    print("  3. Close other memory-intensive applications")
                    print("  4. Check: ps aux | grep claude  # Kill stuck processes")
                    print("="*60 + "\n")
                    raise RuntimeError("Claude process killed by system (exit -9) - likely out of memory")

                elif process.returncode == 1:
                    print("\nPossible causes:")
                    print("  - Not authenticated: Run 'claude auth' to log in")
                    print("  - API key issue: Check your Anthropic API key")
                    print("  - Network error: Check your internet connection")
                    print("  - Rate limit: You may have hit API rate limits\n")

                elif process.returncode < 0:
                    # Negative exit codes are signals (killed by system)
                    signal_num = -process.returncode
                    print(f"\nProcess killed by signal {signal_num}")
                    print("This indicates the process was terminated externally.")
                    print("Run: kill -l  # To see signal names\n")
                    raise RuntimeError(f"Claude process killed by signal {signal_num}")

            return ''.join(output_lines)

        except FileNotFoundError:
            print("\n" + "="*60)
            print("ERROR: Claude Code CLI not found")
            print("="*60)
            print("\nWaverunner requires the Claude Code CLI to be installed.")
            print("\nInstallation:")
            print("  npm install -g @anthropic-ai/claude-code")
            print("\nOr visit: https://github.com/anthropics/claude-code")
            print("\nAfter installing, you'll need to authenticate:")
            print("  claude auth")
            print("\n" + "="*60 + "\n")
            sys.exit(1)
        except KeyboardInterrupt:
            # Only kill if process was created
            if 'process' in locals() and process.poll() is None:
                process.kill()
            print("\n[Interrupted]")
            sys.exit(1)


class AnthropicAPIProvider(LLMProvider):
    """Provider for Anthropic API (direct SDK usage with prompt caching)."""

    def __init__(self):
        """Initialize Anthropic API client."""
        import anthropic
        import os

        # Check for API key
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Set it in your ~/.bashrc or shell config:\n"
                "  export ANTHROPIC_API_KEY='your-api-key-here'"
            )

        self.client = anthropic.Anthropic(api_key=api_key)

    def run(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[int] = None,
        mcps: Optional[list[str]] = None,
        show_spinner: bool = True,
        verbose: bool = False,
        task=None,
        persona=None,
        progress_callback=None,
    ) -> str:
        """
        Run Anthropic API with structured messages and prompt caching.

        Uses message arrays instead of flat strings, enabling prompt caching
        for system prompts and repeated context.
        """
        # Build structured messages
        messages = [
            {"role": "user", "content": prompt}
        ]

        # Build system message with caching
        system_messages = None
        if system_prompt:
            system_messages = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}  # Cache system prompt
                }
            ]

        # Build API call kwargs
        api_kwargs = {
            "model": "claude-sonnet-4-5-20250929",
            "max_tokens": 8192,
            "messages": messages,
        }

        if system_messages:
            api_kwargs["system"] = system_messages

        if timeout:
            api_kwargs["timeout"] = timeout

        # Note: MCP support via API would require implementing the MCP protocol
        # For now, if MCPs are requested, log a warning
        if mcps and verbose:
            print("[Warning: MCP configs not yet supported in Anthropic API provider]")

        try:
            # Show spinner if requested
            if show_spinner and not verbose:
                print("⏳ Calling Anthropic API...", end="", flush=True)

            # Make API call
            response = self.client.messages.create(**api_kwargs)

            # Clear spinner
            if show_spinner and not verbose:
                print("\r\033[K", end="")  # Clear line

            # Extract text from response
            if response.content and len(response.content) > 0:
                return response.content[0].text
            else:
                return ""

        except Exception as e:
            # Clear spinner on error
            if show_spinner and not verbose:
                print("\r\033[K", end="")

            # Re-raise with context
            raise Exception(f"Anthropic API error: {e}") from e


class MockLLMProvider(LLMProvider):
    """Mock provider for testing. Returns predefined responses."""

    def __init__(self, responses: Optional[dict[str, str]] = None):
        """
        Initialize mock provider.

        Args:
            responses: Dict mapping prompt substrings to canned responses
        """
        self.responses = responses or {}
        self.call_count = 0
        self.last_prompt = None
        self.last_system_prompt = None

    def run(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[int] = None,
        mcps: Optional[list[str]] = None,
        show_spinner: bool = True,
        verbose: bool = False,
        task=None,
        persona=None,
        progress_callback=None,
    ) -> str:
        """Return a canned response based on prompt content."""
        self.call_count += 1
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt

        # Match prompt to response
        for key, response in self.responses.items():
            if key in prompt:
                return response

        # Default response if no match
        return """```yaml
tasks:
  - id: "mock-task-1"
    title: "Mock task"
    description: "A mock task for testing"
    complexity: small
    priority: medium
    acceptance_criteria:
      - "Task completes"
    dependencies: []
```"""


# Default provider factory
def get_provider(provider_name: str = "claude-code") -> LLMProvider:
    """
    Get an LLM provider by name.

    Args:
        provider_name: Name of the provider (claude-code, anthropic-api, mock)

    Returns:
        LLMProvider instance
    """
    if provider_name == "claude-code":
        return ClaudeCodeProvider()
    elif provider_name == "anthropic-api":
        return AnthropicAPIProvider()
    elif provider_name == "mock":
        return MockLLMProvider()
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
