"""
VLM Validation Module

Simple validation system for near-miss detection using Vision-Language Models.
"""

__version__ = "2.0.0"

__all__ = [
    'validate_event',
    'get_system_prompt',
    'format_event_metrics',
    'parse_validation_response',
]


def __getattr__(name):
    """Lazy-load optional VLM pieces so imports work without VLM dependencies."""
    if name == 'validate_event':
        from .vlm_backend import validate_event
        return validate_event
    if name in {'get_system_prompt', 'format_event_metrics'}:
        from .prompts import get_system_prompt, format_event_metrics
        return {'get_system_prompt': get_system_prompt, 'format_event_metrics': format_event_metrics}[name]
    if name == 'parse_validation_response':
        from .utils import parse_validation_response
        return parse_validation_response
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
