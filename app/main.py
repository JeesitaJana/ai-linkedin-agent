from fastapi import FastAPI

app = FastAPI(
    title="AI LinkedIn Content Automation Agent",
    description="Backend for an AI-powered LinkedIn content automation system.",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}