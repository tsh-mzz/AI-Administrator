import json
import time
from dataclasses import dataclass
from decimal import Decimal

import openai
import structlog
from django.conf import settings

from .prompt_builder import build_system_prompt
from .tools import execute_tool, get_tools_for_salon

logger = structlog.get_logger(__name__)

_COST_INPUT_PER_M = Decimal("0.00")
_COST_OUTPUT_PER_M = Decimal("0.00")


@dataclass
class AIResponse:
    text: str
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: Decimal = Decimal("0")
    latency_ms: int = 0
    escalate: bool = False


def _get_client() -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )


def _calculate_cost(tokens_input: int, tokens_output: int) -> Decimal:
    return (
        Decimal(tokens_input) / Decimal(1_000_000) * _COST_INPUT_PER_M
        + Decimal(tokens_output) / Decimal(1_000_000) * _COST_OUTPUT_PER_M
    )


def _extract_failed_tool_calls(exc: openai.BadRequestError) -> list | None:
    """Parse tool calls from Groq's tool_use_failed error response.

    In the openai SDK, exc.body is already the inner "error" dict
    (the SDK strips the outer {"error": ...} wrapper via _make_status_error).
    """
    try:
        body = exc.body or {}
        if body.get("code") != "tool_use_failed":
            return None
        return json.loads(body.get("failed_generation", "[]"))
    except Exception:
        return None


def _coerce_tool_args(tool_name: str, args: dict) -> dict:
    """Cast string integers, drop empty optional ints, and fix datetime format."""
    _INT_FIELDS: dict[str, set[str]] = {
        "get_masters": {"service_id"},
        "get_available_slots": {"service_id", "master_id"},
        "create_booking": {"service_id", "master_id"},
    }
    int_fields = _INT_FIELDS.get(tool_name, set())
    result = {}
    for k, v in args.items():
        if k in int_fields:
            if v == "" or v is None:
                continue
            try:
                result[k] = int(v)
            except (ValueError, TypeError):
                result[k] = v
        elif k == "datetime" and isinstance(v, str) and len(v) == 16:
            result[k] = v + ":00"  # "2026-04-30T11:30" → "2026-04-30T11:30:00"
        else:
            result[k] = v
    return result


def _to_openai_tools(tools: list) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t.get(
                    "input_schema", {"type": "object", "properties": {}}
                ),
            },
        }
        for t in tools
    ]


async def _load_conversation_history(conversation) -> list[dict]:
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
        if msg.tool_calls_json:
            history.append(
                {
                    "role": "assistant",
                    "content": msg.content or None,
                    "tool_calls": msg.tool_calls_json,
                }
            )
        elif msg.tool_results_json:
            for r in msg.tool_results_json:
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": r["tool_call_id"],
                        "content": r["content"],
                    }
                )
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


async def _save_tool_turn(conversation, tool_calls: list, tool_results: list) -> None:
    from .models import Message

    await Message.objects.acreate(
        conversation=conversation,
        direction="out",
        role="assistant",
        content="",
        tool_calls_json=tool_calls,
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
    openai_tools = _to_openai_tools(tools)
    total_input = 0
    total_output = 0
    start = time.monotonic()

    full_messages = [{"role": "system", "content": system_prompt}] + messages

    for iteration in range(max_iterations):
        try:
            api_response = await client.chat.completions.create(
                model=salon.ai_model,
                messages=full_messages,
                tools=openai_tools,
                max_tokens=1024,
            )
        except openai.BadRequestError as exc:
            raw_calls = _extract_failed_tool_calls(exc)
            if raw_calls is None:
                raise
            tool_results = []
            serialized_calls = []
            for i, call in enumerate(raw_calls):
                tc_name = call.get("name", "")
                tc_args = _coerce_tool_args(tc_name, call.get("parameters", {}))
                tc_id = f"call_coerced_{iteration}_{i}"
                result = await execute_tool(
                    tool_name=tc_name,
                    tool_input=tc_args,
                    salon=salon,
                    conversation=conversation,
                )
                tool_results.append(
                    {
                        "tool_call_id": tc_id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
                serialized_calls.append(
                    {
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": tc_name,
                            "arguments": json.dumps(tc_args, ensure_ascii=False),
                        },
                    }
                )
            full_messages.append(
                {"role": "assistant", "content": None, "tool_calls": serialized_calls}
            )
            for tr in tool_results:
                full_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tr["tool_call_id"],
                        "content": tr["content"],
                    }
                )
            await _save_tool_turn(conversation, serialized_calls, tool_results)
            continue

        usage = api_response.usage
        if usage:
            total_input += usage.prompt_tokens
            total_output += usage.completion_tokens

        choice = api_response.choices[0]
        finish_reason = choice.finish_reason

        logger.info(
            "llm_call",
            salon_id=salon.id,
            iteration=iteration,
            finish_reason=finish_reason,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

        if finish_reason == "stop":
            text = choice.message.content or "Извините, не могу ответить прямо сейчас."
            latency = int((time.monotonic() - start) * 1000)
            return AIResponse(
                text=text,
                tokens_input=total_input,
                tokens_output=total_output,
                cost_usd=_calculate_cost(total_input, total_output),
                latency_ms=latency,
            )

        if finish_reason == "tool_calls":
            tool_calls = choice.message.tool_calls
            tool_results = []
            serialized_calls = []

            for tc in tool_calls:
                tool_input = json.loads(tc.function.arguments)
                result = await execute_tool(
                    tool_name=tc.function.name,
                    tool_input=tool_input,
                    salon=salon,
                    conversation=conversation,
                )
                tool_results.append(
                    {
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
                serialized_calls.append(
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )

            full_messages.append(
                {
                    "role": "assistant",
                    "content": choice.message.content,
                    "tool_calls": [tc.model_dump() for tc in tool_calls],
                }
            )
            for tr in tool_results:
                full_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tr["tool_call_id"],
                        "content": tr["content"],
                    }
                )

            await _save_tool_turn(conversation, serialized_calls, tool_results)
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
