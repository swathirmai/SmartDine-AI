"""
src/menu_loader.py
Loads and provides access to menu data stored in an Excel spreadsheet.
"""

from pathlib import Path
from typing import Any

import pandas as pd


class MenuLoader:
    """Reads menu data from an Excel file and exposes helper methods."""

    def __init__(self, excel_path: str) -> None:
        self.excel_path = Path(excel_path)
        self._items: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> list[dict[str, Any]]:
        """Read the Excel file and return a list of item dicts.

        Each dict contains all columns from the spreadsheet with the
        column name as the key.  Boolean/numeric types are preserved as
        returned by pandas.
        """
        if not self.excel_path.exists():
            raise FileNotFoundError(
                f"Menu file not found: '{self.excel_path}'\n"
                "Please run 'python setup_menu.py' to create the menu spreadsheet."
            )

        try:
            df = pd.read_excel(self.excel_path, engine="openpyxl")
        except Exception as exc:
            raise RuntimeError(
                f"Failed to read menu file '{self.excel_path}': {exc}"
            ) from exc

        # Normalise column names: strip whitespace
        df.columns = [str(c).strip() for c in df.columns]

        # Convert each row to a plain dict; stringify the ID so it is
        # always a consistent type regardless of Excel cell format.
        items: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            item = row.to_dict()
            item["ID"] = str(item.get("ID", "")).strip()
            # Ensure Price is a float
            try:
                item["Price"] = float(item["Price"])
            except (TypeError, ValueError):
                item["Price"] = 0.0
            # Ensure Available is a plain bool
            item["Available"] = bool(item.get("Available", True))
            items.append(item)

        self._items = items
        return items

    def get_categories(self) -> list[str]:
        """Return a sorted list of unique category names."""
        if not self._items:
            self.load()
        seen: list[str] = []
        for item in self._items:
            cat = str(item.get("Category", "")).strip()
            if cat and cat not in seen:
                seen.append(cat)
        return sorted(seen)

    def get_item_by_id(self, item_id: str) -> dict[str, Any] | None:
        """Return a single item dict for the given ID, or None if not found."""
        if not self._items:
            self.load()
        item_id = str(item_id).strip()
        for item in self._items:
            if item.get("ID") == item_id:
                return item
        return None
