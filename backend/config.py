import os
from dotenv import load_dotenv

load_dotenv()

# API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NUNCHAKU_API_KEY = os.getenv("NUNCHAKU_API_KEY")

# Nunchaku settings
NUNCHAKU_MODEL = "nunchaku-flux.2-klein-9b"
NUNCHAKU_TIER = "fast"
NUNCHAKU_BASE_URL = "https://api.nunchaku.dev"
NUNCHAKU_NEGATIVE_PROMPT = (
    "text, words, letters, signs, labels, watermark, logo, UI elements, captions"
)

# Claude settings
CLAUDE_MODEL = "claude-sonnet-4-6"

# System prompt
SYSTEM_PROMPT = """
You are a visual companion generator for language learning videos. Given a transcript with
timestamps, identify 1 visual concept every 20-30 seconds that is concrete and visualizable.

For each concept return:
- timestamp_seconds (integer)
- concept (the word or phrase in the original language)
- image_prompt (English image generation prompt)

Rules for image_prompts:
- Describe only visual elements — no text, signs, labels, letters, or words anywhere in the scene
- Simple composition with one clear primary subject
- Translate concepts to English even if the transcript is in another language
- Skip abstract or non-visual moments — pick the next concrete one instead
- End every prompt with: "children's storybook illustration, simple composition, one main \
subject, soft colors, painterly, no text, no letters"

Output a JSON array only. No preamble, no explanation, no markdown.
"""
