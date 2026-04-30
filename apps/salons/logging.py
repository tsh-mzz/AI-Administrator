"""Structlog processor that masks PII (phone numbers, client names) in log events."""

_PII_KEYS = frozenset({"client_phone", "phone", "client_name", "name"})


def mask_pii(logger, method, event_dict):
    """Mask PII fields recursively in the event dict."""

    def _process(d):
        if not isinstance(d, dict):
            return d
        return {
            k: (
                _mask_value(v)
                if k in _PII_KEYS
                else _process(v)
                if isinstance(v, dict)
                else v
            )
            for k, v in d.items()
        }

    def _mask_value(v):
        if isinstance(v, str) and len(v) > 3:
            return v[:3] + "***"
        return v

    for key, value in list(event_dict.items()):
        if isinstance(value, dict):
            event_dict[key] = _process(value)

    return event_dict
