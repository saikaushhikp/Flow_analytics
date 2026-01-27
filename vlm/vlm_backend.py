"""
Unified VLM backend with API-first approach and local fallback.

Uses LangChain for consistent interface across different VLM providers.
Priority: API (Gemini) → Local (Qwen) on error
"""

import os
import sys
from pathlib import Path
from typing import Dict, Tuple
import base64
from dotenv import load_dotenv

# Load .env file for API keys
load_dotenv(Path(__file__).parent.parent / '.env')

# Load config
sys.path.insert(0, str(Path(__file__).parent.parent))
from ssm.utils import load_config

config = load_config()
vlm_config = config.get('vlm', {})


def encode_image(image_path: str) -> str:
    """Encode image to base64 string."""
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def build_validation_prompt(event_data: dict) -> str:
    """
    Build VLM prompt with event context.
    
    Args:
        event_data: Event metrics from CSV
        
    Returns:
        Formatted prompt string
    """
    from prompts import build_prompt
    
    return build_prompt(event_data)


def validate_with_gemini(image_path: str, prompt: str) -> Dict:
    """
    Validate using Gemini API directly (without LangChain).
    
    Args:
        image_path: Path to trajectory plot
        prompt: Formatted prompt with event context
        
    Returns:
        Validation result dict
    """
    import google.generativeai as genai
    from PIL import Image
    import time
    
    # Get API key from environment
    api_key_env = vlm_config.get('gemini', {}).get('api_key_env', 'GEMINI_API_KEY')
    api_key = os.environ.get(api_key_env)
    
    if not api_key:
        raise ValueError(
            f"Gemini API key not found in environment variable: {api_key_env}\n"
            f"Set it with: export {api_key_env}='your_key_here'\n"
            f"Or create .env file with: {api_key_env}=your_key_here"
        )
    
    # Configure Gemini
    genai.configure(api_key=api_key)
    
    # Initialize model
    model_name = vlm_config.get('gemini', {}).get('model', 'gemini-1.5-flash-latest')
    model = genai.GenerativeModel(model_name)
    
    # Load image
    img = Image.open(image_path)
    
    # Rate limiting
    rate_limit_delay = vlm_config.get('gemini', {}).get('rate_limit_delay', 4)
    time.sleep(rate_limit_delay)
    
    # Generate response
    response = model.generate_content([prompt, img])
    
    # Parse response
    from vlm.utils import parse_validation_response
    result = parse_validation_response(response.text)
    result['backend'] = model_name
    
    return result


def validate_with_local(image_path: str, prompt: str) -> Dict:
    """
    Validate using local Qwen model.
    
    Args:
        image_path: Path to trajectory plot
        prompt: Formatted prompt with event context
        
    Returns:
        Validation result dict
    """
    from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
    from qwen_vl_utils import process_vision_info
    from PIL import Image
    import torch
    
    # Get model config
    model_id = vlm_config.get('local', {}).get('model_id', 'Qwen/Qwen2.5-VL-3B-Instruct')
    device = vlm_config.get('local', {}).get('device', 'auto')
    
    if device == 'auto':
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    print(f"  Loading local model: {model_id} on {device}...")
    
    # Load model
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        model_id,
        torch_dtype=torch.float32,  # CPU requires float32
        device_map=device if device == 'cuda' else None,
    )
    
    if device == 'cpu':
        model = model.to('cpu')
    
    processor = AutoProcessor.from_pretrained(model_id)
    
    # Prepare messages
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image_path},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    
    # Process
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    
    if device == 'cpu':
        inputs = {k: v.to('cpu') for k, v in inputs.items()}
    else:
        inputs = inputs.to(device)
    
    # Generate
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=512)
    
    generated_ids_trimmed = [
        out_ids[len(in_ids):] 
        for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    
    response_text = processor.batch_decode(
        generated_ids_trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False
    )[0]
    
    # Parse response
    from vlm.utils import parse_validation_response
    result = parse_validation_response(response_text)
    result['backend'] = f"local-{model_id.split('/')[-1]}"
    
    # Cleanup
    del model
    if device == 'cuda':
        torch.cuda.empty_cache()
    
    return result


def validate_event(plot_path: str, event_data: dict) -> Dict:
    """
    Main validation function with API-first, local-fallback strategy.
    
    Args:
        plot_path: Path to trajectory plot image
        event_data: Event metrics from CSV
        
    Returns:
        Validation result dict with keys:
        - classification: str (confirmed_near_miss / false_positive / uncertain)
        - confidence: int (0-100)
        - reasoning: str
        - backend: str (model name used)
    """
    # Verify image exists
    if not Path(plot_path).exists():
        raise FileNotFoundError(f"Plot not found: {plot_path}")
    
    # Build prompt
    prompt = build_validation_prompt(event_data)
    
    # Try API first
    preferred_backend = vlm_config.get('primary_backend', 'gemini')
    
    if preferred_backend == 'gemini':
        try:
            print("  Using Gemini API...")
            result = validate_with_gemini(plot_path, prompt)
            return result
        except Exception as api_error:
            print(f"  ⚠ API error: {api_error}")
            print("  Falling back to local model...")
            
            try:
                result = validate_with_local(plot_path, prompt)
                result['fallback_reason'] = str(api_error)
                return result
            except Exception as local_error:
                raise RuntimeError(
                    f"Both API and local validation failed.\n"
                    f"API error: {api_error}\n"
                    f"Local error: {local_error}"
                )
    
    elif preferred_backend == 'local':
        # User explicitly wants local
        result = validate_with_local(plot_path, prompt)
        return result
    
    else:
        raise ValueError(f"Unknown backend: {preferred_backend}")
