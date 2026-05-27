"""
Jenkins MCP Server

A Model Context Protocol server for interacting with Jenkins CI/CD.
Provides tools for listing jobs, triggering builds, viewing logs, and more.

Environment Variables:
    JENKINS_URL: Jenkins base URL (e.g. https://jenkins.example.com)
    JENKINS_USER: Jenkins username
    JENKINS_TOKEN: Jenkins API token
    JENKINS_FOLDER: Jenkins folder name (default: oa)
"""

import asyncio
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

JENKINS_URL = os.getenv("JENKINS_URL", "")
JENKINS_USER = os.getenv("JENKINS_USER", "")
JENKINS_TOKEN = os.getenv("JENKINS_TOKEN", "")
JENKINS_FOLDER = os.getenv("JENKINS_FOLDER", "")

CHARACTER_LIMIT = 25000

# Password-like parameter names that should be masked in output.
MASKED_PARAM_NAMES = frozenset({
    "registry_password",
    "password",
    "token",
    "secret",
    "nexus_npm_auth",
})

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class JobNameInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    job_name: str = Field(..., description="Jenkins job name (e.g. oa-platform-php)")


class BuildNumberInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    job_name: str = Field(..., description="Jenkins job name")
    build_number: int = Field(..., description="Build number")


class BuildLogInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    job_name: str = Field(..., description="Jenkins job name")
    build_number: int = Field(..., description="Build number")
    tail: int = Field(
        default=200,
        ge=1,
        le=5000,
        description="Number of lines to return from the end of the log (default 200)",
    )


class TriggerBuildInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    job_name: str = Field(..., description="Jenkins job name to trigger")
    parameters: dict[str, str] = Field(
        default_factory=dict,
        description="Build parameters as key-value pairs",
    )


class BuildAndWatchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    job_name: str = Field(..., description="Jenkins job name to trigger")
    parameters: dict[str, str] = Field(
        default_factory=dict,
        description="Build parameters as key-value pairs",
    )
    poll_interval: int = Field(
        default=10,
        ge=3,
        le=60,
        description="Seconds between status checks (default 10)",
    )
    timeout_seconds: int = Field(
        default=600,
        ge=30,
        le=1800,
        description="Maximum seconds to wait for build completion (default 600)",
    )


class CancelBuildInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    job_name: str = Field(..., description="Jenkins job name")
    build_number: int = Field(..., description="Build number to cancel")


class CompareBuildsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    job_name: str = Field(..., description="Jenkins job name")
    build_number_a: int = Field(..., description="First build number")
    build_number_b: int = Field(..., description="Second build number")


class TestReportInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    job_name: str = Field(..., description="Jenkins job name")
    build_number: int = Field(..., description="Build number")


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP("jenkins-mcp")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _job_url(job_name: str) -> str:
    """Build the API URL for a job. Uses folder path if JENKINS_FOLDER is set."""
    if JENKINS_FOLDER:
        return f"{JENKINS_URL}/job/{JENKINS_FOLDER}/job/{job_name}"
    return f"{JENKINS_URL}/job/{job_name}"


def _auth() -> tuple[str, str]:
    if not JENKINS_URL:
        raise ValueError(
            "JENKINS_URL is not set. Please set it via environment variable "
            "or run: jenkins-mcp-config"
        )
    if not JENKINS_USER or not JENKINS_TOKEN:
        raise ValueError(
            "JENKINS_USER and JENKINS_TOKEN environment variables must be set. "
            "Generate your API token at: {JENKINS_URL}/user/{JENKINS_USER}/configure"
        )
    return (JENKINS_USER, JENKINS_TOKEN)


def _headers() -> dict[str, str]:
    return {"Accept": "application/json"}


def _mask_params(params: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of params with password-like values masked."""
    masked = {}
    for key, value in params.items():
        if key.lower() in MASKED_PARAM_NAMES:
            masked[key] = "***"
        else:
            masked[key] = value
    return masked


def _format_timestamp(ts_ms: Optional[int]) -> str:
    """Convert a Jenkins epoch-millis timestamp to a human-readable string."""
    if ts_ms is None or ts_ms == 0:
        return "N/A"
    try:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, OSError):
        return "N/A"


def _format_duration(ms: Optional[int]) -> str:
    """Convert duration in milliseconds to a human-readable string."""
    if ms is None or ms == 0:
        return "N/A"
    seconds = ms // 1000
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {seconds}s"


def _truncate(text: str) -> str:
    """Truncate text to CHARACTER_LIMIT."""
    if len(text) <= CHARACTER_LIMIT:
        return text
    return text[:CHARACTER_LIMIT] + "\n\n... [truncated]"


async def _make_request(
    method: str,
    url: str,
    *,
    follow_redirects: bool = True,
    **kwargs: Any,
) -> httpx.Response:
    """Make an authenticated HTTP request to Jenkins."""
    async with httpx.AsyncClient(verify=False, follow_redirects=follow_redirects) as client:
        response = await client.request(
            method,
            url,
            auth=_auth(),
            headers=_headers(),
            **kwargs,
        )
        response.raise_for_status()
        return response


async def _get_crumb() -> dict[str, str]:
    """Fetch a CSRF crumb from Jenkins for POST requests."""
    response = await _make_request("GET", f"{JENKINS_URL}/crumbIssuer/api/json")
    data = response.json()
    crumb_field = data.get("crumbRequestField", "Jenkins-Crumb")
    crumb_value = data.get("crumb", "")
    return {crumb_field: crumb_value}


def _build_status_class(color: str) -> str:
    """Derive a human-readable status from Jenkins color field."""
    color = (color or "").lower()
    if "red" in color:
        return "FAILURE"
    if "blue" in color:
        if "anime" in color:
            return "BUILDING"
        return "SUCCESS"
    if "yellow" in color:
        return "UNSTABLE"
    if "disabled" in color or "grey" in color:
        return "DISABLED"
    if "anime" in color:
        return "BUILDING"
    return "UNKNOWN"


def _extract_params_from_actions(actions: list[dict]) -> list[dict]:
    """Extract parameter values from a build's actions list."""
    params = []
    for action in actions:
        if action.get("_class") in (
            "hudson.model.ParametersAction",
            "org.jenkinsci.plugins.workflow.job.properties.ParametersAction",
        ) or "parameters" in action:
            for param in action.get("parameters", []):
                params.append({
                    "name": param.get("name", ""),
                    "value": param.get("value", ""),
                })
    return params


def _extract_causes(actions: list[dict]) -> list[dict]:
    """Extract build causes from a build's actions list."""
    causes = []
    for action in actions:
        if "causes" in action:
            for cause in action.get("causes", []):
                causes.append({
                    "short_description": cause.get("shortDescription", ""),
                    "user_id": cause.get("userId", ""),
                    "user_name": cause.get("userName", ""),
                })
    return causes


# ---------------------------------------------------------------------------
# Tools — Read-only (6)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={"readOnlyHint": True},
)
async def jenkins_list_jobs() -> str:
    """List all Jenkins jobs in the configured folder with their current status.

    Returns a table of jobs with name, status (color), last build number, and URL.

    Example:
        jenkins_list_jobs()
    """
    if JENKINS_FOLDER:
        url = f"{JENKINS_URL}/job/{JENKINS_FOLDER}/api/json?tree=jobs[name,color,lastBuild[number],url]"
    else:
        url = f"{JENKINS_URL}/api/json?tree=jobs[name,color,lastBuild[number],url]"
    response = await _make_request("GET", url)
    data = response.json()

    jobs = data.get("jobs", [])
    if not jobs:
        return "No jobs found."

    lines = ["# Jenkins Jobs\n"]
    if JENKINS_FOLDER:
        lines.append(f"**Folder:** `{JENKINS_FOLDER}`  ")
    lines.append(f"**Total:** {len(jobs)} jobs\n")
    lines.append("| # | Job Name | Status | Last Build |")
    lines.append("|---|----------|--------|------------|")
    for i, job in enumerate(jobs, 1):
        name = job.get("name", "unknown")
        color = job.get("color", "notbuilt")
        status = _build_status_class(color)
        last_build = job.get("lastBuild", {})
        last_num = last_build.get("number", "-") if last_build else "-"
        lines.append(f"| {i} | {name} | {status} | {last_num} |")

    return _truncate("\n".join(lines))


@mcp.tool(
    annotations={"readOnlyHint": True},
)
async def jenkins_get_job(job_name: str) -> str:
    """Get details and parameter definitions for a Jenkins job.

    Shows the job description, current status, parameter definitions (name, type,
    default value, choices), and recent build history.

    Args:
        job_name: Jenkins job name (e.g. oa-platform-php)

    Example:
        jenkins_get_job(job_name="oa-platform-php")
    """
    url = (
        f"{_job_url(job_name)}/api/json"
        f"?tree=name,description,color,buildable,concurrentBuild,"
        f"lastBuild[number,url,timestamp,result],"
        f"lastCompletedBuild[number],lastFailedBuild[number],"
        f"lastSuccessfulBuild[number],"
        f"property[parameterDefinitions[name,type,defaultParameterValue[value],choices,description]]"
    )
    response = await _make_request("GET", url)
    data = response.json()

    lines = [f"# Job: {data.get('name', job_name)}\n"]
    lines.append(f"- **Status:** {_build_status_class(data.get('color', ''))}")
    lines.append(f"- **Buildable:** {data.get('buildable', 'N/A')}")
    lines.append(f"- **Concurrent Build:** {data.get('concurrentBuild', 'N/A')}")
    if data.get("description"):
        lines.append(f"- **Description:** {data['description']}")

    last_build = data.get("lastBuild")
    if last_build:
        lines.append(
            f"- **Last Build:** #{last_build['number']} "
            f"({_format_timestamp(last_build.get('timestamp'))}) "
            f"- {last_build.get('result', 'BUILDING')}"
        )

    # Parameter definitions
    params = []
    for prop in data.get("property", []):
        for pdef in prop.get("parameterDefinitions", []):
            param_info = {
                "name": pdef.get("name", ""),
                "type": pdef.get("type", ""),
                "description": pdef.get("description", ""),
                "default": pdef.get("defaultParameterValue", {}).get("value", ""),
                "choices": pdef.get("choices", []),
            }
            params.append(param_info)

    if params:
        lines.append("\n## Parameters\n")
        for p in params:
            lines.append(f"### `{p['name']}`")
            lines.append(f"- **Type:** {p['type']}")
            if p["description"]:
                lines.append(f"- **Description:** {p['description']}")
            if p["default"] != "":
                default_val = "***" if p["name"].lower() in MASKED_PARAM_NAMES else p["default"]
                lines.append(f"- **Default:** `{default_val}`")
            if p["choices"]:
                lines.append(f"- **Choices:** {', '.join(f'`{c}`' for c in p['choices'])}")
            lines.append("")

    return _truncate("\n".join(lines))


@mcp.tool(
    annotations={"readOnlyHint": True},
)
async def jenkins_list_builds(job_name: str, limit: int = 10) -> str:
    """List recent builds for a Jenkins job with parameters, cause, and duration.

    Args:
        job_name: Jenkins job name (e.g. oa-service)
        limit: Number of recent builds to return (1-50, default 10)

    Example:
        jenkins_list_builds(job_name="oa-service", limit=5)
    """
    limit = max(1, min(50, limit))
    url = (
        f"{_job_url(job_name)}/api/json"
        f"?tree=builds[number,url,result,timestamp,duration,building,"
        f"actions[parameters[name,value],causes[shortDescription,userId,userName]]]"
    )
    response = await _make_request("GET", url)
    data = response.json()

    builds = data.get("builds", [])[:limit]
    if not builds:
        return f"No builds found for job `{job_name}`."

    lines = [f"# Recent Builds: {job_name}\n"]
    for build in builds:
        number = build.get("number", "?")
        result = build.get("result") or ("BUILDING" if build.get("building") else "UNKNOWN")
        ts = _format_timestamp(build.get("timestamp"))
        duration = _format_duration(build.get("duration")) if not build.get("building") else "in progress"

        lines.append(f"## Build #{number}\n")
        lines.append(f"- **Result:** {result}")
        lines.append(f"- **Started:** {ts}")
        lines.append(f"- **Duration:** {duration}")

        causes = _extract_causes(build.get("actions", []))
        if causes:
            for c in causes:
                desc = c.get("short_description", "")
                user = c.get("user_name", "")
                if user:
                    lines.append(f"- **Triggered by:** {user} ({desc})")
                else:
                    lines.append(f"- **Cause:** {desc}")

        params = _extract_params_from_actions(build.get("actions", []))
        if params:
            lines.append("- **Parameters:**")
            for p in params:
                val = "***" if p["name"].lower() in MASKED_PARAM_NAMES else p["value"]
                lines.append(f"  - `{p['name']}`: `{val}`")
        lines.append("")

    return _truncate("\n".join(lines))


@mcp.tool(
    annotations={"readOnlyHint": True},
)
async def jenkins_get_build(job_name: str, build_number: int) -> str:
    """Get detailed information about a specific build.

    Shows build result, duration, timestamps, parameters, causes, and artifacts.

    Args:
        job_name: Jenkins job name
        build_number: Build number

    Example:
        jenkins_get_build(job_name="oa-gateway", build_number=42)
    """
    url = (
        f"{_job_url(job_name)}/{build_number}/api/json"
        f"?tree=number,url,result,building,timestamp,duration,"
        f"estimatedDuration,description,"
        f"actions[parameters[name,value],causes[shortDescription,userId,userName]]"
    )
    response = await _make_request("GET", url)
    build = response.json()

    number = build.get("number", build_number)
    result = build.get("result") or ("BUILDING" if build.get("building") else "UNKNOWN")

    lines = [f"# Build #{number} — {job_name}\n"]
    lines.append(f"- **Result:** {result}")
    lines.append(f"- **URL:** {build.get('url', 'N/A')}")
    lines.append(f"- **Started:** {_format_timestamp(build.get('timestamp'))}")

    if build.get("building"):
        lines.append("- **Status:** Currently building...")
    else:
        lines.append(f"- **Duration:** {_format_duration(build.get('duration'))}")

    if build.get("estimatedDuration"):
        lines.append(f"- **Estimated Duration:** {_format_duration(build['estimatedDuration'])}")

    if build.get("description"):
        lines.append(f"- **Description:** {build['description']}")

    causes = _extract_causes(build.get("actions", []))
    if causes:
        lines.append("\n## Causes\n")
        for c in causes:
            desc = c.get("short_description", "")
            user = c.get("user_name", "")
            uid = c.get("user_id", "")
            lines.append(f"- {desc}" + (f" (user: {user} / {uid})" if user else ""))

    params = _extract_params_from_actions(build.get("actions", []))
    if params:
        lines.append("\n## Parameters\n")
        for p in params:
            val = "***" if p["name"].lower() in MASKED_PARAM_NAMES else p["value"]
            lines.append(f"- `{p['name']}`: `{val}`")

    return _truncate("\n".join(lines))


@mcp.tool(
    annotations={"readOnlyHint": True},
)
async def jenkins_get_build_log(job_name: str, build_number: int, tail: int = 200) -> str:
    """Get console output (build log) for a specific build.

    Returns the last N lines of the build console output.

    Args:
        job_name: Jenkins job name
        build_number: Build number
        tail: Number of lines from the end of the log to return (1-5000, default 200)

    Example:
        jenkins_get_build_log(job_name="oa-platform-php", build_number=100, tail=50)
    """
    url = f"{_job_url(job_name)}/{build_number}/consoleText"
    response = await _make_request("GET", url)
    log_text = response.text

    log_lines = log_text.splitlines()
    total_lines = len(log_lines)

    if total_lines <= tail:
        selected = log_lines
    else:
        selected = log_lines[-tail:]

    lines = [
        f"# Build Log: {job_name} #{build_number}\n",
        f"Showing last {len(selected)} of {total_lines} lines\n",
        "```",
    ]
    lines.extend(selected)
    lines.append("```")

    return _truncate("\n".join(lines))


@mcp.tool(
    annotations={"readOnlyHint": True},
)
async def jenkins_get_queue() -> str:
    """Get the current Jenkins build queue.

    Shows all queued items with job name, parameters, wait time, and reason
    for waiting (e.g. waiting for executor, blocked by another build).

    Example:
        jenkins_get_queue()
    """
    url = f"{JENKINS_URL}/queue/api/json"
    response = await _make_request("GET", url)
    data = response.json()

    items = data.get("items", [])
    if not items:
        return "Build queue is empty."

    lines = [f"# Build Queue ({len(items)} items)\n"]
    for i, item in enumerate(items, 1):
        task = item.get("task", {})
        job_name = task.get("name", "unknown")
        url_link = task.get("url", "")
        blocked = item.get("blocked", False)
        buildable = item.get("buildable", False)
        why = item.get("why", "N/A")
        in_queue_since = item.get("inQueueSince", 0)

        wait_ms = int(time.time() * 1000) - in_queue_since if in_queue_since else 0

        lines.append(f"## {i}. {job_name}\n")
        lines.append(f"- **URL:** {url_link}")
        lines.append(f"- **Blocked:** {blocked}")
        lines.append(f"- **Buildable:** {buildable}")
        lines.append(f"- **Queued Since:** {_format_timestamp(in_queue_since)}")
        lines.append(f"- **Wait Time:** {_format_duration(wait_ms)}")
        lines.append(f"- **Reason:** {why}")

        params = item.get("params", "")
        if params:
            lines.append("- **Parameters:**")
            try:
                param_pairs = []
                for pair in params.split("\n"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        param_pairs.append((k.strip(), v.strip()))
                for k, v in param_pairs:
                    val = "***" if k.lower() in MASKED_PARAM_NAMES else v
                    lines.append(f"  - `{k}`: `{val}`")
            except Exception:
                lines.append(f"  - Raw: `{params}`")

        lines.append("")

    return _truncate("\n".join(lines))


# ---------------------------------------------------------------------------
# Tools — Write (3)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": False},
)
async def jenkins_build(job_name: str, parameters: dict[str, str] | None = None) -> str:
    """Trigger a Jenkins build with optional parameters.

    Submits the build and returns the queue item URL for tracking.

    Args:
        job_name: Jenkins job name to trigger
        parameters: Build parameters as key-value pairs (optional)

    Example:
        jenkins_build(job_name="oa-gateway", parameters={"test_version": "kn", "oa_branch": "master"})
    """
    crumb_headers = await _get_crumb()

    if parameters:
        url = f"{_job_url(job_name)}/buildWithParameters"
    else:
        url = f"{_job_url(job_name)}/build"

    request_headers = {**_headers(), **crumb_headers}
    # Remove Accept header for POST to avoid JSON parsing on redirect responses
    request_headers.pop("Accept", None)

    async with httpx.AsyncClient(
        verify=False,
        follow_redirects=False,
    ) as client:
        response = await client.request(
            "POST",
            url,
            auth=_auth(),
            headers=request_headers,
            params=parameters or None,
        )

    # Jenkins returns 201 with Location header pointing to the queue item
    if response.status_code in (200, 201, 302):
        queue_url = response.headers.get("Location", "")
        if queue_url and not queue_url.endswith("api/json"):
            queue_url = queue_url.rstrip("/") + "/api/json"

        lines = [f"# Build Triggered: {job_name}\n"]
        lines.append(f"- **Status:** Successfully queued")
        if parameters:
            lines.append("- **Parameters:**")
            for k, v in parameters.items():
                val = "***" if k.lower() in MASKED_PARAM_NAMES else v
                lines.append(f"  - `{k}`: `{val}`")
        if queue_url:
            lines.append(f"- **Queue URL:** {queue_url}")
        lines.append("")
        lines.append("Use `jenkins_get_queue` to check queue status, or")
        lines.append("use `jenkins_get_build` once the build starts.")
        return _truncate("\n".join(lines))

    # If we got here, something unexpected happened
    return f"Unexpected response from Jenkins: {response.status_code} - {response.text[:500]}"


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": False},
)
async def jenkins_build_and_watch(
    job_name: str,
    parameters: dict[str, str] | None = None,
    poll_interval: int = 10,
    timeout_seconds: int = 600,
) -> str:
    """Trigger a Jenkins build and poll until it completes.

    Starts the build, then periodically checks the queue and build status
    until the build finishes or the timeout is reached.

    Args:
        job_name: Jenkins job name to trigger
        parameters: Build parameters as key-value pairs (optional)
        poll_interval: Seconds between status checks (3-60, default 10)
        timeout_seconds: Maximum seconds to wait for completion (30-1800, default 600)

    Example:
        jenkins_build_and_watch(
            job_name="oa-service",
            parameters={"test_version": "kn", "deploy_type": "api", "oa_branch": "master"},
            poll_interval=15,
            timeout_seconds=300
        )
    """
    crumb_headers = await _get_crumb()

    if parameters:
        trigger_url = f"{_job_url(job_name)}/buildWithParameters"
    else:
        trigger_url = f"{_job_url(job_name)}/build"

    request_headers = {**_headers(), **crumb_headers}
    request_headers.pop("Accept", None)

    # Step 1: Trigger the build
    async with httpx.AsyncClient(verify=False, follow_redirects=False) as client:
        response = await client.request(
            "POST",
            trigger_url,
            auth=_auth(),
            headers=request_headers,
            params=parameters or None,
        )

    if response.status_code not in (200, 201, 302):
        return f"Failed to trigger build: {response.status_code} - {response.text[:500]}"

    queue_url = response.headers.get("Location", "").rstrip("/")
    if not queue_url:
        return "Build was triggered but no queue URL was returned."

    lines = [f"# Build & Watch: {job_name}\n"]
    lines.append("Build triggered. Waiting for completion...\n")

    if parameters:
        lines.append("**Parameters:**")
        for k, v in parameters.items():
            val = "***" if k.lower() in MASKED_PARAM_NAMES else v
            lines.append(f"- `{k}`: `{val}`")
        lines.append("")

    start_time = time.time()
    build_url = None

    # Step 2: Poll queue until build starts
    while time.time() - start_time < timeout_seconds:
        await asyncio.sleep(poll_interval)

        try:
            queue_api_url = f"{queue_url}/api/json"
            q_response = await _make_request("GET", queue_api_url)
            q_data = q_response.json()

            executable = q_data.get("executable")
            if executable:
                build_url = executable.get("url", "").rstrip("/")
                build_number = executable.get("number", "?")
                lines.append(f"Build #{build_number} started. Polling for result...\n")
                break

            cancelled = q_data.get("cancelled", False)
            if cancelled:
                lines.append("Build was cancelled while in the queue.")
                return _truncate("\n".join(lines))

        except Exception as e:
            lines.append(f"Warning: Queue check failed: {e}")

    if not build_url:
        elapsed = int(time.time() - start_time)
        lines.append(f"Timeout after {elapsed}s — build may still be queued or building.")
        lines.append(f"Check manually: {queue_url}")
        return _truncate("\n".join(lines))

    # Step 3: Poll build until complete
    while time.time() - start_time < timeout_seconds:
        await asyncio.sleep(poll_interval)

        try:
            build_api_url = f"{build_url}/api/json?tree=number,result,building,duration,timestamp"
            b_response = await _make_request("GET", build_api_url)
            b_data = b_response.json()

            if not b_data.get("building", True):
                result = b_data.get("result", "UNKNOWN")
                duration = _format_duration(b_data.get("duration"))
                number = b_data.get("number", "?")
                ts = _format_timestamp(b_data.get("timestamp"))

                lines.append("---\n")
                lines.append(f"## Build #{number} Completed\n")
                lines.append(f"- **Result:** {result}")
                lines.append(f"- **Started:** {ts}")
                lines.append(f"- **Duration:** {duration}")
                lines.append(f"- **URL:** {build_url}")

                elapsed = int(time.time() - start_time)
                lines.append(f"- **Total Wait:** {elapsed}s")

                return _truncate("\n".join(lines))

        except Exception as e:
            lines.append(f"Warning: Build check failed: {e}")

    elapsed = int(time.time() - start_time)
    lines.append(f"\nTimeout after {elapsed}s — build is still running.")
    lines.append(f"Check manually: {build_url}")
    return _truncate("\n".join(lines))


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": True},
)
async def jenkins_cancel_build(job_name: str, build_number: int) -> str:
    """Cancel a running Jenkins build.

    Stops the specified build if it is currently running.

    Args:
        job_name: Jenkins job name
        build_number: Build number to cancel

    Example:
        jenkins_cancel_build(job_name="oa-gateway", build_number=42)
    """
    # First check if the build is actually running
    check_url = f"{_job_url(job_name)}/{build_number}/api/json?tree=building,result"
    check_response = await _make_request("GET", check_url)
    check_data = check_response.json()

    if not check_data.get("building", False):
        result = check_data.get("result", "UNKNOWN")
        return f"Build #{build_number} of `{job_name}` is not running. Last result: {result}"

    crumb_headers = await _get_crumb()
    stop_url = f"{_job_url(job_name)}/{build_number}/stop"

    request_headers = {**crumb_headers}

    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        response = await client.request(
            "POST",
            stop_url,
            auth=_auth(),
            headers=request_headers,
        )

    if response.status_code in (200, 201, 302, 204):
        return f"Build #{build_number} of `{job_name}` cancellation request sent successfully."
    else:
        return (
            f"Unexpected response when cancelling build #{build_number}: "
            f"{response.status_code} - {response.text[:300]}"
        )


# ---------------------------------------------------------------------------
# Tools — Advanced (2)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={"readOnlyHint": True},
)
async def jenkins_compare_builds(
    job_name: str,
    build_number_a: int,
    build_number_b: int,
) -> str:
    """Compare parameters and results of two builds for the same job.

    Shows a side-by-side comparison of build parameters, results, durations,
    and timestamps to help identify what changed between builds.

    Args:
        job_name: Jenkins job name
        build_number_a: First build number
        build_number_b: Second build number

    Example:
        jenkins_compare_builds(job_name="oa-service", build_number_a=40, build_number_b=41)
    """
    # Fetch both builds in parallel
    import asyncio as _asyncio

    tree_query = (
        "number,result,timestamp,duration,building,"
        "actions[parameters[name,value],causes[shortDescription,userId,userName]]"
    )

    async def _fetch_build(num: int) -> dict:
        url = f"{_job_url(job_name)}/{num}/api/json?tree={tree_query}"
        resp = await _make_request("GET", url)
        return resp.json()

    build_a, build_b = await _asyncio.gather(
        _fetch_build(build_number_a),
        _fetch_build(build_number_b),
    )

    lines = [f"# Build Comparison: {job_name}\n"]
    lines.append(f"## Build #{build_number_a} vs Build #{build_number_b}\n")

    # Basic info comparison
    lines.append("| Field | Build #{} | Build #{} |".format(build_number_a, build_number_b))
    lines.append("|-------|-----------|-----------|")

    result_a = build_a.get("result") or ("BUILDING" if build_a.get("building") else "UNKNOWN")
    result_b = build_b.get("result") or ("BUILDING" if build_b.get("building") else "UNKNOWN")
    lines.append(f"| Result | {result_a} | {result_b} |")
    lines.append(f"| Started | {_format_timestamp(build_a.get('timestamp'))} | {_format_timestamp(build_b.get('timestamp'))} |")
    lines.append(f"| Duration | {_format_duration(build_a.get('duration'))} | {_format_duration(build_b.get('duration'))} |")

    # Parameter comparison
    params_a = {p["name"]: p["value"] for p in _extract_params_from_actions(build_a.get("actions", []))}
    params_b = {p["name"]: p["value"] for p in _extract_params_from_actions(build_b.get("actions", []))}

    all_param_keys = sorted(set(list(params_a.keys()) + list(params_b.keys())))

    if all_param_keys:
        lines.append("\n## Parameter Comparison\n")
        lines.append("| Parameter | Build #{} | Build #{} | Changed |".format(build_number_a, build_number_b))
        lines.append("|-----------|-----------|-----------|---------|")

        for key in all_param_keys:
            val_a = params_a.get(key, "*not set*")
            val_b = params_b.get(key, "*not set*")

            # Mask passwords
            if key.lower() in MASKED_PARAM_NAMES:
                val_a = "***" if val_a != "*not set*" else val_a
                val_b = "***" if val_b != "*not set*" else val_b

            changed = "Yes" if val_a != val_b else "No"
            lines.append(f"| {key} | `{val_a}` | `{val_b}` | {changed} |")

    # Cause comparison
    causes_a = _extract_causes(build_a.get("actions", []))
    causes_b = _extract_causes(build_b.get("actions", []))

    lines.append("\n## Causes\n")
    lines.append(f"- **Build #{build_number_a}:**")
    for c in causes_a:
        user = c.get("user_name", "")
        desc = c.get("short_description", "")
        lines.append(f"  - {desc}" + (f" by {user}" if user else ""))

    lines.append(f"- **Build #{build_number_b}:**")
    for c in causes_b:
        user = c.get("user_name", "")
        desc = c.get("short_description", "")
        lines.append(f"  - {desc}" + (f" by {user}" if user else ""))

    return _truncate("\n".join(lines))


@mcp.tool(
    annotations={"readOnlyHint": True},
)
async def jenkins_get_test_report(job_name: str, build_number: int) -> str:
    """Get the test report for a specific build.

    Shows test results summary including pass/fail/skip counts, duration,
    and details of any failing test cases.

    Args:
        job_name: Jenkins job name
        build_number: Build number

    Example:
        jenkins_get_test_report(job_name="oa-platform-php", build_number=100)
    """
    url = f"{_job_url(job_name)}/{build_number}/testReport/api/json"

    try:
        response = await _make_request("GET", url)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"No test report found for `{job_name}` #{build_number}. The build may not have test results."
        raise

    data = response.json()

    lines = [f"# Test Report: {job_name} #{build_number}\n"]

    # Summary
    fail_count = data.get("failCount", 0)
    pass_count = data.get("passCount", 0)
    skip_count = data.get("skipCount", 0)
    total = fail_count + pass_count + skip_count

    lines.append("## Summary\n")
    lines.append(f"| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Total | {total} |")
    lines.append(f"| Passed | {pass_count} |")
    lines.append(f"| Failed | **{fail_count}** |")
    lines.append(f"| Skipped | {skip_count} |")

    if total > 0:
        pass_rate = (pass_count / total) * 100
        lines.append(f"| Pass Rate | {pass_rate:.1f}% |")

    # Suites
    suites = data.get("suites", [])
    if suites:
        lines.append("\n## Test Suites\n")
        for suite in suites:
            suite_name = suite.get("name", "Unknown Suite")
            duration = suite.get("duration", 0)
            cases = suite.get("cases", [])

            lines.append(f"### {suite_name}\n")
            lines.append(f"- **Duration:** {duration:.2f}s")
            lines.append(f"- **Cases:** {len(cases)}")

            # Show failing cases
            failing = [c for c in cases if c.get("status") == "FAILED"]
            if failing:
                lines.append(f"- **Failed:** {len(failing)}\n")
                for case in failing:
                    name = case.get("name", "unknown")
                    class_name = case.get("className", "")
                    error_details = case.get("errorDetails", "")
                    error_stack = case.get("errorStackTrace", "")
                    lines.append(f"  - **{name}** ({class_name})")
                    if error_details:
                        lines.append(f"    - Error: {error_details[:200]}")
                    lines.append("")

            # Show all case statuses in a compact table if not too many
            if len(cases) <= 20:
                lines.append("| Test | Status | Duration |")
                lines.append("|------|--------|----------|")
                for case in cases:
                    name = case.get("name", "unknown")
                    status = case.get("status", "UNKNOWN")
                    dur = case.get("duration", 0)
                    lines.append(f"| {name} | {status} | {dur:.2f}s |")
                lines.append("")

    return _truncate("\n".join(lines))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
