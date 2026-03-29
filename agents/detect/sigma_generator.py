# FILE: agents/detect/sigma_generator.py
"""
Sigma rule generator — creates detection rules for techniques that evaded SIEMs.
Uses LLM to generate syntactically correct Sigma YAML.
"""
from __future__ import annotations

import logging
import os
import re
import sys

logger = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
LLM_MODEL    = os.getenv("LLM_MODEL", "claude-sonnet-4-6")

# Minimum required fields for a valid Sigma rule
_REQUIRED_SIGMA_FIELDS = ("title", "status", "logsource", "detection")

_SIGMA_SYSTEM_PROMPT = """\
You are an expert Sigma rule author and threat detection engineer.
Sigma (https://github.com/SigmaHQ/sigma) is a generic YAML-based detection rule format.

When asked to generate a Sigma rule you MUST:
1. Output ONLY valid Sigma YAML — no explanation, no markdown fences, no extra text.
2. Include all required fields: title, id (UUID), status (experimental/test/stable),
   description, references, author, date, modified, tags (mitre attack), logsource,
   detection (condition + selection keywords), falsepositives, level.
3. Use realistic log source definitions (e.g., product: windows, category: process_creation).
4. Make detection keywords specific enough to reduce false positives.
5. Assign the correct MITRE ATT&CK tag in the form: attack.tXXXX
6. Set status: experimental for newly generated rules.
7. Never wrap the YAML in code fences — return raw YAML only.

Example skeleton (fill in real values):
title: Suspicious Process Creation via Technique T1059
id: 00000000-0000-0000-0000-000000000000
status: experimental
description: Detects ...
references:
  - https://attack.mitre.org/techniques/T1059/
author: SecuNet Detect Agent
date: 2024/01/01
tags:
  - attack.execution
  - attack.t1059
logsource:
  product: windows
  category: process_creation
detection:
  selection:
    CommandLine|contains:
      - 'suspicious_string'
  condition: selection
falsepositives:
  - Legitimate administration activity
level: medium
"""


async def generate_sigma_rule(
    technique_id:   str,
    technique_name: str,
    context:        str,
    exploit_output: str = "",
) -> str:
    """
    Use the platform LLM to generate a Sigma detection rule for a given technique.

    Args:
        technique_id:   MITRE ATT&CK technique ID (e.g. "T1210").
        technique_name: Human-readable technique name.
        context:        Additional context (Commander state, host info, etc.).
        exploit_output: Raw output from the exploit attempt (helps tailor IoCs).

    Returns:
        Sigma YAML string. May be empty string on total failure.
    """
    import uuid as _uuid
    rule_id = str(_uuid.uuid4())

    user_prompt = f"""Generate a Sigma detection rule for the following MITRE ATT&CK technique.

Technique ID:   {technique_id}
Technique name: {technique_name}
Rule UUID:      {rule_id}

Context from mission state:
{context[:800] if context else "(none)"}

Exploit output observed (use to identify specific IoCs / artifacts):
{exploit_output[:600] if exploit_output else "(none)"}

Requirements:
- The rule must detect this specific technique in a realistic enterprise environment.
- Use the IoCs visible in the exploit output if present (process names, command-line patterns,
  network destinations, file paths, registry keys, etc.).
- Tag the rule with attack.{technique_id.lower()} and at least one tactic tag.
- Set level to high if the technique is commonly used in ransomware/APT kill chains,
  medium otherwise.
- Output ONLY the raw YAML, starting with 'title:'."""

    try:
        raw_yaml = await _llm_complete_sigma(user_prompt)
        # Strip accidental markdown fences
        raw_yaml = re.sub(r"^```[a-zA-Z]*\n?", "", raw_yaml.strip(), flags=re.MULTILINE)
        raw_yaml = re.sub(r"\n?```$", "", raw_yaml.strip(), flags=re.MULTILINE)
        return raw_yaml.strip()
    except Exception as exc:
        logger.error("[sigma] Rule generation failed for %s: %s", technique_id, exc)
        return ""


def validate_sigma_rule(yaml_text: str) -> tuple[bool, str]:
    """
    Basic structural validation of a Sigma YAML rule.

    Checks:
    - The text is non-empty.
    - All required fields (title, status, logsource, detection) are present.
    - The YAML can be parsed without errors.

    Returns:
        (is_valid: bool, error_message: str)
        error_message is empty string when is_valid is True.
    """
    if not yaml_text or not yaml_text.strip():
        return False, "Rule is empty"

    # Check required fields are present (simple substring check first)
    for field in _REQUIRED_SIGMA_FIELDS:
        if f"{field}:" not in yaml_text:
            return False, f"Missing required field: '{field}'"

    # Try to parse as YAML
    try:
        import yaml  # type: ignore
        parsed = yaml.safe_load(yaml_text)
        if not isinstance(parsed, dict):
            return False, "Parsed YAML is not a dict — expected a mapping at top level"

        # Confirm required keys are in the parsed dict too
        for field in _REQUIRED_SIGMA_FIELDS:
            if field not in parsed:
                return False, f"Parsed YAML missing required key: '{field}'"

        # Validate logsource is a dict with at least one key
        logsource = parsed.get("logsource", {})
        if not isinstance(logsource, dict) or not logsource:
            return False, "logsource must be a non-empty mapping"

        # Validate detection has a condition
        detection = parsed.get("detection", {})
        if not isinstance(detection, dict):
            return False, "detection must be a mapping"
        if "condition" not in detection:
            return False, "detection block is missing 'condition' key"

        return True, ""
    except Exception as exc:
        return False, f"YAML parse error: {exc}"


# ── Internal LLM helper (mirrors base_agent._llm_complete) ───────────────────

async def _llm_complete_sigma(user_prompt: str) -> str:
    """Call the configured LLM provider to generate Sigma YAML."""
    if LLM_PROVIDER == "anthropic":
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        resp = await client.messages.create(
            model=LLM_MODEL,
            max_tokens=4096,
            system=_SIGMA_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return resp.content[0].text

    elif LLM_PROVIDER in ("openai", "lmstudio"):
        from openai import AsyncOpenAI
        kwargs: dict = {"api_key": os.getenv("OPENAI_API_KEY", "none")}
        if LLM_PROVIDER == "lmstudio":
            kwargs["base_url"] = os.getenv("LMSTUDIO_URL", "http://localhost:1234/v1")
        client = AsyncOpenAI(**kwargs)
        messages = [
            {"role": "system",  "content": _SIGMA_SYSTEM_PROMPT},
            {"role": "user",    "content": user_prompt},
        ]
        resp = await client.chat.completions.create(
            model=LLM_MODEL, max_tokens=4096, messages=messages
        )
        return resp.choices[0].message.content

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER!r}")
