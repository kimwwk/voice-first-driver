"""Single MCP entrypoint — auto-discovers tool modules from tools/ package."""
import importlib
import os
import pkgutil

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("chill-tools")

# Resolve DATA_DIR: repo-root/data by default
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("CHILL_DATA_DIR", os.path.join(REPO_ROOT, "data"))
os.makedirs(DATA_DIR, exist_ok=True)

# Export so tool modules can import it
os.environ["CHILL_DATA_DIR"] = DATA_DIR

# Auto-discover and register tools from the tools/ package
import tools as _tools_pkg

for _importer, modname, _ispkg in pkgutil.iter_modules(_tools_pkg.__path__):
    module = importlib.import_module(f"tools.{modname}")
    if hasattr(module, "register"):
        module.register(mcp)

if __name__ == "__main__":
    mcp.run()
