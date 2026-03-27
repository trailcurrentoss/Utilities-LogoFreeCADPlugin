# -*- coding: utf-8 -*-
"""XML-RPC server that runs inside FreeCAD to expose its Python environment.

This server runs in a background thread and marshals code execution to
FreeCAD's main (GUI) thread via a QTimer-polled queue, ensuring all
FreeCAD/Part/Gui operations execute safely.
"""

import io
import json
import queue
import sys
import threading
import traceback
from xmlrpc.server import SimpleXMLRPCServer

import FreeCAD

DEFAULT_PORT = 12785

_server = None
_server_thread = None
_exec_queue = queue.Queue()
_timer = None
_namespace = {}


def _init_namespace():
    """Pre-import common FreeCAD modules into the execution namespace."""
    for alias, module_name in [
        ("FreeCAD", "FreeCAD"), ("App", "FreeCAD"),
        ("FreeCADGui", "FreeCADGui"), ("Gui", "FreeCADGui"),
        ("Part", "Part"), ("Mesh", "Mesh"), ("Draft", "Draft"),
        ("Sketcher", "Sketcher"), ("PartDesign", "PartDesign"),
        ("Import", "Import"), ("importSVG", "importSVG"),
        ("BOPTools", "BOPTools"),
    ]:
        try:
            _namespace[alias] = __import__(module_name)
        except ImportError:
            pass
    # Convenience builtins
    import builtins
    _namespace["__builtins__"] = builtins


def _process_queue():
    """Called on the main thread by QTimer. Executes queued code."""
    while not _exec_queue.empty():
        try:
            code, timeout_event, container = _exec_queue.get_nowait()
        except queue.Empty:
            break

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        old_stdout, old_stderr = sys.stdout, sys.stderr

        try:
            sys.stdout = stdout_buf
            sys.stderr = stderr_buf

            # Try as single expression first (returns a value)
            try:
                compiled = compile(code, "<mcp>", "eval")
                result = eval(compiled, _namespace)
                if result is not None:
                    container["result"] = repr(result)
            except SyntaxError:
                # Fall back to statement execution
                compiled = compile(code, "<mcp>", "exec")
                exec(compiled, _namespace)

        except Exception:
            container["error"] = traceback.format_exc()
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        stdout_val = stdout_buf.getvalue()
        stderr_val = stderr_buf.getvalue()
        if stdout_val:
            container["stdout"] = stdout_val
        if stderr_val:
            container["stderr"] = stderr_val

        timeout_event.set()


# ── RPC-exposed methods ────────────────────────────────────────────

def ping():
    """Health check."""
    return True


def execute(code, timeout=60):
    """Execute Python code on FreeCAD's main thread.

    Returns a dict with optional keys: result, stdout, stderr, error.
    """
    event = threading.Event()
    container = {}
    _exec_queue.put((code, event, container))
    if not event.wait(timeout=timeout):
        return {"error": "Execution timed out after {}s".format(timeout)}
    return container


# ── Server lifecycle ───────────────────────────────────────────────

def start(port=DEFAULT_PORT):
    """Start the RPC server. Returns True on success, False if already running."""
    global _server, _server_thread, _timer

    if _server is not None:
        FreeCAD.Console.PrintWarning(
            "MCP RPC server is already running on port {}\n".format(port)
        )
        return False

    _init_namespace()

    # Use allow_reuse_address so the port can be rebound after
    # unclean shutdown without waiting for TIME_WAIT to expire.
    SimpleXMLRPCServer.allow_reuse_address = True
    try:
        _server = SimpleXMLRPCServer(
            ("127.0.0.1", port),
            allow_none=True,
            logRequests=False,
        )
    except OSError as e:
        FreeCAD.Console.PrintError(
            "MCP RPC server failed to start on port {}: {}\n".format(port, e)
        )
        return False
    _server.register_function(execute, "execute")
    _server.register_function(ping, "ping")

    _server_thread = threading.Thread(
        target=_server.serve_forever, daemon=True
    )
    _server_thread.start()

    # QTimer to poll the execution queue on the main thread
    from PySide import QtCore  # noqa: PySide ships with FreeCAD

    _timer = QtCore.QTimer()
    _timer.timeout.connect(_process_queue)
    _timer.start(50)  # 50 ms polling interval

    FreeCAD.Console.PrintMessage(
        "MCP RPC server started on 127.0.0.1:{}\n".format(port)
    )
    return True


def stop():
    """Stop the RPC server. Returns True on success."""
    global _server, _server_thread, _timer

    if _server is None:
        return False

    if _timer is not None:
        _timer.stop()
        _timer = None

    _server.shutdown()
    _server = None
    _server_thread = None

    FreeCAD.Console.PrintMessage("MCP RPC server stopped\n")
    return True


def is_running():
    return _server is not None
