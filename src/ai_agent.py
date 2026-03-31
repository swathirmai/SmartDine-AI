"""
src/ai_agent.py
SmartDine AI agent powered by Claude with tool-use for RAG-based ordering.
"""

import json
import os
import random
from typing import Any

import anthropic
from dotenv import load_dotenv

from src.rag_engine import RAGEngine
from src.order_manager import OrderManager


# Tool schema definitions -------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_menu",
        "description": (
            "Search the restaurant menu using natural language. "
            "Use this to find dishes by description, ingredient, cuisine type, "
            "or any other free-text query. Returns the most relevant items."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query, e.g. 'spicy vegetarian pasta'",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_menu_by_category",
        "description": (
            "List all available items in a specific menu category such as "
            "'Appetizers', 'Salads', 'Main Course', 'Sides', 'Desserts', or 'Beverages'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Category name, e.g. 'Desserts'",
                }
            },
            "required": ["category"],
        },
    },
    {
        "name": "add_to_order",
        "description": (
            "Add a menu item to the customer's current order (cart). "
            "Always confirm the item ID and price from a prior menu search before calling this."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "string",
                    "description": "Unique item ID from the menu (e.g. 'M001')",
                },
                "item_name": {
                    "type": "string",
                    "description": "Display name of the item",
                },
                "price": {
                    "type": "number",
                    "description": "Price per unit in USD",
                },
                "quantity": {
                    "type": "integer",
                    "description": "Number of units to add (default 1)",
                    "default": 1,
                },
                "special_request": {
                    "type": "string",
                    "description": "Optional special instructions, e.g. 'no onions'",
                    "default": "",
                },
            },
            "required": ["item_id", "item_name", "price"],
        },
    },
    {
        "name": "remove_from_order",
        "description": "Remove a specific item from the customer's current order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "string",
                    "description": "Unique item ID to remove (e.g. 'M001')",
                }
            },
            "required": ["item_id"],
        },
    },
    {
        "name": "view_order",
        "description": (
            "Retrieve the current order summary including all items, quantities, "
            "prices, subtotal, tax, and total."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "checkout",
        "description": (
            "Finalise the order, generate a receipt, and complete the transaction. "
            "Ask the customer for their preferred payment method before calling this."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "payment_method": {
                    "type": "string",
                    "description": "Payment method, e.g. 'Credit Card', 'Cash', 'Mobile Pay'",
                },
                "special_instructions": {
                    "type": "string",
                    "description": "Any final special instructions for the kitchen",
                    "default": "",
                },
            },
            "required": ["payment_method"],
        },
    },
]


# Agent class -------------------------------------------------------------

class SmartDineAgent:
    """Conversational ordering agent backed by Claude and RAG menu search."""

    def __init__(
        self,
        rag_engine: RAGEngine,
        order_manager: OrderManager,
        model: str = "claude-sonnet-4-6",
    ) -> None:
        load_dotenv()

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY not found.  "
                "Please copy .env.example to .env and add your key."
            )

        self.rag_engine = rag_engine
        self.order_manager = order_manager
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key)
        self.conversation_history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    @property
    def system_prompt(self) -> str:
        return (
            "You are SmartDine AI, a friendly and knowledgeable restaurant ordering assistant. "
            "Your job is to help customers explore the menu, answer questions about dishes, "
            "take their order, and process payment.\n\n"
            "Guidelines:\n"
            "- Always search the menu before recommending or adding items to confirm availability and price.\n"
            "- Be warm, enthusiastic, and concise — like a great waiter.\n"
            "- When a customer asks for something, use 'search_menu' to find the best matches.\n"
            "- To list items in a category, use 'get_menu_by_category'.\n"
            "- Before adding an item, confirm the name, price, and any special requests with the customer.\n"
            "- Use 'view_order' to show the current cart when the customer asks.\n"
            "- When the customer is ready to pay, ask for their payment method, then call 'checkout'.\n"
            "- After checkout, include the word RECEIPT in your response so the UI can display it nicely.\n"
            "- If an item is unavailable, apologise and suggest alternatives.\n"
            "- Keep dietary restrictions and preferences in mind when making recommendations.\n"
            "- Format prices as $X.XX.\n"
        )

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Dispatch a tool call and return a JSON-serialisable result string."""
        try:
            if tool_name == "search_menu":
                return self._tool_search_menu(**tool_input)
            elif tool_name == "get_menu_by_category":
                return self._tool_get_menu_by_category(**tool_input)
            elif tool_name == "add_to_order":
                return self._tool_add_to_order(**tool_input)
            elif tool_name == "remove_from_order":
                return self._tool_remove_from_order(**tool_input)
            elif tool_name == "view_order":
                return self._tool_view_order()
            elif tool_name == "checkout":
                return self._tool_checkout(**tool_input)
            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    def _tool_search_menu(self, query: str, n_results: int = 5) -> str:
        results = self.rag_engine.search(query, n_results=n_results)
        if not results:
            return json.dumps({"message": "No matching items found.", "items": []})
        simplified = []
        for item in results:
            simplified.append(
                {
                    "id": item.get("ID"),
                    "name": item.get("Name"),
                    "category": item.get("Category"),
                    "description": item.get("Description"),
                    "price": item.get("Price"),
                    "dietary": item.get("Dietary"),
                    "calories": item.get("Calories"),
                    "available": item.get("Available"),
                    "similarity_score": item.get("similarity_score"),
                }
            )
        return json.dumps({"items": simplified})

    def _tool_get_menu_by_category(self, category: str) -> str:
        results = self.rag_engine.search_by_category(category)
        if not results:
            return json.dumps(
                {"message": f"No items found in category '{category}'.", "items": []}
            )
        simplified = []
        for item in results:
            simplified.append(
                {
                    "id": item.get("ID"),
                    "name": item.get("Name"),
                    "description": item.get("Description"),
                    "price": item.get("Price"),
                    "dietary": item.get("Dietary"),
                    "calories": item.get("Calories"),
                    "available": item.get("Available"),
                }
            )
        return json.dumps({"category": category, "items": simplified})

    def _tool_add_to_order(
        self,
        item_id: str,
        item_name: str,
        price: float,
        quantity: int = 1,
        special_request: str = "",
    ) -> str:
        self.order_manager.add_item(item_id, item_name, price, quantity, special_request)
        summary = self.order_manager.get_order_summary()
        return json.dumps(
            {
                "success": True,
                "message": f"Added {quantity}x {item_name} to your order.",
                "cart_total": summary["total"],
                "item_count": summary["item_count"],
            }
        )

    def _tool_remove_from_order(self, item_id: str) -> str:
        removed = self.order_manager.remove_item(item_id)
        if removed:
            summary = self.order_manager.get_order_summary()
            return json.dumps(
                {
                    "success": True,
                    "message": f"Item {item_id} removed from your order.",
                    "cart_total": summary["total"],
                }
            )
        return json.dumps(
            {"success": False, "message": f"Item {item_id} was not found in your order."}
        )

    def _tool_view_order(self) -> str:
        if self.order_manager.is_empty():
            return json.dumps({"message": "Your order is currently empty.", "order": None})
        return json.dumps(self.order_manager.get_order_summary())

    def _tool_checkout(
        self, payment_method: str, special_instructions: str = ""
    ) -> str:
        if self.order_manager.is_empty():
            return json.dumps(
                {"success": False, "message": "Cannot checkout — order is empty."}
            )
        order_number = str(random.randint(100000, 999999))
        receipt = self.order_manager.generate_receipt(payment_method, order_number)
        self.order_manager.clear_order()
        return json.dumps(
            {
                "success": True,
                "order_number": order_number,
                "receipt": receipt,
                "special_instructions": special_instructions,
            }
        )

    # ------------------------------------------------------------------
    # Agentic chat loop
    # ------------------------------------------------------------------

    def chat(self, user_message: str) -> str:
        """Send a user message and run the agentic tool-use loop until done."""
        self.conversation_history.append(
            {"role": "user", "content": user_message}
        )

        while True:
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=self.system_prompt,
                    tools=TOOLS,
                    messages=self.conversation_history,
                )
            except anthropic.APIError as exc:
                error_msg = f"I'm having trouble connecting right now. Please try again. ({exc})"
                return error_msg

            # Append assistant turn (full content block list)
            self.conversation_history.append(
                {"role": "assistant", "content": response.content}
            )

            if response.stop_reason == "end_turn":
                # Extract and return the text response
                text_parts = [
                    block.text
                    for block in response.content
                    if hasattr(block, "text")
                ]
                return "\n".join(text_parts).strip()

            if response.stop_reason == "tool_use":
                # Execute every tool the model requested
                tool_results: list[dict[str, Any]] = []
                for block in response.content:
                    if block.type == "tool_use":
                        result_str = self._execute_tool(block.name, block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result_str,
                            }
                        )

                # Feed results back as a user turn and loop
                if tool_results:
                    self.conversation_history.append(
                        {"role": "user", "content": tool_results}
                    )
                continue  # next iteration calls the model again

            # Unexpected stop reason — return whatever text we have
            text_parts = [
                block.text
                for block in response.content
                if hasattr(block, "text")
            ]
            return "\n".join(text_parts).strip() or "Something unexpected happened. Please try again."

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear conversation history and the current order."""
        self.conversation_history.clear()
        self.order_manager.clear_order()
