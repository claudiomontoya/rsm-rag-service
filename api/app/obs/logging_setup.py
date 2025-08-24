from __future__ import annotations
import logging
import json
import sys
from typing import Dict, Any
from opentelemetry import trace
from opentelemetry.trace import format_trace_id, format_span_id

class StructuredFormatter(logging.Formatter):
    """JSON structured logging formatter with OpenTelemetry correlation."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        
        span = trace.get_current_span()
        span_context = span.get_span_context()
        
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if span_context.is_valid:
            log_entry.update({
                "trace_id": format_trace_id(span_context.trace_id),
                "span_id": format_span_id(span_context.span_id),
                "trace_flags": f"{span_context.trace_flags:02x}"
            })
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'lineno', 'funcName', 'created',
                'msecs', 'relativeCreated', 'thread', 'threadName',
                'processName', 'process', 'exc_info', 'exc_text', 'stack_info'
            }:
                extra_fields[key] = value
        
        if extra_fields:
            log_entry["extra"] = extra_fields
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)

def setup_logging(level: int = logging.INFO, structured: bool = True) -> None:
    """Configure application logging."""
    
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    
    if structured:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    
    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("qdrant_client").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    print(f"📝 Logging configured (structured={structured}, level={logging.getLevelName(level)})")

class ContextLogger:
    """Logger with automatic context enrichment."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def _add_context(self, extra: Dict[str, Any] = None) -> Dict[str, Any]:
        """Add contextual information to log entry."""
        context = extra or {}
        
        # Add trace information
        span = trace.get_current_span()
        if span.is_recording():
            context["span_name"] = span.name
        
        return context
    
    def debug(self, message: str, **kwargs):
        self.logger.debug(message, extra=self._add_context(kwargs))
    
    def info(self, message: str, **kwargs):
        self.logger.info(message, extra=self._add_context(kwargs))
    
    def warning(self, message: str, **kwargs):
        self.logger.warning(message, extra=self._add_context(kwargs))
    
    def error(self, message: str, **kwargs):
        self.logger.error(message, extra=self._add_context(kwargs))
    
    def exception(self, message: str, **kwargs):
        self.logger.exception(message, extra=self._add_context(kwargs))

def get_logger(name: str) -> ContextLogger:
    """Get context-aware logger."""
    return ContextLogger(name)