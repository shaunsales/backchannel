import json
import logging
from notion_client import Client
from app.pullers.base import BasePuller, PullResult

log = logging.getLogger(__name__)


class NotionPuller(BasePuller):

    def _client(self) -> Client:
        token = self.credentials.get("token", "")
        if not token:
            raise ValueError("Notion API token not configured")
        return Client(auth=token)

    def test_connection(self) -> bool:
        client = self._client()
        resp = client.search(query="", page_size=1)
        return "results" in resp

    def pull(self, cursor: str | None = None, since: str | None = None) -> PullResult:
        client = self._client()
        max_depth = self.config.get("max_depth", 5)
        documents = []

        log.info("Starting Notion sync (cursor=%s)", cursor or "none")

        # Paginate through all pages
        start_cursor = None
        page_num = 0
        skipped = 0
        while True:
            params = {"filter": {"property": "object", "value": "page"}, "page_size": 100}
            if start_cursor:
                params["start_cursor"] = start_cursor

            log.info("Fetching page list (batch cursor=%s)...", start_cursor or "start")
            resp = client.search(**params)
            batch = resp.get("results", [])
            log.info("Got %d pages in this batch", len(batch))

            for page in batch:
                page_num += 1
                last_edited = page.get("last_edited_time", "")
                title = _extract_title(page) or ""

                # Skip archived or trashed pages
                if page.get("archived") or page.get("in_trash"):
                    log.info("[%d] Skipped (archived/trashed): %s", page_num, title or "Untitled")
                    skipped += 1
                    continue

                # Skip untitled pages with no title at all
                if not title.strip():
                    log.info("[%d] Skipped (no title): %s", page_num, page["id"][:12])
                    skipped += 1
                    continue

                # Incremental: skip pages not edited since cursor
                if cursor and last_edited and last_edited <= cursor:
                    skipped += 1
                    continue

                log.info("[%d] Processing: %s (edited %s)", page_num, title, last_edited)
                doc = self.normalize(page, client, max_depth)
                if doc is None:
                    skipped += 1
                    continue

                # Skip pages with empty/trivial content
                body = doc["body_markdown"].strip()
                if not body:
                    log.info("[%d] Skipped (empty body): %s", page_num, title)
                    skipped += 1
                    continue

                documents.append(doc)
                log.info("[%d] Done: %s (%d chars markdown)", page_num, title, len(body))

            if not resp.get("has_more"):
                break
            start_cursor = resp.get("next_cursor")

        # New cursor = latest last_edited_time
        new_cursor = cursor or ""
        for doc in documents:
            ts = doc.get("source_ts", "")
            if ts > new_cursor:
                new_cursor = ts

        log.info("Notion sync complete: %d docs fetched, %d skipped, cursor=%s",
                 len(documents), skipped, new_cursor[:20] if new_cursor else "none")

        return PullResult(
            documents=documents,
            new_cursor=new_cursor,
            docs_new=len(documents),
        )

    def normalize(self, page: dict, client: Client, max_depth: int = 5) -> dict | None:
        page_id = page["id"]
        title = _extract_title(page)

        try:
            blocks = _fetch_blocks_recursive(client, page_id, depth=0, max_depth=max_depth)
            body_md = _blocks_to_markdown(blocks)
        except Exception as e:
            log.warning(f"Failed to fetch blocks for page {page_id}: {e}")
            body_md = ""

        metadata = {
            "url": page.get("url", ""),
            "parent_type": page.get("parent", {}).get("type", ""),
            "created_time": page.get("created_time", ""),
            "last_edited_by": page.get("last_edited_by", {}).get("id", ""),
        }

        return {
            "source_id": page_id,
            "title": title or "Untitled",
            "body_markdown": body_md,
            "metadata": json.dumps(metadata),
            "source_ts": page.get("last_edited_time", ""),
        }


def _extract_title(page: dict) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            title_parts = prop.get("title", [])
            return "".join(t.get("plain_text", "") for t in title_parts)
    return ""


def _fetch_blocks_recursive(client: Client, block_id: str, depth: int, max_depth: int) -> list:
    if depth >= max_depth:
        return []

    blocks = []
    start_cursor = None
    while True:
        params = {"block_id": block_id, "page_size": 100}
        if start_cursor:
            params["start_cursor"] = start_cursor

        resp = client.blocks.children.list(**params)

        for block in resp.get("results", []):
            if block.get("has_children"):
                block["_children"] = _fetch_blocks_recursive(
                    client, block["id"], depth + 1, max_depth
                )
            blocks.append(block)

        if not resp.get("has_more"):
            break
        start_cursor = resp.get("next_cursor")

    return blocks


def _rich_text_to_md(rich_texts: list) -> str:
    parts = []
    for rt in rich_texts:
        text = rt.get("plain_text", "")
        annot = rt.get("annotations", {})
        if annot.get("code"):
            text = f"`{text}`"
        if annot.get("bold"):
            text = f"**{text}**"
        if annot.get("italic"):
            text = f"*{text}*"
        if annot.get("strikethrough"):
            text = f"~~{text}~~"
        href = rt.get("href")
        if href:
            text = f"[{text}]({href})"
        parts.append(text)
    return "".join(parts)


def _blocks_to_markdown(blocks: list, indent: int = 0) -> str:
    lines = []
    prefix = "  " * indent

    for block in blocks:
        btype = block.get("type", "")
        data = block.get(btype, {})
        children = block.get("_children", [])

        if btype == "paragraph":
            text = _rich_text_to_md(data.get("rich_text", []))
            lines.append(f"{prefix}{text}")
            lines.append("")

        elif btype.startswith("heading_"):
            level = int(btype[-1])
            text = _rich_text_to_md(data.get("rich_text", []))
            lines.append(f"{prefix}{'#' * level} {text}")
            lines.append("")

        elif btype == "bulleted_list_item":
            text = _rich_text_to_md(data.get("rich_text", []))
            lines.append(f"{prefix}- {text}")

        elif btype == "numbered_list_item":
            text = _rich_text_to_md(data.get("rich_text", []))
            lines.append(f"{prefix}1. {text}")

        elif btype == "to_do":
            text = _rich_text_to_md(data.get("rich_text", []))
            checked = "x" if data.get("checked") else " "
            lines.append(f"{prefix}- [{checked}] {text}")

        elif btype == "toggle":
            text = _rich_text_to_md(data.get("rich_text", []))
            lines.append(f"{prefix}<details><summary>{text}</summary>")
            lines.append("")

        elif btype == "code":
            text = _rich_text_to_md(data.get("rich_text", []))
            lang = data.get("language", "")
            lines.append(f"{prefix}```{lang}")
            lines.append(f"{prefix}{text}")
            lines.append(f"{prefix}```")
            lines.append("")

        elif btype == "quote":
            text = _rich_text_to_md(data.get("rich_text", []))
            for line in text.split("\n"):
                lines.append(f"{prefix}> {line}")
            lines.append("")

        elif btype == "callout":
            icon = data.get("icon", {}).get("emoji", "")
            text = _rich_text_to_md(data.get("rich_text", []))
            lines.append(f"{prefix}> {icon} {text}")
            lines.append("")

        elif btype == "divider":
            lines.append(f"{prefix}---")
            lines.append("")

        elif btype == "image":
            url = ""
            if data.get("type") == "file":
                url = data.get("file", {}).get("url", "")
            elif data.get("type") == "external":
                url = data.get("external", {}).get("url", "")
            caption = _rich_text_to_md(data.get("caption", []))
            lines.append(f"{prefix}![{caption}]({url})")
            lines.append("")

        elif btype == "bookmark":
            url = data.get("url", "")
            caption = _rich_text_to_md(data.get("caption", []))
            lines.append(f"{prefix}[{caption or url}]({url})")
            lines.append("")

        elif btype == "table":
            pass  # table rows handled as children

        elif btype == "table_row":
            cells = data.get("cells", [])
            row_text = " | ".join(_rich_text_to_md(cell) for cell in cells)
            lines.append(f"{prefix}| {row_text} |")

        elif btype == "child_page":
            title = data.get("title", "Untitled")
            lines.append(f"{prefix}**[Subpage: {title}]**")
            lines.append("")

        elif btype == "child_database":
            title = data.get("title", "Untitled")
            lines.append(f"{prefix}**[Database: {title}]**")
            lines.append("")

        else:
            # Best-effort for unknown block types
            rich_text = data.get("rich_text", [])
            if rich_text:
                text = _rich_text_to_md(rich_text)
                lines.append(f"{prefix}{text}")
                lines.append("")

        if children:
            if btype == "toggle":
                lines.append(_blocks_to_markdown(children, indent + 1))
                lines.append(f"{prefix}</details>")
                lines.append("")
            else:
                lines.append(_blocks_to_markdown(children, indent + 1))

    return "\n".join(lines)
