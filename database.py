"""SQLite database for board game cafe data."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "cafe.db"


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables and seed with sample data."""
    conn = get_connection()
    cur = conn.cursor()

    # Create tables
    cur.executescript("""
        DROP TABLE IF EXISTS food_bev_orders;
        DROP TABLE IF EXISTS table_rentals;
        DROP TABLE IF EXISTS game_sales;
        DROP TABLE IF EXISTS board_games;

        CREATE TABLE board_games (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            cost REAL NOT NULL,
            category TEXT NOT NULL,
            in_stock INTEGER NOT NULL
        );

        CREATE TABLE game_sales (
            id INTEGER PRIMARY KEY,
            game_id INTEGER NOT NULL,
            sale_date TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            channel TEXT NOT NULL,
            FOREIGN KEY (game_id) REFERENCES board_games(id)
        );

        CREATE TABLE table_rentals (
            id INTEGER PRIMARY KEY,
            table_number INTEGER NOT NULL,
            rental_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            duration_hours REAL NOT NULL,
            hourly_rate REAL NOT NULL
        );

        CREATE TABLE food_bev_orders (
            id INTEGER PRIMARY KEY,
            rental_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            FOREIGN KEY (rental_id) REFERENCES table_rentals(id)
        );
    """)

    # Seed board_games (cost is wholesale price, ~55% of retail)
    games = [
        ("Catan", 49.99, 27.50, "Strategy", 8),
        ("Ticket to Ride", 44.99, 24.75, "Family", 12),
        ("Pandemic", 39.99, 22.00, "Cooperative", 5),
        ("Wingspan", 59.99, 33.00, "Strategy", 6),
        ("Azul", 34.99, 19.25, "Abstract", 10),
        ("Codenames", 19.99, 11.00, "Party", 15),
        ("Splendor", 29.99, 16.50, "Strategy", 7),
        ("7 Wonders", 49.99, 27.50, "Strategy", 4),
        ("Carcassonne", 34.99, 19.25, "Family", 9),
        ("Dominion", 44.99, 24.75, "Deck Building", 6),
        ("Scythe", 79.99, 44.00, "Strategy", 3),
        ("Root", 69.99, 38.50, "Strategy", 4),
        ("Gloomhaven", 139.99, 77.00, "RPG", 2),
        ("Exploding Kittens", 19.99, 11.00, "Party", 20),
        ("Mysterium", 44.99, 24.75, "Cooperative", 5),
    ]
    cur.executemany(
        "INSERT INTO board_games (name, price, cost, category, in_stock) VALUES (?, ?, ?, ?, ?)",
        games
    )

    # Seed game_sales
    sales = [
        (1, "2026-01-15", 2, 49.99, "in_store"),
        (2, "2026-01-18", 1, 44.99, "online"),
        (3, "2026-01-20", 3, 39.99, "in_store"),
        (6, "2026-01-22", 4, 19.99, "online"),
        (5, "2026-01-25", 2, 34.99, "in_store"),
        (14, "2026-01-28", 5, 19.99, "online"),
        (1, "2026-02-01", 1, 49.99, "in_store"),
        (4, "2026-02-03", 2, 59.99, "online"),
        (7, "2026-02-05", 1, 29.99, "in_store"),
        (11, "2026-02-08", 1, 79.99, "online"),
        (12, "2026-02-10", 2, 69.99, "in_store"),
        (9, "2026-02-12", 3, 34.99, "online"),
        (10, "2026-02-14", 1, 44.99, "in_store"),
        (8, "2026-02-16", 2, 49.99, "online"),
        (15, "2026-02-18", 1, 44.99, "in_store"),
    ]
    cur.executemany(
        "INSERT INTO game_sales (game_id, sale_date, quantity, unit_price, channel) VALUES (?, ?, ?, ?, ?)",
        sales
    )

    # Seed table_rentals
    rentals = [
        (1, "2026-01-15", "14:00", 2.0, 8.00),
        (2, "2026-01-15", "16:00", 3.0, 8.00),
        (3, "2026-01-16", "18:00", 2.5, 8.00),
        (1, "2026-01-18", "12:00", 4.0, 8.00),
        (4, "2026-01-20", "15:00", 2.0, 10.00),
        (2, "2026-01-22", "17:00", 3.0, 8.00),
        (5, "2026-01-25", "14:00", 2.0, 10.00),
        (3, "2026-01-28", "19:00", 3.5, 8.00),
        (1, "2026-02-01", "13:00", 2.0, 8.00),
        (4, "2026-02-03", "16:00", 4.0, 10.00),
        (2, "2026-02-05", "18:00", 2.5, 8.00),
        (5, "2026-02-08", "15:00", 3.0, 10.00),
        (3, "2026-02-10", "14:00", 2.0, 8.00),
        (1, "2026-02-12", "17:00", 3.0, 8.00),
        (4, "2026-02-15", "12:00", 5.0, 10.00),
        (2, "2026-02-18", "16:00", 2.0, 8.00),
    ]
    cur.executemany(
        "INSERT INTO table_rentals (table_number, rental_date, start_time, duration_hours, hourly_rate) VALUES (?, ?, ?, ?, ?)",
        rentals
    )

    # Seed food_bev_orders
    orders = [
        (1, "Coffee", 2, 4.50),
        (1, "Brownie", 1, 3.50),
        (2, "Craft Beer", 3, 7.00),
        (2, "Nachos", 1, 9.00),
        (3, "Tea", 2, 3.50),
        (4, "Pizza Slice", 4, 5.00),
        (4, "Soda", 4, 2.50),
        (5, "Coffee", 2, 4.50),
        (6, "Craft Beer", 4, 7.00),
        (7, "Hot Chocolate", 2, 4.00),
        (7, "Cookie", 3, 2.50),
        (8, "Wine", 2, 8.00),
        (9, "Latte", 2, 5.50),
        (10, "Nachos", 2, 9.00),
        (10, "Soda", 3, 2.50),
        (11, "Tea", 1, 3.50),
        (12, "Pizza Slice", 3, 5.00),
        (13, "Coffee", 3, 4.50),
        (14, "Craft Beer", 2, 7.00),
        (15, "Brownie", 2, 3.50),
    ]
    cur.executemany(
        "INSERT INTO food_bev_orders (rental_id, item_name, quantity, unit_price) VALUES (?, ?, ?, ?)",
        orders
    )

    conn.commit()
    conn.close()


def query_db(sql: str) -> list[dict]:
    """Execute a SELECT query and return results as list of dicts."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_schema() -> str:
    """Return database schema description for the agent."""
    return """
Database Tables:

1. board_games
   - id: INTEGER PRIMARY KEY
   - name: TEXT (game name)
   - price: REAL (retail/selling price)
   - cost: REAL (wholesale cost we paid)
   - category: TEXT (Strategy, Family, Cooperative, Abstract, Party, Deck Building, RPG)
   - in_stock: INTEGER (quantity in stock)

2. game_sales
   - id: INTEGER PRIMARY KEY
   - game_id: INTEGER (FK to board_games.id)
   - sale_date: TEXT (YYYY-MM-DD)
   - quantity: INTEGER
   - unit_price: REAL
   - channel: TEXT (online or in_store)

3. table_rentals
   - id: INTEGER PRIMARY KEY
   - table_number: INTEGER (1-5)
   - rental_date: TEXT (YYYY-MM-DD)
   - start_time: TEXT (HH:MM)
   - duration_hours: REAL
   - hourly_rate: REAL

4. food_bev_orders
   - id: INTEGER PRIMARY KEY
   - rental_id: INTEGER (FK to table_rentals.id)
   - item_name: TEXT
   - quantity: INTEGER
   - unit_price: REAL
""".strip()


if __name__ == "__main__":
    init_db()
    print("Database initialized with sample data.")
