"""Tests for Prometheus format parser."""

import pytest

from collector.parser import (
    Metric,
    ParsedMetrics,
    parse_labels,
    parse_prometheus_text,
    parse_value,
)


class TestParseLabels:
    """Tests for label parsing."""
    
    def test_empty_labels(self):
        """Test parsing empty label string."""
        assert parse_labels("") == {}
    
    def test_single_label(self):
        """Test parsing single label."""
        result = parse_labels('cpu="0"')
        assert result == {"cpu": "0"}
    
    def test_multiple_labels(self):
        """Test parsing multiple labels."""
        result = parse_labels('cpu="0",mode="idle"')
        assert result == {"cpu": "0", "mode": "idle"}
    
    def test_label_with_special_chars(self):
        """Test parsing label with escaped characters."""
        result = parse_labels('path="/home/user"')
        assert result == {"path": "/home/user"}
    
    def test_label_with_escaped_quote(self):
        """Test parsing label with escaped quote."""
        result = parse_labels('name="test\\"value"')
        assert result == {"name": 'test"value'}


class TestParseValue:
    """Tests for value parsing."""
    
    def test_integer(self):
        """Test parsing integer value."""
        assert parse_value("123") == 123.0
    
    def test_float(self):
        """Test parsing float value."""
        assert parse_value("123.456") == 123.456
    
    def test_scientific_notation(self):
        """Test parsing scientific notation."""
        assert parse_value("1.5e10") == 1.5e10
    
    def test_positive_infinity(self):
        """Test parsing positive infinity."""
        assert parse_value("+Inf") == float("inf")
        assert parse_value("Inf") == float("inf")
    
    def test_negative_infinity(self):
        """Test parsing negative infinity."""
        assert parse_value("-Inf") == float("-inf")
    
    def test_nan(self):
        """Test parsing NaN."""
        import math
        assert math.isnan(parse_value("NaN"))


class TestParsePrometheusText:
    """Tests for full Prometheus text parsing."""
    
    def test_empty_input(self):
        """Test parsing empty input."""
        result = parse_prometheus_text("")
        assert len(result.metrics) == 0
    
    def test_single_metric(self):
        """Test parsing single metric."""
        text = 'node_load1 1.5'
        result = parse_prometheus_text(text)
        
        assert len(result.metrics) == 1
        assert result.metrics[0].name == "node_load1"
        assert result.metrics[0].value == 1.5
        assert result.metrics[0].labels == {}
    
    def test_metric_with_labels(self):
        """Test parsing metric with labels."""
        text = 'node_cpu_seconds_total{cpu="0",mode="idle"} 10000.5'
        result = parse_prometheus_text(text)
        
        assert len(result.metrics) == 1
        assert result.metrics[0].name == "node_cpu_seconds_total"
        assert result.metrics[0].value == 10000.5
        assert result.metrics[0].labels == {"cpu": "0", "mode": "idle"}
    
    def test_skip_comments(self):
        """Test that comments are skipped."""
        text = """
# HELP node_load1 1m load average.
# TYPE node_load1 gauge
node_load1 1.5
"""
        result = parse_prometheus_text(text)
        
        assert len(result.metrics) == 1
        assert result.metrics[0].name == "node_load1"
    
    def test_skip_empty_lines(self):
        """Test that empty lines are skipped."""
        text = """
node_load1 1.5

node_load5 1.2
"""
        result = parse_prometheus_text(text)
        
        assert len(result.metrics) == 2
    
    def test_full_node_exporter_output(self, sample_node_exporter_output):
        """Test parsing full Node Exporter output."""
        result = parse_prometheus_text(sample_node_exporter_output)
        
        # Check that metrics were parsed
        assert len(result.metrics) > 0
        
        # Check specific metrics
        assert result.get_metric_value("node_load1") == 1.5
        assert result.get_metric_value("node_load5") == 1.2
        assert result.get_metric_value("node_memory_MemTotal_bytes") == 17179869184
    
    def test_full_dcgm_output(self, sample_dcgm_output):
        """Test parsing full DCGM output."""
        result = parse_prometheus_text(sample_dcgm_output)
        
        assert len(result.metrics) > 0
        assert result.get_metric_value("DCGM_FI_DEV_GPU_UTIL") == 35.0
        assert result.get_metric_value("DCGM_FI_DEV_GPU_TEMP") == 48.0


class TestParsedMetrics:
    """Tests for ParsedMetrics class."""
    
    def test_get_metrics_by_name(self):
        """Test getting metrics by name."""
        metrics = ParsedMetrics(metrics=[
            Metric(name="cpu", value=1.0, labels={"cpu": "0"}),
            Metric(name="cpu", value=2.0, labels={"cpu": "1"}),
            Metric(name="memory", value=100.0),
        ])
        
        cpu_metrics = metrics.get_metrics_by_name("cpu")
        assert len(cpu_metrics) == 2
        
        mem_metrics = metrics.get_metrics_by_name("memory")
        assert len(mem_metrics) == 1
    
    def test_get_metric_value_with_labels(self):
        """Test getting metric value with label filter."""
        metrics = ParsedMetrics(metrics=[
            Metric(name="cpu", value=1.0, labels={"cpu": "0", "mode": "idle"}),
            Metric(name="cpu", value=2.0, labels={"cpu": "0", "mode": "user"}),
        ])
        
        idle_value = metrics.get_metric_value("cpu", labels={"mode": "idle"})
        assert idle_value == 1.0
        
        user_value = metrics.get_metric_value("cpu", labels={"mode": "user"})
        assert user_value == 2.0
    
    def test_get_metric_value_default(self):
        """Test default value when metric not found."""
        metrics = ParsedMetrics(metrics=[])
        
        value = metrics.get_metric_value("nonexistent", default=42.0)
        assert value == 42.0
    
    def test_get_all_values(self):
        """Test getting all values for a metric."""
        metrics = ParsedMetrics(metrics=[
            Metric(name="cpu", value=1.0, labels={"cpu": "0"}),
            Metric(name="cpu", value=2.0, labels={"cpu": "1"}),
        ])
        
        all_values = metrics.get_all_values("cpu")
        assert len(all_values) == 2
        assert ({"cpu": "0"}, 1.0) in all_values
        assert ({"cpu": "1"}, 2.0) in all_values
