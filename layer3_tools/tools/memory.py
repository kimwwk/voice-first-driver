"""Memory tool — capture and organize knowledge."""
import os
from datetime import datetime


def register(mcp):
    data_dir = os.environ.get("CHILL_DATA_DIR", "data")
    memory_dir = os.path.join(data_dir, "memory")

    @mcp.tool()
    def remember(content: str, category: str = "general") -> str:
        """Store information in memory, organized by category.

        Args:
            content: The information to remember.
            category: Category for organization (e.g. "general", "personal", "work", "shopping", "ideas").
        """
        cat_dir = os.path.join(memory_dir, category)
        os.makedirs(cat_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(cat_dir, f"{timestamp}.md")
        header = f"# {category.title()} — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        with open(filepath, "w") as f:
            f.write(header + content + "\n")
        return f"Stored in '{category}' memory."

    @mcp.tool()
    def recall(query: str, category: str = "") -> str:
        """Search stored memories by keyword, optionally filtered by category.

        Args:
            query: Search keyword or phrase.
            category: Optional category filter (leave empty to search all).
        """
        search_dir = os.path.join(memory_dir, category) if category else memory_dir
        if not os.path.exists(search_dir):
            return "No memories found."
        results = []
        query_lower = query.lower()
        for root, _dirs, files in os.walk(search_dir):
            for fname in sorted(files, reverse=True):
                if not fname.endswith(".md"):
                    continue
                filepath = os.path.join(root, fname)
                with open(filepath) as f:
                    text = f.read()
                if query_lower in text.lower():
                    cat = os.path.relpath(root, memory_dir)
                    results.append(f"[{cat}] {text.strip()}")
                if len(results) >= 10:
                    break
            if len(results) >= 10:
                break
        if not results:
            return f"No memories matching '{query}'."
        return "\n---\n".join(results)
