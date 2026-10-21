import json
import os
from typing import Any, Callable, Dict, Optional

from django.conf import settings

from hurricane.server.gateway import HurricaneASGIGateway, HurricaneWSGIGateway

_CONFIG: Dict[str, Any] = {
    "options": {},
    "check_func": None,
    "is_asgi": False,
    "include_probe": True,
}

_GATEWAY_INSTANCE: Optional[Any] = None
_PROBE_GATEWAY_INSTANCE: Optional[Any] = None


def _ensure_django_ready():
    import django

    if not django.apps.apps.ready:
        django.setup()


def _load_config():
    global _CONFIG
    if not _CONFIG.get("options") and "HURRICANE_GRANIAN_CONFIG" in os.environ:
        try:
            loaded = json.loads(os.environ["HURRICANE_GRANIAN_CONFIG"])
            _CONFIG["options"] = loaded.get("options", {})
            _CONFIG["is_asgi"] = loaded.get("is_asgi", False)
            _CONFIG["include_probe"] = loaded.get("include_probe", True)
        except Exception:
            pass


def configure_granian(
    options: Dict[str, Any],
    check_func: Optional[Callable] = None,
    is_asgi: bool = False,
    include_probe: bool = True,
):
    global _CONFIG, _GATEWAY_INSTANCE, _PROBE_GATEWAY_INSTANCE
    _CONFIG["options"] = options
    _CONFIG["check_func"] = check_func
    _CONFIG["is_asgi"] = is_asgi
    _CONFIG["include_probe"] = include_probe
    _GATEWAY_INSTANCE = None
    _PROBE_GATEWAY_INSTANCE = None

    try:
        clean_opts = {
            k: v for k, v in options.items() if isinstance(v, (int, float, str, bool, list, dict)) or v is None
        }
        os.environ["HURRICANE_GRANIAN_CONFIG"] = json.dumps(
            {
                "options": clean_opts,
                "is_asgi": is_asgi,
                "include_probe": include_probe,
            }
        )
    except Exception:
        pass


def is_asgi_configured() -> bool:
    _load_config()
    if _CONFIG.get("is_asgi"):
        return True
    return bool(getattr(settings, "ASGI_APPLICATION", None))


def get_application():
    global _GATEWAY_INSTANCE
    if _GATEWAY_INSTANCE is not None:
        return _GATEWAY_INSTANCE

    _ensure_django_ready()
    _load_config()

    options = _CONFIG.get("options", {})
    check_func = _CONFIG.get("check_func")
    include_probe = _CONFIG.get("include_probe", True)

    if is_asgi_configured():
        _GATEWAY_INSTANCE = HurricaneASGIGateway(
            options=options,
            check_func=check_func,
            include_probe=include_probe,
        )
    else:
        _GATEWAY_INSTANCE = HurricaneWSGIGateway(
            options=options,
            check_func=check_func,
            include_probe=include_probe,
        )
    return _GATEWAY_INSTANCE


def get_probe_application():
    global _PROBE_GATEWAY_INSTANCE
    if _PROBE_GATEWAY_INSTANCE is not None:
        return _PROBE_GATEWAY_INSTANCE

    _ensure_django_ready()
    _load_config()

    options = _CONFIG.get("options", {})
    check_func = _CONFIG.get("check_func")

    probe_options = dict(options)
    probe_options["static"] = False
    probe_options["media"] = False

    _PROBE_GATEWAY_INSTANCE = HurricaneWSGIGateway(
        options=probe_options,
        check_func=check_func,
        include_probe=True,
    )
    return _PROBE_GATEWAY_INSTANCE
