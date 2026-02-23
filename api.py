"""HTTP API for the board game cafe assistant."""

from fastapi import FastAPI
from pydantic import BaseModel

from agent import run_agent
from database import init_db, DB_PATH

app = FastAPI(
    title="Board Game Cafe Assistant API",
    description="Natural language queries against cafe data",
    version="1.0.0",
)


# Initialize DB on startup
@app.on_event("startup")
def startup():
    if not DB_PATH.exists():
        init_db()


class Query(BaseModel):
    question: str
    conversation_history: list[dict] = []


class Answer(BaseModel):
    answer: str


@app.post("/ask", response_model=Answer)
def ask_question(query: Query) -> Answer:
    """
    Ask a natural language question about the cafe's data.

    Optionally include conversation_history for follow-up questions.
    """
    answer = run_agent(
        query.question,
        conversation_history=query.conversation_history or None,
    )
    return Answer(answer=answer)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
