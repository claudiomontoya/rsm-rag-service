from __future__ import annotations
import time
from collections import Counter, defaultdict, deque
from typing import Dict, Any, Deque
from dataclasses import dataclass, field
from threading import RLock

@dataclass
class MetricPoint:
    """Individual metric measurement."""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)

class MetricsRegistry:
    """Thread-safe metrics collection."""
    
    def __init__(self):
        self._lock = RLock()
        self._counters: Dict[str, Counter] = defaultdict(Counter)
        self._histograms: Dict[str, Deque[MetricPoint]] = defaultdict(lambda: deque(maxlen=1000))
        self._gauges: Dict[str, float] = {}
        
    def increment_counter(self, name: str, labels: Dict[str, str] = None, value: float = 1.0):
        """Increment a counter metric."""
        with self._lock:
            key = self._make_key(name, labels)
            self._counters[name][key] += value
    
    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a histogram value."""
        with self._lock:
            point = MetricPoint(
                timestamp=time.time(),
                value=value,
                labels=labels or {}
            )
            self._histograms[name].append(point)
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge value."""
        with self._lock:
            key = self._make_key(name, labels)
            self._gauges[key] = value
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics."""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "histograms": self._process_histograms(),
                "gauges": dict(self._gauges),
                "timestamp": time.time()
            }
    
    def _make_key(self, name: str, labels: Dict[str, str] = None) -> str:
        """Create metric key with labels."""
        if not labels:
            return name
        
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def _process_histograms(self) -> Dict[str, Any]:
        """Process histogram data into summaries."""
        processed = {}
        for name, points in self._histograms.items():
            if not points:
                continue
                
            values = [p.value for p in points]
            values.sort()
            
            n = len(values)
            processed[name] = {
                "count": n,
                "sum": sum(values),
                "min": min(values),
                "max": max(values),
                "mean": sum(values) / n,
                "p50": values[int(n * 0.5)] if n > 0 else 0,
                "p95": values[int(n * 0.95)] if n > 0 else 0,
                "p99": values[int(n * 0.99)] if n > 0 else 0,
            }
        
        return processed

# Global metrics registry
metrics_registry = MetricsRegistry()

def record_metric(metric_type: str, name: str, value: float = 1.0, labels: Dict[str, str] = None):
    """Record a metric of specified type."""
    if metric_type == "counter":
        metrics_registry.increment_counter(name, labels, value)
    elif metric_type == "histogram":
        metrics_registry.record_histogram(name, value, labels)
    elif metric_type == "gauge":
        metrics_registry.set_gauge(name, value, labels)

# Convenience functions
def inc_counter(name: str, labels: Dict[str, str] = None, value: float = 1.0):
    """Increment counter."""
    metrics_registry.increment_counter(name, labels, value)

def record_duration(name: str, duration_ms: float, labels: Dict[str, str] = None):
    """Record duration in milliseconds."""
    metrics_registry.record_histogram(name, duration_ms, labels)

def set_gauge(name: str, value: float, labels: Dict[str, str] = None):
    """Set gauge value."""
    metrics_registry.set_gauge(name, value, labels)