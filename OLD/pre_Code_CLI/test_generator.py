from __future__ import annotations

import re
from dataclasses import dataclass

from anthropic import AsyncAnthropic

from config import Settings
from mcp_client import PlaywrightMCPSession
from models import StepManifest
from prompts.test_generator_prompt import SYSTEM_PROMPT

MAX_AGENT_TURNS = 25  # safety cap so a confused model can't loop forever burning tokens/tool calls

FILE_BLOCK_RE = re.compile(
    r"###\s*(PAGE_OBJECT_FILE|TEST_FILE):\s*(?P<path>\S+)\s*```(?:python)?\s*(?P<code>.*?)```",
    re.DOTALL,
)


@dataclass
class GeneratedTest:
    page_object_path: str
    page_object_code: str
    test_path: str
    test_code: str
    transcript: list[dict]  # full message history - validator mines this for real snapshot data


class TestGenerator:
    def __init__(self, settings: Settings, mcp: PlaywrightMCPSession):
        self.settings = settings
        self.mcp = mcp
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate(self, manifest: StepManifest, feedback: str | None = None) -> GeneratedTest:
        tools = await self.mcp.anthropic_tools()

        user_prompt = (
            "Step manifest (source of truth - implement every step, no more, no less):\n"
            f"{manifest.to_json()}\n"
        )
        if feedback:
            user_prompt += (
                f"\nThe previous attempt failed validation for these reasons - fix them:\n{feedback}\n"
            )

        messages: list[dict] = [{"role": "user", "content": user_prompt}]
        final_text: str | None = None

        for _ in range(MAX_AGENT_TURNS):
            response = await self.client.messages.create(
                model=self.settings.model,
                max_tokens=self.settings.max_tokens,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if not tool_uses:
                final_text = "".join(b.text for b in response.content if b.type == "text")
                break

            tool_results = []
            for block in tool_uses:
                result_text = await self.mcp.call_tool(block.name, block.input or {})
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": result_text}
                )
            messages.append({"role": "user", "content": tool_results})

        if final_text is None:
            raise RuntimeError(
                f"Test generator hit its {MAX_AGENT_TURNS}-turn cap without producing final output."
            )

        blocks = {m.group(1): m for m in FILE_BLOCK_RE.finditer(final_text)}
        if "PAGE_OBJECT_FILE" not in blocks or "TEST_FILE" not in blocks:
            raise RuntimeError(
                "Model output did not contain the expected PAGE_OBJECT_FILE / TEST_FILE blocks:\n\n"
                + final_text
            )

        po, tf = blocks["PAGE_OBJECT_FILE"], blocks["TEST_FILE"]
        return GeneratedTest(
            page_object_path=po.group("path"),
            page_object_code=po.group("code").strip(),
            test_path=tf.group("path"),
            test_code=tf.group("code").strip(),
            transcript=messages,
        )
