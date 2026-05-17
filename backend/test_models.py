import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

for model in ["gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-flash-latest"]:
    try:
        response = client.models.generate_content(model=model, contents='hi')
        print(f"SUCCESS with {model}")
    except Exception as e:
        print(f"FAILED {model}: {e}")
