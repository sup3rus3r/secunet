"""
OS layer execution API.
Agents submit tool execution requests here.
CC validates scope, runs the command, streams output to dashboard,
writes result to Commander context store.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status

from api.scope_enforcer import enforce
from comm_hub import broadcaster
from shared.message_schema import ExecuteRequest, ExecuteResponse
from shared.event_types import AGENT_COMMAND_RESULT, EVT_COMMAND_EXECUTION

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/execute", tags=["execution"])

COMMAND_TIMEOUT = 300  # seconds


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest) -> ExecuteResponse:
    """
    Execute a shell command on the Kali OS layer.

    Steps:
      1. Validate target against authorised scope (hard gate)
      2. Run command via subprocess
      3. Stream result to dashboard terminal feed
      4. Write to Commander context store
      5. Return result to calling agent
    """
    # 1. Scope gate — raises HTTP 403 if out of scope
    enforce(req.target)

    execution_id = str(uuid.uuid4())
    logger.info("[%s] %s → %s: %s", execution_id, req.agent_id, req.target, req.command[:100])

    # 2. Execute
    try:
        proc = await asyncio.create_subprocess_shell(
            req.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=COMMAND_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail=f"Command timed out after {COMMAND_TIMEOUT}s",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {exc}",
        )

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    exit_code = proc.returncode or 0

    response = ExecuteResponse(
        execution_id=execution_id,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        scope_validated=True,
    )

    # 3. Broadcast to dashboard terminal feed (skip for silent/internal commands)
    if not req.silent:
        await broadcaster.manager.send({
            "type":         AGENT_COMMAND_RESULT,
            "execution_id": execution_id,
            "agent_id":     req.agent_id,
            "command":      req.command,
            "target":       req.target,
            "technique":    req.technique,
            "stdout":       stdout[:2000],   # truncate for WS payload
            "stderr":       stderr[:500],
            "exit_code":    exit_code,
            "timestamp":    _now(),
        })

    # 4. Write to Commander context store (Phase 2 wires fully)
    if not req.silent:
        await _write_execution(req, response)

    return response


async def _write_execution(req: ExecuteRequest, resp: ExecuteResponse) -> None:
    try:
        from commander.write_pipeline import write_event
        await write_event(EVT_COMMAND_EXECUTION, {
            "agent_id":     req.agent_id,
            "command":      req.command,
            "target":       req.target,
            "technique":    req.technique,
            "stdout_summary": resp.stdout[:500],
            "exit_code":    resp.exit_code,
            "execution_id": resp.execution_id,
        })
    except ImportError:
        pass  # Phase 2 not built yet
