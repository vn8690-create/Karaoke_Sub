"""
Pipeline executors for running stages in different contexts.

Executors handle the actual execution of pipeline stages, providing
different implementations for different execution contexts:

- LocalExecutor: Runs stages directly in-process (for CLI)
- RemoteExecutor: Runs stages via backend API (for remote CLI)

Both executors use the same stage interface, ensuring consistent
behavior regardless of execution context.
"""
from karaoke_gen.pipeline.executors.local import LocalExecutor, create_local_executor
from karaoke_gen.pipeline.executors.remote import RemoteExecutor, create_remote_executor

__all__ = [
    "LocalExecutor",
    "RemoteExecutor",
    "create_local_executor",
    "create_remote_executor",
]
