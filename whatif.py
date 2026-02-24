"""What-if scenario analysis tool."""

from database import query_db


def whatif_price_change(target: str, change_percent: float) -> dict:
    """
    Calculate impact of changing prices.

    Args:
        target: "games", "food", or a specific item name
        change_percent: Percentage change (e.g., 10 for +10%, -15 for -15%)

    Returns:
        Dict with current vs projected revenue and profit
    """
    multiplier = 1 + (change_percent / 100)

    if target.lower() == "games":
        # Get current game sales revenue and profit
        current = query_db("""
            SELECT
                SUM(gs.quantity * gs.unit_price) as revenue,
                SUM(gs.quantity * (gs.unit_price - bg.cost)) as profit
            FROM game_sales gs
            JOIN board_games bg ON gs.game_id = bg.id
        """)[0]

        new_revenue = current["revenue"] * multiplier
        # Profit changes more than revenue because costs stay fixed
        new_profit = current["profit"] + (current["revenue"] * (multiplier - 1))

        return {
            "scenario": f"Game prices {'increased' if change_percent > 0 else 'decreased'} by {abs(change_percent)}%",
            "current_revenue": round(current["revenue"], 2),
            "projected_revenue": round(new_revenue, 2),
            "revenue_change": round(new_revenue - current["revenue"], 2),
            "current_profit": round(current["profit"], 2),
            "projected_profit": round(new_profit, 2),
            "profit_change": round(new_profit - current["profit"], 2),
            "assumption": "Assumes same volume sold at new prices"
        }

    elif target.lower() == "food":
        # Get current food/bev revenue and profit
        current = query_db("""
            SELECT
                SUM(fbo.quantity * fbo.unit_price) as revenue,
                SUM(fbo.quantity * (fbo.unit_price - fbi.cost)) as profit
            FROM food_bev_orders fbo
            JOIN food_bev_items fbi ON fbo.item_name = fbi.item_name
        """)[0]

        new_revenue = current["revenue"] * multiplier
        new_profit = current["profit"] + (current["revenue"] * (multiplier - 1))

        return {
            "scenario": f"Food & beverage prices {'increased' if change_percent > 0 else 'decreased'} by {abs(change_percent)}%",
            "current_revenue": round(current["revenue"], 2),
            "projected_revenue": round(new_revenue, 2),
            "revenue_change": round(new_revenue - current["revenue"], 2),
            "current_profit": round(current["profit"], 2),
            "projected_profit": round(new_profit, 2),
            "profit_change": round(new_profit - current["profit"], 2),
            "assumption": "Assumes same volume sold at new prices"
        }

    elif target.lower() in ("tables", "rentals", "table_rentals"):
        # Get current rental revenue
        current = query_db("""
            SELECT SUM(duration_hours * hourly_rate) as revenue
            FROM table_rentals
        """)[0]

        new_revenue = current["revenue"] * multiplier

        return {
            "scenario": f"Table rental rates {'increased' if change_percent > 0 else 'decreased'} by {abs(change_percent)}%",
            "current_revenue": round(current["revenue"], 2),
            "projected_revenue": round(new_revenue, 2),
            "revenue_change": round(new_revenue - current["revenue"], 2),
            "note": "Table rentals are pure profit (no direct costs)",
            "assumption": "Assumes same booking volume at new rates"
        }

    else:
        # Specific item - try games first, then food
        game = query_db(f"SELECT id, name, price, cost FROM board_games WHERE LOWER(name) LIKE '%{target.lower()}%'")
        if game:
            game = game[0]
            sales = query_db(f"""
                SELECT SUM(quantity) as units, SUM(quantity * unit_price) as revenue
                FROM game_sales WHERE game_id = {game['id']}
            """)[0]

            if not sales["units"]:
                return {"error": f"No sales found for {game['name']}"}

            current_revenue = sales["revenue"]
            current_profit = sales["units"] * (game["price"] - game["cost"])
            new_price = game["price"] * multiplier
            new_revenue = sales["units"] * new_price
            new_profit = sales["units"] * (new_price - game["cost"])

            return {
                "scenario": f"{game['name']} price changed from ${game['price']:.2f} to ${new_price:.2f} ({change_percent:+.0f}%)",
                "units_sold": sales["units"],
                "current_revenue": round(current_revenue, 2),
                "projected_revenue": round(new_revenue, 2),
                "revenue_change": round(new_revenue - current_revenue, 2),
                "current_profit": round(current_profit, 2),
                "projected_profit": round(new_profit, 2),
                "profit_change": round(new_profit - current_profit, 2),
                "assumption": "Assumes same units sold at new price"
            }

        # Try food items
        food = query_db(f"SELECT item_name, sell_price, cost FROM food_bev_items WHERE LOWER(item_name) LIKE '%{target.lower()}%'")
        if food:
            food = food[0]
            sales = query_db(f"""
                SELECT SUM(quantity) as units, SUM(quantity * unit_price) as revenue
                FROM food_bev_orders WHERE LOWER(item_name) = '{food['item_name'].lower()}'
            """)[0]

            if not sales["units"]:
                return {"error": f"No sales found for {food['item_name']}"}

            current_revenue = sales["revenue"]
            current_profit = sales["units"] * (food["sell_price"] - food["cost"])
            new_price = food["sell_price"] * multiplier
            new_revenue = sales["units"] * new_price
            new_profit = sales["units"] * (new_price - food["cost"])

            return {
                "scenario": f"{food['item_name']} price changed from ${food['sell_price']:.2f} to ${new_price:.2f} ({change_percent:+.0f}%)",
                "units_sold": sales["units"],
                "current_revenue": round(current_revenue, 2),
                "projected_revenue": round(new_revenue, 2),
                "revenue_change": round(new_revenue - current_revenue, 2),
                "current_profit": round(current_profit, 2),
                "projected_profit": round(new_profit, 2),
                "profit_change": round(new_profit - current_profit, 2),
                "assumption": "Assumes same units sold at new price"
            }

        return {"error": f"Could not find item matching '{target}'"}


def whatif_volume_change(target: str, quantity_change: int) -> dict:
    """
    Calculate impact of selling more or fewer units.

    Args:
        target: Item name or category
        quantity_change: Additional units (positive) or fewer units (negative)

    Returns:
        Dict with revenue and profit impact
    """
    # Try to find the item
    game = query_db(f"SELECT id, name, price, cost FROM board_games WHERE LOWER(name) LIKE '%{target.lower()}%'")
    if game:
        game = game[0]
        revenue_per_unit = game["price"]
        profit_per_unit = game["price"] - game["cost"]

        return {
            "scenario": f"{'Sell' if quantity_change > 0 else 'Sold'} {abs(quantity_change)} {'more' if quantity_change > 0 else 'fewer'} units of {game['name']}",
            "price_per_unit": game["price"],
            "cost_per_unit": game["cost"],
            "profit_per_unit": round(profit_per_unit, 2),
            "revenue_impact": round(quantity_change * revenue_per_unit, 2),
            "profit_impact": round(quantity_change * profit_per_unit, 2),
        }

    food = query_db(f"SELECT item_name, sell_price, cost FROM food_bev_items WHERE LOWER(item_name) LIKE '%{target.lower()}%'")
    if food:
        food = food[0]
        revenue_per_unit = food["sell_price"]
        profit_per_unit = food["sell_price"] - food["cost"]

        return {
            "scenario": f"{'Sell' if quantity_change > 0 else 'Sold'} {abs(quantity_change)} {'more' if quantity_change > 0 else 'fewer'} units of {food['item_name']}",
            "price_per_unit": food["sell_price"],
            "cost_per_unit": food["cost"],
            "profit_per_unit": round(profit_per_unit, 2),
            "revenue_impact": round(quantity_change * revenue_per_unit, 2),
            "profit_impact": round(quantity_change * profit_per_unit, 2),
        }

    return {"error": f"Could not find item matching '{target}'"}


def whatif_expense_change(category: str, change_percent: float, month: str = None) -> dict:
    """
    Calculate impact of operating expense changes.

    Args:
        category: "all", "rent", "labor", "utilities", etc.
        change_percent: Percentage change
        month: Optional month filter (e.g., "2026-01" or "january")

    Returns:
        Dict with expense impact on net profit
    """
    multiplier = 1 + (change_percent / 100)

    # Build month filter clause
    month_clause = ""
    month_label = "all time"
    if month:
        # Handle month names like "january" or formats like "2026-01"
        month_lower = month.lower()
        month_map = {
            "january": "2026-01", "jan": "2026-01",
            "february": "2026-02", "feb": "2026-02",
        }
        month_value = month_map.get(month_lower, month)
        month_clause = f"AND month = '{month_value}'"
        month_label = month_value

    if category.lower() == "all":
        current = query_db(f"SELECT SUM(amount) as total FROM operating_expenses WHERE 1=1 {month_clause}")[0]

        if not current["total"]:
            return {"error": f"No expenses found for {month_label}"}

        new_total = current["total"] * multiplier

        return {
            "scenario": f"All operating expenses {'increased' if change_percent > 0 else 'decreased'} by {abs(change_percent)}%",
            "period": month_label,
            "current_expenses": round(current["total"], 2),
            "projected_expenses": round(new_total, 2),
            "expense_change": round(new_total - current["total"], 2),
            "net_profit_impact": round(-(new_total - current["total"]), 2),
            "note": "Negative impact means reduced profit"
        }
    else:
        current = query_db(f"""
            SELECT SUM(amount) as total
            FROM operating_expenses
            WHERE LOWER(category) LIKE '%{category.lower()}%'
            {month_clause}
        """)[0]

        if not current["total"]:
            return {"error": f"No expenses found matching category '{category}' for {month_label}"}

        new_total = current["total"] * multiplier

        return {
            "scenario": f"{category.title()} expenses {'increased' if change_percent > 0 else 'decreased'} by {abs(change_percent)}%",
            "period": month_label,
            "current_expenses": round(current["total"], 2),
            "projected_expenses": round(new_total, 2),
            "expense_change": round(new_total - current["total"], 2),
            "net_profit_impact": round(-(new_total - current["total"]), 2),
            "note": "Negative impact means reduced profit"
        }


def whatif_hours_change(hours_change: float, hourly_rate: float = None) -> dict:
    """
    Calculate impact of more/fewer table rental hours.

    Args:
        hours_change: Additional hours (positive) or fewer hours (negative)
        hourly_rate: Optional specific rate (uses average if not provided)

    Returns:
        Dict with revenue impact
    """
    if hourly_rate is None:
        avg = query_db("SELECT AVG(hourly_rate) as rate FROM table_rentals")[0]
        hourly_rate = avg["rate"]

    revenue_impact = hours_change * hourly_rate

    return {
        "scenario": f"{'Add' if hours_change > 0 else 'Reduce'} {abs(hours_change)} rental hours at ${hourly_rate:.2f}/hour",
        "hourly_rate": hourly_rate,
        "hours_change": hours_change,
        "revenue_impact": round(revenue_impact, 2),
        "profit_impact": round(revenue_impact, 2),
        "note": "Table rentals are 100% margin (no direct costs)"
    }


def run_scenario(scenario_type: str, **params) -> dict:
    """
    Run a what-if scenario.

    Args:
        scenario_type: One of "price_change", "volume_change", "expense_change", "hours_change"
        **params: Parameters specific to the scenario type

    Returns:
        Dict with scenario results
    """
    scenarios = {
        "price_change": whatif_price_change,
        "volume_change": whatif_volume_change,
        "expense_change": whatif_expense_change,
        "hours_change": whatif_hours_change,
    }

    if scenario_type not in scenarios:
        return {
            "error": f"Unknown scenario type: {scenario_type}",
            "valid_types": list(scenarios.keys())
        }

    try:
        return scenarios[scenario_type](**params)
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    from database import init_db, DB_PATH

    if not DB_PATH.exists():
        init_db()

    import json

    print("=== What-If Scenario Examples ===\n")

    scenarios = [
        ("price_change", {"target": "games", "change_percent": 10}),
        ("price_change", {"target": "food", "change_percent": -5}),
        ("price_change", {"target": "Catan", "change_percent": 15}),
        ("volume_change", {"target": "Catan", "quantity_change": 10}),
        ("volume_change", {"target": "Coffee", "quantity_change": 50}),
        ("expense_change", {"category": "all", "change_percent": 10}),
        ("expense_change", {"category": "labor", "change_percent": -5}),
        ("hours_change", {"hours_change": 20}),
    ]

    for scenario_type, params in scenarios:
        print(f"{scenario_type}: {params}")
        result = run_scenario(scenario_type, **params)
        print(json.dumps(result, indent=2))
        print()
