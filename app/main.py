import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

from fasthtml.common import *
from app.config import DASHBOARD_PORT
from app.db import init_db
from app.components.layout import head_tags
from app.routes import dashboard, services, sync, auth, docs, api, history
from app import logstream
from app.pullers.notion import NotionPuller
from app.services.manager import register_puller

hdrs = head_tags()
app, rt = fast_app(hdrs=hdrs, live=True)

init_db()
logstream.install()
register_puller("notion", NotionPuller)

dashboard.register(rt)
services.register(rt)
sync.register(rt)
auth.register(rt)
docs.register(rt)
api.register(rt)
history.register(rt)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=DASHBOARD_PORT, reload=True)
