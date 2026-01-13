"""Prometheus exposition format parser."""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Metric:
    """Represents a single Prometheus metric."""
    
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    
    def get_label(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a label value by key."""
        return self.labels.get(key, default)


@dataclass
class ParsedMetrics:
    """Collection of parsed metrics."""
    
    metrics: list[Metric] = field(default_factory=list)
    
    def get_metrics_by_name(self, name: str) -> list[Metric]:
        """Get all metrics with a given name."""
        return [m for m in self.metrics if m.name == name]
    
    def get_metric_value(
        self, 
        name: str, 
        labels: Optional[dict[str, str]] = None,
        default: float = 0.0
    ) -> float:
        """Get a single metric value by name and optional label filter.
        
        Args:
            name: Metric name
            labels: Optional dict of label key-value pairs to filter by
            default: Default value if metric not found
            
        Returns:
            Metric value or default
        """
        for metric in self.metrics:
            if metric.name != name:
                continue
            
            if labels is None:
                return metric.value
            
            # Check if all specified labels match
            if all(metric.labels.get(k) == v for k, v in labels.items()):
                return metric.value
        
        return default
    
    def get_all_values(self, name: str) -> list[tuple[dict[str, str], float]]:
        """Get all values for a metric name with their labels.
        
        Returns:
            List of (labels, value) tuples
        """
        return [(m.labels, m.value) for m in self.metrics if m.name == name]


# Regex patterns for parsing
METRIC_LINE_PATTERN = re.compile(
    r'^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)'
    r'(?:\{(?P<labels>[^}]*)\})?'
    r'\s+(?P<value>[+-]?(?:\d+\.?\d*|\d*\.?\d+)(?:[eE][+-]?\d+)?|[+-]?Inf|NaN)$'
)

LABEL_PATTERN = re.compile(
    r'(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*"(?P<value>(?:[^"\\]|\\.)*)"'
)


def parse_labels(label_str: str) -> dict[str, str]:
    """Parse label string into a dictionary.
    
    Args:
        label_str: Label string like 'cpu="0",mode="idle"'
        
    Returns:
        Dictionary of labels
    """
    labels = {}
    for match in LABEL_PATTERN.finditer(label_str):
        key = match.group("key")
        value = match.group("value")
        # Unescape escaped characters
        value = value.replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n')
        labels[key] = value
    return labels


def parse_value(value_str: str) -> float:
    """Parse a metric value string to float.
    
    Args:
        value_str: Value string like '123.45', '+Inf', '-Inf', 'NaN'
        
    Returns:
        Float value
    """
    value_str = value_str.strip()
    if value_str == "+Inf" or value_str == "Inf":
        return float("inf")
    elif value_str == "-Inf":
        return float("-inf")
    elif value_str == "NaN":
        return float("nan")
    else:
        return float(value_str)


def parse_prometheus_text(text: str) -> ParsedMetrics:
    """Parse Prometheus exposition format text.
    
    Args:
        text: Prometheus format text
        
    Returns:
        ParsedMetrics object containing all parsed metrics
    """
    metrics = []
    
    for line in text.splitlines():
        line = line.strip()
        
        # Skip empty lines, comments, HELP and TYPE lines
        if not line or line.startswith("#"):
            continue
        
        match = METRIC_LINE_PATTERN.match(line)
        if match:
            name = match.group("name")
            labels_str = match.group("labels") or ""
            value_str = match.group("value")
            
            labels = parse_labels(labels_str) if labels_str else {}
            value = parse_value(value_str)
            
            metrics.append(Metric(name=name, value=value, labels=labels))
    
    return ParsedMetrics(metrics=metrics)
