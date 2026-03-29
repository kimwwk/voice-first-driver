import os
from dotenv import load_dotenv

load_dotenv()

AGENT_URL = os.getenv("AGENT_URL", "http://localhost:3001")
PORT = int(os.getenv("PORT", "3000"))
