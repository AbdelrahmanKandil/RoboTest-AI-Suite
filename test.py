from google import genai

client = genai.Client(api_key="AIzaSyBKbU6UjiuNfQotTcy6iXuSmzrwI-Q4Hw8")

for m in client.models.list():
    print(m.name)
