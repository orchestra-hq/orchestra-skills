#!/usr/bin/env python3
"""LLM-judge grading for free-text (no `check`) assertions.

Batches every free-text assertion for a single run into one forced tool call —
`strict: true` + `tool_choice` guarantees the response validates against the
schema exactly, so there's no JSON parsing or retry-on-malformed-output needed.

Not invoked directly — called from grade.py when `--llm-judge` is passed.
"""
from __future__ import annotations

VERDICT_TOOL = {
    "name": "record_verdicts",
    "description": "Record a pass/fail verdict for each assertion under review.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer", "description": "0-based index matching the numbered assertion list"},
                        "passed": {"type": "boolean"},
                        "rationale": {"type": "string", "description": "One or two sentences citing evidence from the transcript"},
                    },
                    "required": ["index", "passed", "rationale"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["verdicts"],
        "additionalProperties": False,
    },
}

JUDGE_SYSTEM = (
    "You are grading whether an AI agent's response to a task satisfies a list of "
    "assertions. Be skeptical — an assertion only passes if the transcript actually "
    "demonstrates it, not if the response is merely plausible or well-intentioned. "
    "Cite concrete evidence from the transcript in each rationale."
)


def _build_prompt(prompt: str, expected_output: str, transcript: str,
                   output_text: str, assertions: list[dict]) -> str:
    numbered = "\n".join(f"{i}. {a['text']}" for i, a in enumerate(assertions))
    parts = [
        f"Task given to the agent:\n{prompt}",
        f"Expected behavior:\n{expected_output}",
        f"Agent's final response:\n{transcript or '(empty — the agent produced no final text response)'}",
    ]
    if output_text:
        parts.append(f"Produced file contents:\n{output_text}")
    parts.append(
        "Assertions to check (0-indexed):\n" + numbered + "\n\n"
        "For each assertion above, call record_verdicts with a verdict for every index."
    )
    return "\n\n".join(parts)


def judge_run(client, model: str, prompt: str, expected_output: str,
              transcript: str, output_text: str, assertions: list[dict]) -> list[dict]:
    """Grade `assertions` (each {"text": ...}) against one run. Returns a list of
    {"index": int, "passed": bool, "rationale": str}, one per input assertion.
    """
    judge_prompt = _build_prompt(prompt, expected_output, transcript, output_text, assertions)
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=JUDGE_SYSTEM,
        tools=[VERDICT_TOOL],
        tool_choice={"type": "tool", "name": "record_verdicts"},
        messages=[{"role": "user", "content": judge_prompt}],
    )
    tool_use = next(b for b in response.content if b.type == "tool_use")
    return tool_use.input["verdicts"]
