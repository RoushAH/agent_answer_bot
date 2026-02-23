"""Semantic search over board games using ChromaDB."""

import chromadb
from chromadb.config import Settings

from database import query_db, DB_PATH

# Persistent storage alongside the SQLite database
CHROMA_PATH = DB_PATH.parent / "chroma_db"

# Module-level client (initialized lazily)
_client = None
_collection = None


def _get_collection():
    """Get or create the ChromaDB collection."""
    global _client, _collection

    if _collection is not None:
        return _collection

    _client = chromadb.PersistentClient(
        path=str(CHROMA_PATH),
        settings=Settings(anonymized_telemetry=False),
    )

    _collection = _client.get_or_create_collection(
        name="board_games",
        metadata={"description": "Board game inventory for semantic search"},
    )

    return _collection


def init_search_index() -> int:
    """
    Initialize or refresh the search index from the database.

    Returns the number of games indexed.
    """
    collection = _get_collection()

    # Clear existing data
    existing = collection.get()
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    # Load games from database
    games = query_db("SELECT id, name, category, price, in_stock FROM board_games")

    if not games:
        return 0

    # Prepare documents for embedding
    # Combine name and category for richer semantic matching
    documents = [
        f"{game['name']} - {game['category']} game"
        for game in games
    ]

    # Metadata for retrieval
    metadatas = [
        {
            "name": game["name"],
            "category": game["category"],
            "price": game["price"],
            "in_stock": game["in_stock"],
        }
        for game in games
    ]

    # IDs as strings
    ids = [str(game["id"]) for game in games]

    # Add to collection (ChromaDB handles embedding automatically)
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )

    return len(games)


def search_games(query: str, n: int = 5) -> list[dict]:
    """
    Semantic search for board games.

    Args:
        query: Natural language search query
        n: Number of results to return

    Returns:
        List of matching games with similarity scores
    """
    collection = _get_collection()

    # Check if index exists, initialize if empty
    if collection.count() == 0:
        init_search_index()

    # Perform semantic search
    results = collection.query(
        query_texts=[query],
        n_results=min(n, collection.count()),
    )

    # Format results
    games = []
    for i, metadata in enumerate(results["metadatas"][0]):
        games.append({
            "name": metadata["name"],
            "category": metadata["category"],
            "price": metadata["price"],
            "in_stock": metadata["in_stock"],
            "relevance": round(1 - results["distances"][0][i], 3),  # Convert distance to similarity
        })

    return games


if __name__ == "__main__":
    # Test the search
    from database import init_db

    if not DB_PATH.exists():
        init_db()

    print("Initializing search index...")
    count = init_search_index()
    print(f"Indexed {count} games.\n")

    test_queries = [
        "cooperative games for families",
        "strategy and trading",
        "quick party games",
        "complex adventure games",
    ]

    for query in test_queries:
        print(f"Query: {query}")
        results = search_games(query, n=3)
        for game in results:
            print(f"  - {game['name']} ({game['category']}) - relevance: {game['relevance']}")
        print()
