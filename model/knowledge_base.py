import google.generativeai as genai

genai.configure(api_key="AQ.Ab8RN6JAY4DY8zzgNk4bnqLs4ubIIiOznrPNqePmlq2Mo7nroA")

model = genai.GenerativeModel("gemini-1.5-flash")

def get_answer(question):
    try:
        prompt = f"""You are a helpful plant care assistant specialized in tomato plants (and general gardening).
Answer the following question in a friendly, concise way (max 4-5 sentences). 
If the question is not related to plants or gardening, politely say you can only help with plant-related questions.

Question: {question}
"""
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"ERROR: {str(e)}"