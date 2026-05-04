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

_COST_INPUT_PER_M = Decimal("0.15")  # gpt-4o-mini input  $/1M tokens
_COST_OUTPUT_PER_M = Decimal("0.60")  # gpt-4o-mini output $/1M tokens

_DEFAULT_MODEL = "gpt-4o-mini"


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
        api_key=settings.OPENAI_API_KEY,
    )


def _calculate_cost(tokens_input: int, tokens_output: int) -> Decimal:
    return (
        Decimal(tokens_input) / Decimal(1_000_000) * _COST_INPUT_PER_M
        + Decimal(tokens_output) / Decimal(1_000_000) * _COST_OUTPUT_PER_M
    )


def _extract_failed_tool_calls(exc: openai.BadRequestError) -> list | None:
    """Defensive: parse Groq tool_use_failed errors. Rarely fires with OpenAI.

    Keep for a few weeks as a fallback layer.
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

    summarized_through_id = (conversation.context_json or {}).get("summarized_through_id", 0)
    summary = (conversation.context_json or {}).get("summary", "")

    qs = Message.objects.filter(conversation=conversation).exclude(role="system")
    if summarized_through_id:
        qs = qs.filter(id__gt=summarized_through_id)

    messages = []
    async for msg in qs.order_by("-created_at")[:20]:
        messages.append(msg)
    messages.reverse()

    history = []

    if summary:
        history.append({
            "role": "system",
            "content": f"Краткое содержание предыдущей части разговора: {summary}",
        })

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

    # Drop orphan tool messages whose introducing assistant.tool_calls was
    # truncated off by the 20-message window. OpenAI 400s on tool messages
    # without a preceding tool_calls message in the same payload.
    known_tool_call_ids: set[str] = set()
    cleaned: list[dict] = []
    for entry in history:
        if entry["role"] == "assistant" and entry.get("tool_calls"):
            for tc in entry["tool_calls"]:
                tc_id = (
                    tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                )
                if tc_id:
                    known_tool_call_ids.add(tc_id)
            cleaned.append(entry)
        elif entry["role"] == "tool":
            if entry.get("tool_call_id") in known_tool_call_ids:
                cleaned.append(entry)
        else:
            cleaned.append(entry)

    return cleaned


async def _maybe_compress_history(conversation) -> None:
    from .models import Message

    summarized_through_id = (conversation.context_json or {}).get("summarized_through_id", 0)

    total = await Message.objects.filter(
        conversation=conversation,
        role__in=["user", "assistant"],
        id__gt=summarized_through_id,
    ).acount()

    if total <= 20:
        return

    # Keep the 10 most recent messages raw; summarize everything older
    keep_ids = [
        msg.id async for msg in (
            Message.objects.filter(
                conversation=conversation,
                role__in=["user", "assistant"],
                id__gt=summarized_through_id,
            ).order_by("-created_at")[:10]
        )
    ]

    old_messages = [
        msg async for msg in (
            Message.objects.filter(
                conversation=conversation,
                role__in=["user", "assistant"],
                id__gt=summarized_through_id,
            ).exclude(id__in=keep_ids).order_by("created_at")
        )
    ]

    if not old_messages:
        return

    lines = []
    for msg in old_messages:
        prefix = "Клиент" if msg.role == "user" else "Бот"
        lines.append(f"{prefix}: {msg.content[:300]}")

    client = _get_client()
    try:
        resp = await client.chat.completions.create(
            model=_DEFAULT_MODEL,
            messages=[{
                "role": "user",
                "content": (
                    "Кратко суммируй этот диалог в 3-5 предложениях. "
                    "Укажи: что хотел клиент, что обсуждали, какие услуги/мастера/время рассматривались, "
                    "что было забронировано (если было), имя и телефон клиента (если назвал).\n\n"
                    + "\n".join(lines)
                ),
            }],
            max_tokens=300,
        )
        summary = resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("summarization_failed", error=str(exc))
        return

    context = dict(conversation.context_json or {})
    context["summary"] = summary
    context["summarized_through_id"] = old_messages[-1].id

    await conversation.__class__.objects.filter(pk=conversation.pk).aupdate(
        context_json=context
    )
    logger.info(
        "history_compressed",
        conversation_id=conversation.pk,
        messages_compressed=len(old_messages),
    )


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


async def _log_usage(
    conversation, model: str, prompt_tokens: int, completion_tokens: int
) -> None:
    from .models import AIUsageLog

    try:
        await AIUsageLog.objects.acreate(
            salon_id=conversation.salon_id,
            conversation=conversation,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    except Exception as exc:
        logger.warning("usage_log_failed", error=str(exc))


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
    model = salon.ai_model or _DEFAULT_MODEL

    full_messages = [{"role": "system", "content": system_prompt}] + messages

    for iteration in range(max_iterations):
        try:
            api_response = await client.chat.completions.create(
                model=model,
                messages=full_messages,
                tools=openai_tools,
                max_tokens=1024,
                parallel_tool_calls=False,
            )
        except openai.RateLimitError:
            logger.warning("openai_rate_limited", salon_id=salon.id, model=model)
            return AIResponse(
                text="Извините, сервис временно перегружен. Попробуйте через минуту.",
                tokens_input=total_input,
                tokens_output=total_output,
                latency_ms=int((time.monotonic() - start) * 1000),
            )
        except openai.APITimeoutError:
            logger.error("openai_timeout", salon_id=salon.id, model=model)
            return AIResponse(
                text="Извините, произошла техническая ошибка. Администратор свяжется с вами.",
                tokens_input=total_input,
                tokens_output=total_output,
                latency_ms=int((time.monotonic() - start) * 1000),
                escalate=True,
            )
        except openai.BadRequestError as exc:
            # Groq tool_use_failed defensive fallback — rarely fires with OpenAI
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
            logger.info(
                "llm_call",
                salon_id=salon.id,
                model=model,
                iteration=iteration,
                finish_reason=api_response.choices[0].finish_reason,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
            )
            await _log_usage(
                conversation, model, usage.prompt_tokens, usage.completion_tokens
            )

        choice = api_response.choices[0]
        finish_reason = choice.finish_reason

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
                tool_input = _coerce_tool_args(tc.function.name, tool_input)
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

    await _maybe_compress_history(conversation)

    return response
