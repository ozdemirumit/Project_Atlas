import asyncio
import sys

from atlas.api.app import create_app

if sys.platform == "win32":
    # psycopg's async driver cannot run on Windows' default ProactorEventLoop ("Psycopg cannot
    # use the 'ProactorEventLoop' to run in async mode") -- it needs SelectorEventLoop. This must
    # be set before uvicorn creates its event loop (which happens after this module finishes
    # importing), so setting it here at import time is early enough.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = create_app()
