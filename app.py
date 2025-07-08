import os
import json
import time
import traceback
import logging
import gc
import psutil
from flask import Flask, request, jsonify
from groq import Groq

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Setup Flask App ---
app = Flask(__name__)
client = Groq(api_key="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")

MAX_CHARS = 10_000
MAX_ATTEMPTS = 3

COMMON_IMPORTS = """
import math
import random
import json
from collections import defaultdict
"""


# Root route for simple webpage
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Alienballs Terrain Generator</title>
    </head>
    <body>
        <h1>Alienballs Terrain Generator</h1>
        <p>The server is operational. Use the /generate endpoint to generate terrain.</p>
    </body>
    </html>
    """


@app.route("/generate", methods=["POST"])
def generate():
    try:
        input_data = request.get_json(force=True)
        search_value = input_data.get("search", "").strip()
        if not search_value:
            raise ValueError("No search value provided in POST body")

        script_output = call_groq_and_execute(search_value)
        chunked = convert_block_string_to_chunks(script_output)

        # Log memory usage
        process = psutil.Process()
        memory_info = process.memory_info()
        logger.info(f"Memory usage after request: {memory_info.rss / 1024 / 1024:.2f} MB")

        # Force garbage collection
        gc.collect()

        return jsonify(chunked)

    except Exception as e:
        logger.error(f"Generation failed: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Generation failed: {str(e)}"}), 500


def call_groq_and_execute(search_value: str) -> str:
    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info(f"Attempt {attempt} for theme: {search_value}")

            response = client.chat.completions.create(
                model="compound-beta-mini",
                messages=[
                    {
                        "role": "user",
                        "content": f"""
You are an AI assistant that generates Minecraft-style terrain using Python.

Write a Python script that:
- Uses ONLY the Python standard library
- Implements a simple noise function (like value or Perlin) with minimal memory usage
- Generates a 300x300 area
- y varies between 50–80, clamped to -64 to 256
- Each block is a dictionary: {{ "x": int, "y": int, "z": int, "block": str }}
- Use Minecraft block IDs without 'minecraft:' prefix (e.g., 'sand', 'dirt', 'cactus', 'stone')
- Add 5–10% special features (e.g., for desert: cacti, sandstone formations)
- Try to only generate areas that players would see, for example dont generate underground only the top layer
- At the end, print the block list as JSON using:
import json
print(json.dumps(blocks))
- Optimize for low memory usage (e.g., avoid large lists, use generators where possible)

Theme: "{search_value}"

Return ONLY code. No explanation. No markdown.
"""
                    }
                ],
                max_tokens=2000
            )

            script = response.choices[0].message.content
            if not script:
                raise ValueError("Groq returned no content")

            script = strip_code_blocks(script)
            full_script = COMMON_IMPORTS + "\n\n" + script

            # Capture printed output
            captured = {}

            def fake_print(x):
                captured.setdefault("result", str(x))

            exec_globals = {
                "__builtins__": __builtins__,
                "print": fake_print,
                "blocks": []
            }

            exec(full_script, exec_globals)

            if "result" not in captured:
                raise RuntimeError("Script did not print a result")

            return captured["result"]

        except Exception as e:
            logger.warning(f"Attempt {attempt} failed: {str(e)}")
            last_error = str(e)
            time.sleep(1)

    raise RuntimeError(f"All {MAX_ATTEMPTS} attempts failed. Last error: {last_error}")


def strip_code_blocks(text: str) -> str:
    lines = text.strip().splitlines()
    return "\n".join(line for line in lines if not line.strip().startswith("```")).strip()


def convert_block_string_to_chunks(raw_json: str) -> dict:
    blocks = json.loads(raw_json)
    chunks = {}
    current = ""
    piece_index = 1

    for block in blocks:
        x, y, z = block.get("x"), block.get("y"), block.get("z")
        block_id = block.get("block")
        if x is None or y is None or z is None or not block_id:
            continue

        line = f"{x},{y},{z};{block_id}"
        sep = "|" if current else ""

        if len(current) + len(sep) + len(line) > MAX_CHARS:
            chunks[piece_index] = current
            piece_index += 1
            current = line
        else:
            current += sep + line

    if current:
        chunks[piece_index] = current

    logger.info(f"Converted {len(blocks)} blocks into {len(chunks)} chunks")
    return chunks


# --- Run Application ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
