import os
import google.generativeai as genai

try:
    from model.config import GEMINI_API_KEY
except ImportError:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3.6-flash")

def get_answer(question):
    try:
        prompt = f"You are GreenMind's AI assistant. Answer the following question briefly and helpfully (max 4-5 sentences).\n\nQuestion: {question}"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return "Sorry, I couldn't process that right now. Please try again."   