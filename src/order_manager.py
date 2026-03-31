"""
src/order_manager.py
Manages the in-session shopping cart and generates receipts.
"""

from datetime import datetime
from typing import Any


class OrderManager:
    """Tracks items added to an order and produces summaries / receipts."""

    TAX_RATE = 0.10  # 10 %

    def __init__(self) -> None:
        # cart: {item_id: {name, price, quantity, special_request}}
        self.cart: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Cart mutation methods
    # ------------------------------------------------------------------

    def add_item(
        self,
        item_id: str,
        item_name: str,
        price: float,
        quantity: int = 1,
        special_request: str = "",
    ) -> None:
        """Add an item to the cart, or increment quantity if already present."""
        item_id = str(item_id).strip()
        if item_id in self.cart:
            self.cart[item_id]["quantity"] += quantity
            if special_request:
                self.cart[item_id]["special_request"] = special_request
        else:
            self.cart[item_id] = {
                "name": item_name,
                "price": float(price),
                "quantity": int(quantity),
                "special_request": special_request,
            }

    def remove_item(self, item_id: str) -> bool:
        """Remove an item from the cart.  Returns False if it was not found."""
        item_id = str(item_id).strip()
        if item_id not in self.cart:
            return False
        del self.cart[item_id]
        return True

    def update_quantity(self, item_id: str, quantity: int) -> bool:
        """Set the quantity for an existing cart item.

        If quantity <= 0 the item is removed.
        Returns False if the item was not found.
        """
        item_id = str(item_id).strip()
        if item_id not in self.cart:
            return False
        if quantity <= 0:
            del self.cart[item_id]
        else:
            self.cart[item_id]["quantity"] = int(quantity)
        return True

    def clear_order(self) -> None:
        """Empty the cart."""
        self.cart.clear()

    # ------------------------------------------------------------------
    # Read-only helpers
    # ------------------------------------------------------------------

    def is_empty(self) -> bool:
        """Return True when the cart contains no items."""
        return len(self.cart) == 0

    def get_order_summary(self) -> dict[str, Any]:
        """Return a structured summary of the current order."""
        items: list[dict[str, Any]] = []
        subtotal = 0.0

        for item_id, entry in self.cart.items():
            line_subtotal = entry["price"] * entry["quantity"]
            subtotal += line_subtotal
            items.append(
                {
                    "item_id": item_id,
                    "name": entry["name"],
                    "qty": entry["quantity"],
                    "price": entry["price"],
                    "subtotal": round(line_subtotal, 2),
                    "special_request": entry.get("special_request", ""),
                }
            )

        tax = round(subtotal * self.TAX_RATE, 2)
        total = round(subtotal + tax, 2)
        subtotal = round(subtotal, 2)

        return {
            "items": items,
            "subtotal": subtotal,
            "tax": tax,
            "total": total,
            "item_count": sum(e["quantity"] for e in self.cart.values()),
        }

    # ------------------------------------------------------------------
    # Receipt generation
    # ------------------------------------------------------------------

    def generate_receipt(self, payment_method: str, order_number: str) -> str:
        """Return a formatted plain-text receipt."""
        summary = self.get_order_summary()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines: list[str] = [
            "=" * 48,
            "           SMARTDINE AI RESTAURANT",
            "              ORDER RECEIPT",
            "=" * 48,
            f"  Order #: {order_number}",
            f"  Date   : {now}",
            "-" * 48,
            f"  {'ITEM':<24} {'QTY':>4} {'PRICE':>7} {'SUBTOTAL':>8}",
            "-" * 48,
        ]

        for item in summary["items"]:
            name = item["name"][:24]
            lines.append(
                f"  {name:<24} {item['qty']:>4}  ${item['price']:>6.2f}  ${item['subtotal']:>7.2f}"
            )
            if item.get("special_request"):
                lines.append(f"    * Note: {item['special_request']}")

        lines += [
            "-" * 48,
            f"  {'Subtotal':<30}  ${summary['subtotal']:>7.2f}",
            f"  {'Tax (10%)':<30}  ${summary['tax']:>7.2f}",
            "=" * 48,
            f"  {'TOTAL':<30}  ${summary['total']:>7.2f}",
            "=" * 48,
            f"  Payment Method: {payment_method}",
            "-" * 48,
            "  Thank you for dining with SmartDine AI!",
            "  We hope to see you again soon.",
            "=" * 48,
        ]

        return "\n".join(lines)
