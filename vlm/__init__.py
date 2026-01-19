"""
VLM Validation Module

Simple validation system for near-miss detection using Vision-Language Models.
"""

__version__ = "2.0.0"

from .vlm_backend import validate_event
from .prompts import get_system_prompt, format_event_metrics
from .utils import parse_validation_response

__all__ = [
    'validate_event',
    'get_system_prompt',
    'format_event_metrics',
    'parse_validation_response',
]
