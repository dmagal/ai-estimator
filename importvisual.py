from flask import Flask, request, jsonify
import os
from openai import OpenAI

# Initialize OpenAI client using environment variable
client = OpenAI()

app = Flask(__name__)

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()

    # If data comes in as a list, grab the first item
    if isinstance(data, list):
        data = data[0]

    text = data.get("text", "")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    prompt = f"You are a helpful assistant. Convert the following extracted receipt or invoice text into structured CSV data with proper columns.\n\n{text}"

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        result = response.choices[0].message.content.strip()
        print("CSV result from GPT:\n", result)
        return jsonify({"csv": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
