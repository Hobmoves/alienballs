from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

def call_groq_api(search_value):
    prompt = f"""
You are an AI assistant helping generate alien terrain for Minecraft.

Write a JavaScript function named `generateBiome` that returns an array of block objects for a 300x300 terrain grid. Each block object must be in the format:

    {{ x: int, y: int, z: int, block: "minecraft:block_id" }}

Requirements:
- x, z from 0 to 299
- y from -64 to 256, base terrain around 65 ± 15
- Include your own perlinNoise2D(x, z) function (no external libs)
- Use Perlin noise for height variation

Example: Volcanic biome with blackstone surface, basalt and stone subsurface, lava pools, obsidian craters.

Return only one valid JavaScript file with:
- a self-contained generateBiome() function
- perlinNoise2D() implementation
- no comments or explanations

Biome theme: "{search_value}"
"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "deepseek-r1-distill-llama-70b",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4000
    }

    response = requests.post(GROQ_API_URL, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()

    if not result.get("choices") or not result["choices"][0].get("message", {}).get("content"):
        raise ValueError("Invalid response from Groq API")

    return result["choices"][0]["message"]["content"]

@app.route("/generate", methods=["POST"])
def generate_biome():
    try:
        data = request.get_json(force=True)
        search_value = data.get("search", "").strip()
        if not search_value:
            return jsonify({"error": "Missing 'search' value"}), 400

        js_code = call_groq_api(search_value)
        return jsonify({"js_code": js_code})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
