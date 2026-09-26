import os

# Tests must never need real credentials; settings only require a syntactically valid URL.
os.environ.setdefault("DATABASE_URL", "postgresql://sql_agent:unused@localhost:5432/unused")
