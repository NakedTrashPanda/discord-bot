import google.generativeai as genai
from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

def get_model(model_name="gemini-2.0-flash-exp"):
    return genai.GenerativeModel(model_name)

async def generate_text(prompt, model_name="gemini-2.0-flash-exp", max_tokens=1000):
    try:
        model = get_model(model_name)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return None

async def generate_with_grounding(prompt, model_name="gemini-2.0-flash-exp", max_tokens=1000):
    try:
        model = get_model(model_name)
        response = model.generate_content(
            prompt,
            tools="google_search_retrieval"
        )
        sources = []
        if hasattr(response, "grounding_metadata") and response.grounding_metadata:
            chunks = response.grounding_metadata.grounding_chunks
            for chunk in chunks:
                if hasattr(chunk, "web"):
                    sources.append({"title": chunk.web.title or "Source", "url": chunk.web.uri})
        return {"text": response.text, "sources": sources}
    except Exception as e:
        return {"text": None, "sources": [], "error": str(e)}

async def generate_structured(prompt, response_schema=None, model_name="gemini-2.0-flash-exp"):
    try:
        model = get_model(model_name)
        generation_config = {}
        if response_schema:
            generation_config["response_mime_type"] = "application/json"
            generation_config["response_schema"] = response_schema
        response = model.generate_content(prompt, generation_config=generation_config)
        return response.text
    except Exception as e:
        return None
