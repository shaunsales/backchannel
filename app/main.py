from fasthtml.common import *
from app.config import DASHBOARD_PORT
from app.db import init_db
from app.components.layout import head_tags
from app.routes import dashboard

hdrs = head_tags()
app, rt = fast_app(hdrs=hdrs, live=True)

init_db()

dashboard.register(rt)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=DASHBOARD_PORT, reload=True)
