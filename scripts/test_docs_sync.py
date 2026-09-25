"""Self-check for docs_sync.py's path mapping. Run: python3 scripts/test_docs_sync.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from docs_sync import link_to_page, page_key  # noqa: E402

# Links and files resolve to the same page key, however the link is written.
assert link_to_page("core-concepts/pipelines/schema#taskmodel") == "docs/core-concepts/pipelines/schema"
assert link_to_page("integrations/python/") == "docs/integrations/python"
assert link_to_page("mcp.") == "docs/mcp"  # trailing sentence punctuation
assert page_key("docs/integrations/python.mdx") == "docs/integrations/python"
assert page_key("docs/integrations/dbt_core/index.mdx") == "docs/integrations/dbt_core"
assert page_key("docs/faq.md") == "docs/faq"

print("docs_sync: ok")
