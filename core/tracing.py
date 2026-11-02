# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — OpenTelemetry Tracing (setup + fallback no-op)
# ------------------------------------------------------------------------------
# Fournit :
#   • init_tracing(app=None)         → initialise OTel + instrumente FastAPI
#   • instrument_fastapi(app)        → instrumente une app FastAPI déjà créée
#   • get_tracer(name)               → retourne un tracer (ou no-op si OTel absent)
#   • span(name, **attrs)            → context manager pour créer un span
#   • set_span_attribute(key, value) → ajoute un attribut au span courant
#   • set_span_status_ok() / set_span_status_error(msg)
#   • get_current_trace_id()         → utile pour lier logs & traces
#
# Sans OTel configuré → tout devient no-op silencieux, aucun crash.
#
# Variables d'environnement :
#   OTEL_ENABLED            : true | false          (défaut: true si installé)
#   OTEL_SERVICE_NAME       : bek-v16-hybrid        (défaut)
#   OTEL_EXPORTER_ENDPOINT  : http://localhost:4317 (défaut, gRPC OTLP)
#   OTEL_SAMPLE_RATIO       : 1.0                   (défaut, tout tracer)
#   OTEL_CONSOLE_EXPORT     : false                 (défaut, mettre true pour debug)
# ==============================================================================

from __future__ import annotations

import contextlib
import logging
import os
from typing import Any, Optional

logger = logging.getLogger("bek.tracing")

# ─── Détection OTel ─────────────────────────────────────────────────────────
_OTEL_AVAILABLE = False
try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )
    from opentelemetry.trace import Status, StatusCode, Span
    _OTEL_AVAILABLE = True
except ImportError:
    trace = None  # type: ignore
    Resource = None  # type: ignore
    TracerProvider = None  # type: ignore
    BatchSpanProcessor = None  # type: ignore
    ConsoleSpanExporter = None  # type: ignore
    Status = None  # type: ignore
    StatusCode = None  # type: ignore
    Span = None  # type: ignore
    logger.info("[Tracing] OpenTelemetry non installé → mode no-op")


# ─── État global ────────────────────────────────────────────────────────────
_INITIALIZED = False
_TRACER_NAME = "bek"
_DEFAULT_NOOP_TRACER = None


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# ─── Init ───────────────────────────────────────────────────────────────────
def init_tracing(app: Any = None) -> bool:
    """
    Initialise OpenTelemetry :
        - Crée un TracerProvider (Resource = service.name)
        - Ajoute un exporter OTLP (gRPC) vers OTEL_EXPORTER_ENDPOINT
        - Ajoute éventuellement un ConsoleExporter (si OTEL_CONSOLE_EXPORT=true)
        - Instrumente FastAPI si `app` est fourni

    Retourne True si l'init a réussi, False sinon (fallback no-op).
    Idempotent : peut être appelé plusieurs fois sans risque.
    """
    global _INITIALIZED

    if _INITIALIZED:
        return True

    # OTel absent → no-op
    if not _OTEL_AVAILABLE:
        logger.info("[Tracing] init ignoré (OTel non installé)")
        return False

    # Désactivé explicitement
    if not _env_bool("OTEL_ENABLED", default=True):
        logger.info("[Tracing] init ignoré (OTEL_ENABLED=false)")
        return False

    try:
        service_name = os.getenv("OTEL_SERVICE_NAME", "bek-v16-hybrid")
        sample_ratio = _env_float("OTEL_SAMPLE_RATIO", 1.0)
        endpoint = os.getenv("OTEL_EXPORTER_ENDPOINT", "http://localhost:4317")
        console_export = _env_bool("OTEL_CONSOLE_EXPORT", default=False)

        resource = Resource.create({SERVICE_NAME: service_name})

        # Sampler : toujours par défaut (1.0)
        try:
            from opentelemetry.sdk.trace.sampling import (
                ParentBased,
                TraceIdRatioBased,
            )
            sampler = ParentBased(root=TraceIdRatioBased(sample_ratio))
        except Exception:
            sampler = None

        provider_kwargs = {"resource": resource}
        if sampler is not None:
            provider_kwargs["sampler"] = sampler

        provider = TracerProvider(**provider_kwargs)

        # Exporter OTLP (gRPC) si endpoint défini
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info(
                "[Tracing] Exporteur OTLP configuré → %s (service=%s, ratio=%.2f)",
                endpoint, service_name, sample_ratio,
            )
        except ImportError:
            logger.warning(
                "[Tracing] opentelemetry-exporter-otlp non installé → pas d'export réseau"
            )
        except Exception as exc:
            logger.warning("[Tracing] Exporteur OTLP indisponible : %s", exc)

        # ConsoleExporter (debug)
        if console_export:
            try:
                provider.add_span_processor(
                    BatchSpanProcessor(ConsoleSpanExporter())
                )
                logger.info("[Tracing] ConsoleExporter activé (OTEL_CONSOLE_EXPORT=true)")
            except Exception as exc:
                logger.warning("[Tracing] ConsoleExporter indisponible : %s", exc)

        trace.set_tracer_provider(provider)

        # Instrumentation FastAPI
        if app is not None:
            instrument_fastapi(app)

        # Instrumentation httpx (utilisé par Pinecone etc.)
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            HTTPXClientInstrumentor().instrument()
            logger.info("[Tracing] httpx instrumenté")
        except Exception:
            pass

        # Instrumentation requests (utilisé par providers LLM)
        try:
            from opentelemetry.instrumentation.requests import RequestsInstrumentor
            RequestsInstrumentor().instrument()
            logger.info("[Tracing] requests instrumenté")
        except Exception:
            pass

        # Instrumentation logging (ajoute trace_id dans les logs)
        try:
            from opentelemetry.instrumentation.logging import LoggingInstrumentor
            LoggingInstrumentor().instrument(set_logging_format=False)
            logger.info("[Tracing] logging instrumenté (trace_id injecté)")
        except Exception:
            pass

        _INITIALIZED = True
        logger.info("✅ [Tracing] OpenTelemetry initialisé")
        return True

    except Exception as exc:
        logger.error("[Tracing] Échec init OpenTelemetry : %s", exc, exc_info=True)
        return False


def instrument_fastapi(app: Any) -> None:
    """Instrumente une app FastAPI existante (spans HTTP auto)."""
    if not _OTEL_AVAILABLE or app is None:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("[Tracing] FastAPI instrumenté")
    except Exception as exc:
        logger.warning("[Tracing] FastAPI instrumentation échouée : %s", exc)


# ─── API pour les modules métier ────────────────────────────────────────────
def get_tracer(name: str = _TRACER_NAME) -> Any:
    """Retourne un tracer OTel (ou no-op si OTel absent)."""
    if not _OTEL_AVAILABLE or not _INITIALIZED:
        return _NoopTracer()
    try:
        return trace.get_tracer(name)
    except Exception:
        return _NoopTracer()


@contextlib.contextmanager
def span(name: str, **attributes: Any):
    """
    Context manager pour tracer une opération.

    Usage :
        with span("my.operation", user_id=42):
            ...
    """
    if not _OTEL_AVAILABLE or not _INITIALIZED:
        # No-op
        yield _NoopSpan()
        return

    tracer = trace.get_tracer(_TRACER_NAME)
    with tracer.start_as_current_span(name) as s:
        for k, v in attributes.items():
            try:
                s.set_attribute(k, v)
            except Exception:
                pass
        try:
            yield s
        except Exception as exc:
            try:
                s.record_exception(exc)
                s.set_status(Status(StatusCode.ERROR, str(exc)))
            except Exception:
                pass
            raise


def set_span_attribute(key: str, value: Any) -> None:
    """Ajoute un attribut au span courant (no-op si hors span)."""
    if not _OTEL_AVAILABLE or not _INITIALIZED:
        return
    try:
        current = trace.get_current_span()
        if current is not None and current.is_recording():
            current.set_attribute(key, value)
    except Exception:
        pass


def set_span_status_ok() -> None:
    """Marque le span courant comme OK."""
    if not _OTEL_AVAILABLE or not _INITIALIZED:
        return
    try:
        current = trace.get_current_span()
        if current is not None and current.is_recording():
            current.set_status(Status(StatusCode.OK))
    except Exception:
        pass


def set_span_status_error(message: str = "") -> None:
    """Marque le span courant comme ERROR."""
    if not _OTEL_AVAILABLE or not _INITIALIZED:
        return
    try:
        current = trace.get_current_span()
        if current is not None and current.is_recording():
            current.set_status(Status(StatusCode.ERROR, message or "error"))
    except Exception:
        pass


def get_current_trace_id() -> str:
    """Retourne le trace_id du span courant en hex (ou '')."""
    if not _OTEL_AVAILABLE or not _INITIALIZED:
        return ""
    try:
        current = trace.get_current_span()
        if current is None:
            return ""
        ctx = current.get_span_context()
        if not ctx or not ctx.is_valid:
            return ""
        return format(ctx.trace_id, "032x")
    except Exception:
        return ""


def shutdown_tracing() -> None:
    """Arrête proprement le TracerProvider (flush des spans en attente)."""
    global _INITIALIZED
    if not _OTEL_AVAILABLE or not _INITIALIZED:
        return
    try:
        provider = trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
        logger.info("[Tracing] TracerProvider arrêté proprement")
    except Exception:
        pass
    _INITIALIZED = False


# ─── No-op fallback (OTel absent) ───────────────────────────────────────────
class _NoopSpan:
    def set_attribute(self, *a: Any, **kw: Any) -> None: pass
    def record_exception(self, *a: Any, **kw: Any) -> None: pass
    def set_status(self, *a: Any, **kw: Any) -> None: pass
    def is_recording(self) -> bool: return False
    def get_span_context(self) -> Any: return None
    def __enter__(self) -> "_NoopSpan": return self
    def __exit__(self, *a: Any) -> None: return None


class _NoopTracer:
    def start_as_current_span(self, *a: Any, **kw: Any) -> "_NoopSpan":
        return _NoopSpan()
    def start_span(self, *a: Any, **kw: Any) -> "_NoopSpan":
        return _NoopSpan()


# ─── Test direct ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    print("=== Test 1 : init sans OTel configuré ===")
    ok = init_tracing()
    print(f"init_tracing() = {ok}")

    print("\n=== Test 2 : span no-op ===")
    with span("test.operation", foo="bar") as s:
        print(f"span actif = {s.is_recording()}")
        set_span_attribute("custom.attr", 42)
        set_span_status_ok()

    print("\n=== Test 3 : get_current_trace_id ===")
    tid = get_current_trace_id()
    print(f"trace_id = {tid!r}  (vide si hors span)")

    print("\n=== Test 4 : erreur dans un span ===")
    try:
        with span("test.error"):
            raise RuntimeError("boom")
    except RuntimeError:
        print("exception bien propagée")

    shutdown_tracing()
    print("\n✅ Tests terminés")