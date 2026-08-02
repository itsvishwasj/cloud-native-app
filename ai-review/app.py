from fastapi import FastAPI

app = FastAPI(
    title="AI Code Review Service",
    version="1.0"
)

@app.get("/")
def home():
    return {
        "status": "Running",
        "service": "AI Code Review"
    }
print("Testing AI Review")
