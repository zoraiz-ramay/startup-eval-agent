"""Benchmark reference schemas for startup evaluation.

Exposes the Tracxn benchmark (https://tracxn.com): the canonical set of
dimensions a credible startup profile should cover.
"""
from .tracxn import (
    BENCHMARK_NAME,
    BENCHMARK_SOURCE,
    DIMENSIONS,
    benchmark_coverage,
    map_field_to_dimension,
)

__all__ = [
    "BENCHMARK_NAME",
    "BENCHMARK_SOURCE",
    "DIMENSIONS",
    "benchmark_coverage",
    "map_field_to_dimension",
]
