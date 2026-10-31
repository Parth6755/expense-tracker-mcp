from fastmcp import FastMCP
import os
import sqlite3
import aiosqlite
from pathlib import Path

# Cloud-compatible writable database directory
DATA_DIR = Path(os.environ.get("DATA_DIR", "/tmp/expense-tracker"))

DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = str(DATA_DIR / "expenses.db")

CATEGORIES_PATH = Path(__file__).parent / "categories.json"

print(f"Database path: {DB_PATH}")

mcp = FastMCP("ExpenseTracker")


# --------------------------------
# 2. Initialize database
# --------------------------------

def init_db():
    try:
        with sqlite3.connect(DB_PATH) as conn:

            conn.execute("PRAGMA journal_mode=WAL")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
            """)

        print("Database initialized successfully.")

    except Exception as e:
        print(f"Database initialization error: {e}")
        raise


init_db()


# --------------------------------
# 3. Add expense
# --------------------------------

@mcp.tool()
async def add_expense(
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = ""
):
    """Add a new expense entry to the database."""

    try:
        if amount <= 0:
            return {"status": "error", "message": "Amount must be greater than zero."}

        async with aiosqlite.connect(DB_PATH) as conn:

            cursor = await conn.execute(
                """
                INSERT INTO expenses
                (date, amount, category, subcategory, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (date, amount, category, subcategory, note)
            )

            await conn.commit()

            return {
                "status": "success",
                "id": cursor.lastrowid,
                "message": "Expense added successfully."
            }

    except Exception as e:
        return {"status": "error", "message": str(e)}


# --------------------------------
# 4. List expenses
# --------------------------------

@mcp.tool()
async def list_expenses(start_date: str, end_date: str):
    """List expenses within an inclusive date range."""

    try:
        async with aiosqlite.connect(DB_PATH) as conn:

            cursor = await conn.execute(
                """
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
                """,
                (start_date, end_date)
            )

            rows = await cursor.fetchall()

            columns = [column[0] for column in cursor.description]

            return [
                dict(zip(columns, row))
                for row in rows
            ]

    except Exception as e:
        return {"status": "error", "message": str(e)}


# --------------------------------
# 5. Summarize expenses
# --------------------------------

@mcp.tool()
async def summarize(
    start_date: str,
    end_date: str,
    category: str = None
):
    """Summarize expenses by category."""

    try:
        async with aiosqlite.connect(DB_PATH) as conn:

            query = """
                SELECT
                    category,
                    SUM(amount) AS total_amount,
                    COUNT(*) AS count
                FROM expenses
                WHERE date BETWEEN ? AND ?
            """

            params = [start_date, end_date]

            if category:
                query += " AND category = ?"
                params.append(category)

            query += """
                GROUP BY category
                ORDER BY total_amount DESC
            """

            cursor = await conn.execute(query, params)

            rows = await cursor.fetchall()

            columns = [column[0] for column in cursor.description]

            return [
                dict(zip(columns, row))
                for row in rows
            ]

    except Exception as e:
        return {"status": "error", "message": str(e)}


# --------------------------------
# 6. Expense categories resource
# --------------------------------

@mcp.resource(
    "expense:///categories",
    mime_type="application/json"
)
def categories():
    """Return available expense categories."""

    default_categories = {
        "categories": [
            "Food & Dining",
            "Transportation",
            "Shopping",
            "Entertainment",
            "Bills & Utilities",
            "Healthcare",
            "Travel",
            "Education",
            "Business",
            "Other"
        ]
    }

    try:
        if os.path.exists(CATEGORIES_PATH):

            with open(CATEGORIES_PATH, "r", encoding="utf-8") as file:
                return file.read()

        return json.dumps(default_categories, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e)
        })


# --------------------------------
# 7. Start MCP server
# --------------------------------

if __name__ == "__main__":
    mcp.run()
