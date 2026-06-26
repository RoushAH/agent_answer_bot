"""HTTP API for the board game cafe assistant."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel

from agent import run_agent
from database import init_db, DB_PATH


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB on startup."""
    if not DB_PATH.exists():
        init_db()
    yield


app = FastAPI(
    title="Board Game Cafe Assistant API",
    description="Natural language queries against cafe data",
    version="1.0.0",
    lifespan=lifespan,
)


class Query(BaseModel):
    question: str
    conversation_history: list[dict] = []


class Answer(BaseModel):
    answer: str
    plan: str | None = None


@app.post("/ask", response_model=Answer)
def ask_question(query: Query) -> Answer:
    """
    Ask a natural language question about the cafe's data.

    Optionally include conversation_history for follow-up questions.
    """
    # For now, run_agent returns just the answer string
    # We could enhance it to return (answer, plan) tuple in the future
    answer = run_agent(
        query.question,
        conversation_history=query.conversation_history or None,
    )
    return Answer(answer=answer, plan=None)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
