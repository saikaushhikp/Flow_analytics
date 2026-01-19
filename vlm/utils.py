"""
Utility functions for VLM response parsing.
"""

import re
from typing import Dict


def parse_validation_response(response_text: str) -> Dict:
    """
    Parse VLM response into structured format.
    
    Expected format:
        Classification: confirmed_near_miss
        Confidence: 85%
        Reasoning: [detailed explanation]
    
    Args:
        response_text: Raw VLM response
        
    Returns:
        Dictionary with parsed fields:
        - classification: str
        - confidence: int
        - reasoning: str
    """
    result = {
        'classification': 'uncertain',
        'confidence': 50,
        'reasoning': 'Failed to parse response',
    }
    
    # Normalize text
    text = response_text.strip()
    
    # Extract classification
    class_patterns = [
        r'Classification:\s*([^\n]+)',
        r'classification:\s*([^\n]+)',
        r'CLASSIFICATION:\s*([^\n]+)',
    ]
    
    for pattern in class_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            classification = match.group(1).strip().lower()
            # Normalize classification values
            if 'confirm' in classification or 'near' in classification or 'miss' in classification:
                result['classification'] = 'confirmed_near_miss'
            elif 'false' in classification or 'negative' in classification or 'not' in classification:
                result['classification'] = 'false_positive'
            else:
                result['classification'] = 'uncertain'
            break
    
    # Extract confidence
    conf_patterns = [
        r'Confidence:\s*(\d+)',
        r'confidence:\s*(\d+)',
        r'CONFIDENCE:\s*(\d+)',
        r'(\d+)%',
    ]
    
    for pattern in conf_patterns:
        match = re.search(pattern, text)
        if match:
            confidence = int(match.group(1))
            # Clamp to 0-100
            result['confidence'] = max(0, min(100, confidence))
            break
    
    # Extract reasoning
    reasoning_patterns = [
        r'Reasoning:\s*(.+?)(?=\n\n|\Z)',
        r'reasoning:\s*(.+?)(?=\n\n|\Z)',
        r'REASONING:\s*(.+?)(?=\n\n|\Z)',
    ]
    
    for pattern in reasoning_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            reasoning = match.group(1).strip()
            # Clean up reasoning
            reasoning = re.sub(r'\n+', '\n', reasoning)  # Remove multiple newlines
            reasoning = re.sub(r'^\s*-\s*', '', reasoning, flags=re.MULTILINE)  # Remove bullet points
            result['reasoning'] = reasoning
            break
    
    # If no structured format found, try to extract from free text
    if result['reasoning'] == 'Failed to parse response':
        # Use entire response as reasoning
        result['reasoning'] = text
        
        # Try to infer classification from keywords in text
        text_lower = text.lower()
        if any(word in text_lower for word in ['confirmed', 'genuine', 'valid near-miss', 'true near-miss']):
            result['classification'] = 'confirmed_near_miss'
        elif any(word in text_lower for word in ['false positive', 'not a near-miss', 'no collision risk']):
            result['classification'] = 'false_positive'
    
    return result
