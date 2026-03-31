# SmartDine AI

AI-powered restaurant ordering system using Python, Claude LLM, and RAG (Retrieval-Augmented Generation).

## How It Works

```
User (natural language)
        |
        v
  SmartDine Agent  (Claude claude-sonnet-4-6 + Tool Use)
        |
        +---> search_menu()  ---> RAGEngine (ChromaDB + sentence-transformers)
        |                              |
        |                         menu.xlsx  (source of truth)
        |
        +---> add_to_order()  ---> OrderManager (in-memory cart)
        +---> view_order()    ---/
        +---> checkout()      ---> Receipt generation
```

- **LLM**: Claude (`claude-sonnet-4-6`) via the Anthropic API  
- **RAG**: `sentence-transformers` (`all-MiniLM-L6-v2`) for embeddings + `ChromaDB` as the vector store  
- **Menu data**: `data/menu.xlsx` spreadsheet (34 items across 6 categories)  
- **CLI**: `rich`-powered terminal UI with spinner, tables, and receipt panel

## Project Structure

```
SmartDine AI/
├── data/
│   └── menu.xlsx          # Menu spreadsheet (auto-created on first run)
├── src/
│   ├── menu_loader.py     # Reads & validates the Excel file
│   ├── rag_engine.py      # ChromaDB indexing + semantic search
│   ├── order_manager.py   # Cart CRUD + receipt generation
│   └── ai_agent.py        # Claude agent with 6 tools
├── main.py                # CLI entry point
├── setup_menu.py          # Creates the sample menu.xlsx
└── requirements.txt
```

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your Anthropic API key
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...

# 3. (Optional) Generate menu spreadsheet manually
python setup_menu.py

# 4. Start the app
python main.py
```

`data/menu.xlsx` is created automatically on first launch if it doesn't exist.

## Usage

Type your order in plain English:

```
[You]: I'd like a burger
[You]: Can I get some fries and a lemonade too?
[You]: What desserts do you have?
[You]: order            # show current cart
[You]: checkout         # pay and get receipt
```

### Special Commands

| Command | Action |
|---------|--------|
| `menu`  | Show all menu categories |
| `order` | Display current cart |
| `clear` | Reset order and conversation |
| `quit`  | Exit the app |

## Menu Categories

| Category    | Items |
|-------------|-------|
| Appetizers  | 6     |
| Salads      | 5     |
| Main Course | 8     |
| Sides       | 5     |
| Desserts    | 5     |
| Beverages   | 5     |

## Agent Tools

The Claude agent uses tool-use to interact with the system:

| Tool | Description |
|------|-------------|
| `search_menu` | Semantic search via RAG |
| `get_menu_by_category` | List all items in a category |
| `add_to_order` | Add item to cart |
| `remove_from_order` | Remove item from cart |
| `view_order` | Get current order summary |
| `checkout` | Finalise order & generate receipt |
