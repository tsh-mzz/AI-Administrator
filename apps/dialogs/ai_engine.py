import json
import time
from dataclasses import dataclass
from decimal import Decimal

import anthropic
import structlog
from django.conf import settings

from .prompt_builder import build_system_prompt
from .tools import execute_tool, get_tools_for_salon

logger = structlog.get_logger(__name__)

# Cost per 1M tokens (USD) for claude-sonnet-4-6
_COST_INPUT_PER_M = Decimal("3.00")
_COST_OUTPUT_PER_M = Decimal("15.00")


@dataclass
class AIResponse:
    text: str
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: Decimal = Decimal("0")
    latency_ms: int = 0
    escalate: bool = False


def _get_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


def _calculate_cost(tokens_input: int, tokens_output: int) -> Decimal:
    return (
        Decimal(tokens_input) / Decimal(1_000_000) * _COST_INPUT_PER_M
        + Decimal(tokens_output) / Decimal(1_000_000) * _COST_OUTPUT_PER_M
    )


async def _load_conversation_history(conversation) -> list[dict]:
    """Load last 20 messages and format for Claude."""
    from .models import Message

    messages = []
    async for msg in (
        Message.objects.filter(conversation=conversation)
        .exclude(role="system")
        .order_by("-created_at")[:20]
    ):
        messages.append(msg)

    messages.reverse()

    history = []
    for msg in messages:
        if msg.role == "tool":
            continue
        if msg.tool_calls_json:
            history.append({"role": "assistant", "content": msg.tool_calls_json})
        elif msg.tool_results_json:
            history.append({"role": "user", "content": msg.tool_results_json})
        else:
            history.append({"role": msg.role, "content": msg.content})

    return history


async def _save_user_message(conversation, text: str) -> None:
    from .models import Message
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(seconds=60)
    already_saved = await Message.objects.filter(
        conversation=conversation, role="user", content=text, created_at__gte=cutoff
    ).aexists()
    if already_saved:
        return
    await Message.objects.acreate(
        conversation=conversation,
        direction="in",
        role="user",
        content=text,
    )


async def _save_tool_turn(conversation, tool_calls_content, tool_results: list) -> None:
    from .models import Message

    serialized = [
        b if isinstance(b, dict) else b.model_dump() for b in tool_calls_content
    ]
    await Message.objects.acreate(
        conversation=conversation,
        direction="out",
        role="assistant",
        content="",
        tool_calls_json=serialized,
    )
    await Message.objects.acreate(
        conversation=conversation,
        direction="in",
        role="tool",
        content="",
        tool_results_json=tool_results,
    )


async def _save_assistant_message(conversation, response: AIResponse) -> None:
    from .models import Message

    await Message.objects.acreate(
        conversation=conversation,
        direction="out",
        role="assistant",
        content=response.text,
        tokens_input=response.tokens_input,
        tokens_output=response.tokens_output,
        cost_usd=response.cost_usd,
        latency_ms=response.latency_ms,
    )


async def _run_agent_loop(
    system_prompt: str,
    messages: list[dict],
    tools: list[dict],
    salon,
    conversation,
    max_iterations: int = 5,
) -> AIResponse:
    client = _get_client()
    total_input = 0
    total_output = 0
    start = time.monotonic()

    for iteration in range(max_iterations):
        api_response = await client.messages.create(
            model=salon.ai_model,
            system=system_prompt,
            messages=messages,
            tools=tools,
            max_tokens=1024,
        )

        total_input += api_response.usage.input_tokens
        total_output += api_response.usage.output_tokens

        logger.info(
            "llm_call",
            salon_id=salon.id,
            iteration=iteration,
            stop_reason=api_response.stop_reason,
            input_tokens=api_response.usage.input_tokens,
            output_tokens=api_response.usage.output_tokens,
        )

        if api_response.stop_reason == "end_turn":
            text = next(
                (
                    block.text
                    for block in api_response.content
                    if hasattr(block, "text")
                ),
                "Извините, не могу ответить прямо сейчас.",
            )
            latency = int((time.monotonic() - start) * 1000)
            return AIResponse(
                text=text,
                tokens_input=total_input,
                tokens_output=total_output,
                cost_usd=_calculate_cost(total_input, total_output),
                latency_ms=latency,
            )

        if api_response.stop_reason == "tool_use":
            tool_results = []
            for block in api_response.content:
                if block.type == "tool_use":
                    result = await execute_tool(
                        tool_name=block.name,
                        tool_input=block.input,
                        salon=salon,
                        conversation=conversation,
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )

            messages.append({"role": "assistant", "content": api_response.content})
            messages.append({"role": "user", "content": tool_results})
            await _save_tool_turn(conversation, api_response.content, tool_results)
            continue

        break

    latency = int((time.monotonic() - start) * 1000)
    return AIResponse(
        text="Извините, произошла ошибка. Администратор свяжется с вами в ближайшее время.",
        tokens_input=total_input,
        tokens_output=total_output,
        cost_usd=_calculate_cost(total_input, total_output),
        latency_ms=latency,
        escalate=True,
    )


async def process_incoming_message(conversation, user_message: str) -> AIResponse:
    """Main entry point: process one user message and return bot reply."""
    salon = await conversation.salon.__class__.objects.aget(pk=conversation.salon_id)

    history = await _load_conversation_history(conversation)
    system_prompt = build_system_prompt(salon)
    await _save_user_message(conversation, user_message)
    tools = get_tools_for_salon(salon)

    messages = history + [{"role": "user", "content": user_message}]

    try:
        response = await _run_agent_loop(
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
            salon=salon,
            conversation=conversation,
        )
    except Exception as exc:
        logger.error("ai_engine_error", error=str(exc), salon_id=salon.id)
        response = AIResponse(
            text="Извините, произошла техническая ошибка. Администратор свяжется с вами.",
            escalate=True,
        )

    await _save_assistant_message(conversation, response)

    if response.escalate:
        await conversation.__class__.objects.filter(pk=conversation.pk).aupdate(
            status="handed_to_admin"
        )

    return response
