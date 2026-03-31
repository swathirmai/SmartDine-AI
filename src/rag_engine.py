"""
src/rag_engine.py
RAG engine that indexes menu items in ChromaDB and supports semantic search.
"""

from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer


class RAGEngine:
    """Vector-search engine for menu items using ChromaDB + sentence-transformers."""

    COLLECTION_NAME = "menu_items"
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"

    def __init__(
        self,
        menu_items: list[dict[str, Any]],
        persist_dir: str = "./chroma_db",
    ) -> None:
        self.menu_items = menu_items
        self.persist_dir = persist_dir

        # Initialise the persistent ChromaDB client
        self._client = chromadb.PersistentClient(path=persist_dir)

        # Load the embedding model (downloaded automatically on first use)
        self._model = SentenceTransformer(self.EMBEDDING_MODEL)

        # Collection is created/retrieved in index_menu()
        self._collection: chromadb.Collection | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_document_text(self, item: dict[str, Any]) -> str:
        """Produce the text that will be embedded for a menu item."""
        return (
            f"{item.get('Name', '')}: {item.get('Description', '')}. "
            f"Category: {item.get('Category', '')}. "
            f"Dietary: {item.get('Dietary', '')}. "
            f"Price: ${item.get('Price', 0):.2f}"
        )

    def _item_to_metadata(self, item: dict[str, Any]) -> dict[str, Any]:
        """Convert an item dict to a ChromaDB-safe metadata dict.

        ChromaDB only accepts str / int / float / bool values.
        """
        meta: dict[str, Any] = {}
        for key, value in item.items():
            if isinstance(value, (str, int, float, bool)):
                meta[key] = value
            else:
                # Fallback: convert to string
                meta[key] = str(value)
        return meta

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index_menu(self) -> None:
        """Index all menu items into ChromaDB.

        If the collection already contains documents the method returns
        immediately to avoid duplicate entries.
        """
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        # Skip re-indexing if data is already present
        if self._collection.count() > 0:
            return

        if not self.menu_items:
            return

        ids: list[str] = []
        documents: list[str] = []
        embeddings: list[list[float]] = []
        metadatas: list[dict[str, Any]] = []

        for item in self.menu_items:
            doc_text = self._build_document_text(item)
            embedding = self._model.encode(doc_text).tolist()

            ids.append(str(item.get("ID", "")))
            documents.append(doc_text)
            embeddings.append(embedding)
            metadatas.append(self._item_to_metadata(item))

        self._collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search(
        self, query: str, n_results: int = 5
    ) -> list[dict[str, Any]]:
        """Semantic search: return the top-n most relevant menu items.

        Each result dict contains all item metadata fields plus a
        ``similarity_score`` (0–1, higher = more similar).
        """
        if self._collection is None:
            self.index_menu()

        query_embedding = self._model.encode(query).tolist()

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, self._collection.count()),
            include=["metadatas", "distances"],
        )

        items: list[dict[str, Any]] = []
        metadatas_list = results.get("metadatas", [[]])[0]
        distances_list = results.get("distances", [[]])[0]

        for meta, distance in zip(metadatas_list, distances_list):
            item = dict(meta)
            # Convert cosine distance (0–2) to similarity (0–1)
            item["similarity_score"] = round(1 - distance / 2, 4)
            items.append(item)

        return items

    def search_by_category(
        self, category: str, n_results: int = 10
    ) -> list[dict[str, Any]]:
        """Return up to n_results items from a specific category.

        Uses a ChromaDB metadata filter so no embedding is needed.
        """
        if self._collection is None:
            self.index_menu()

        results = self._collection.get(
            where={"Category": category},
            include=["metadatas"],
            limit=n_results,
        )

        items: list[dict[str, Any]] = []
        for meta in results.get("metadatas", []):
            item = dict(meta)
            item["similarity_score"] = 1.0  # not ranked by relevance
            items.append(item)

        return items
