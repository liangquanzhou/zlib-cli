"""Z-Library CLI entry point.

Designed for both human and AI agent use. Pass --json to any command
for machine-readable JSON output on stdout.
"""

import asyncio
import json as json_mod
import sys
import click
from rich.console import Console
from rich.table import Table

from .config import (
    load_config,
    save_config,
    load_last_search,
    save_last_search,
    get_download_dir,
    CONFIG_FILE,
)
from .client import ZlibClient

console = Console(stderr=True)
stdout_console = Console()


def run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def json_out(data):
    """Write JSON to stdout and exit."""
    click.echo(json_mod.dumps(data, ensure_ascii=False, indent=2))


def error_out(msg: str, as_json: bool = False):
    """Print error. JSON mode writes to stdout; human mode writes to stderr."""
    if as_json:
        json_out({"error": str(msg)})
        sys.exit(1)
    else:
        console.print(f"[red]{msg}[/red]")


def format_size(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def extract_book_id(url: str) -> str:
    """Extract book ID (e.g. '5393918/a28f0c') from URL path."""
    parts = url.strip("/").split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return url


def get_authors(book: dict) -> str:
    """Extract author string from a book dict."""
    authors = book.get("authors", "")
    if isinstance(authors, list):
        names = []
        for a in authors:
            if isinstance(a, dict):
                names.append(a.get("name", a.get("author", "")))
            else:
                names.append(str(a))
        return ", ".join(n for n in names if n)
    return str(authors) if authors else ""


def book_to_dict(book: dict, index: int | None = None) -> dict:
    """Normalize a book object to a flat dict for JSON output."""
    url = book.get("url", "")
    d = {
        "id": extract_book_id(url),
        "name": book.get("name", ""),
        "authors": get_authors(book),
        "year": book.get("year", ""),
        "extension": book.get("extension", ""),
        "size": book.get("size", ""),
        "language": book.get("language", ""),
        "url": url,
    }
    if index is not None:
        d["index"] = index
    for extra in ("publisher", "isbn", "rating", "description", "download_url"):
        val = book.get(extra)
        if val:
            d[extra] = val
    return d


# ── CLI group ──────────────────────────────────────────────────────


@click.group()
def cli():
    """Search and download ebooks from Z-Library.

    \b
    Workflow:
      1. zl login                  # one-time setup
      2. zl search "query"         # find books
      3. zl download <#>           # download by result index

    \b
    Agent integration:
      Pass --json to any command for structured JSON output on stdout.
      All human-readable messages go to stderr, so stdout is always clean JSON.

    \b
    Proxy:
      Auto-detects all_proxy/https_proxy/http_proxy from environment.
      Or set persistently: zl config proxy socks5://127.0.0.1:7890

    \b
    Config: ~/.config/zlib-cli/config.json
    Downloads: ~/Downloads/zlib/ (override with: zl config download_dir PATH)
    """
    pass


# ── login ──────────────────────────────────────────────────────────


@cli.command()
@click.option("--email", prompt="Email", help="Z-Library / SingleLogin email.")
@click.option(
    "--password", prompt="Password", hide_input=True, help="Z-Library password."
)
@click.option("--json", "as_json", is_flag=True, help="Output result as JSON.")
def login(email, password, as_json):
    """Authenticate and save credentials.

    Verifies credentials against Z-Library server, then saves to local config.
    Credentials are stored in ~/.config/zlib-cli/config.json (chmod 600).

    \b
    JSON output: {"ok": true} or {"error": "..."}
    """

    async def _verify():
        client = ZlibClient()
        if client.proxy_list:
            console.print(f"[dim]Using proxy: {client.proxy_list[0]}[/dim]")
        await client.login(email, password)

    try:
        run(_verify())
    except Exception as e:
        error_out(f"Login failed: {e}", as_json)
        if not as_json:
            console.print("[dim]Tip: zl config proxy socks5://127.0.0.1:7890[/dim]")
        return

    config = load_config()
    config["email"] = email
    config["password"] = password
    save_config(config)

    if as_json:
        json_out({"ok": True})
    else:
        console.print("[green]✓ Login successful, credentials saved.[/green]")


# ── search ─────────────────────────────────────────────────────────


@cli.command()
@click.argument("query")
@click.option("-l", "--lang", help="Language filter. Values: english, chinese, russian, etc.")
@click.option("-e", "--ext", help="File format filter. Values: pdf, epub, mobi, djvu, fb2, azw3, txt.")
@click.option("--year-from", type=int, help="Minimum publication year (inclusive).")
@click.option("--year-to", type=int, help="Maximum publication year (inclusive).")
@click.option("-n", "--count", default=10, show_default=True, help="Number of results to return.")
@click.option("--exact", is_flag=True, help="Exact title match only.")
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON array.")
def search(query, lang, ext, year_from, year_to, count, exact, as_json):
    """Search for books by title, author, or ISBN.

    \b
    Examples:
      zl search "clean code" -e pdf
      zl search "机器学习" -l chinese -n 20
      zl search "978-0-13-468599-1"             # search by ISBN

    Results are cached locally. Use the index number (#) with
    'zl download', 'zl info' to reference results.

    \b
    JSON output: array of objects with fields:
      index, id, name, authors, year, extension, size, language, url
    """

    async def _search():
        client = ZlibClient()
        await client.login()
        kwargs = {"count": count, "exact": exact}
        if lang:
            kwargs["lang"] = [lang]
        if ext:
            kwargs["extensions"] = [ext]
        if year_from:
            kwargs["from_year"] = year_from
        if year_to:
            kwargs["to_year"] = year_to
        return await client.search(query, **kwargs)

    try:
        results = run(_search())
    except Exception as e:
        error_out(f"Search failed: {e}", as_json)
        return

    if not results:
        if as_json:
            json_out([])
        else:
            console.print("[yellow]No results found.[/yellow]")
        return

    cache = []
    out_list = []
    for i, book in enumerate(results, 1):
        d = book_to_dict(book, index=i)
        out_list.append(d)
        cache.append({"id": d["id"], "name": d["name"], "ext": d["extension"]})

    save_last_search(cache)

    if as_json:
        json_out(out_list)
        return

    table = Table(title=f"Search: {query}", show_lines=False, padding=(0, 1))
    table.add_column("#", style="cyan", width=3, justify="right")
    table.add_column("Title", style="bold", max_width=45, overflow="ellipsis")
    table.add_column("Author", max_width=22, overflow="ellipsis")
    table.add_column("Year", width=4, justify="center")
    table.add_column("Ext", width=5, justify="center")
    table.add_column("Size", width=8, justify="right")
    table.add_column("ID", style="dim", max_width=18)

    for d in out_list:
        table.add_row(
            str(d["index"]),
            d["name"],
            d["authors"],
            str(d["year"]),
            d["extension"],
            d["size"],
            d["id"],
        )

    stdout_console.print(table)
    console.print(
        "\n[dim]Download: [bold]zl download <#>[/bold] or "
        "[bold]zl download <ID>[/bold][/dim]"
    )


# ── download ───────────────────────────────────────────────────────


@cli.command()
@click.argument("ref")
@click.option("-o", "--output", help="Output directory. Default: ~/Downloads/zlib/")
@click.option("--json", "as_json", is_flag=True, help="Output result as JSON.")
def download(ref, output, as_json):
    """Download a book to local disk.

    REF can be:
      - An index number from the last search (e.g. "3")
      - A book ID from Z-Library (e.g. "5393918/a28f0c")

    \b
    JSON output: {"path": "/abs/path/to/file.pdf", "size": 4231680}
    Error:       {"error": "..."}
    """
    if ref.isdigit():
        idx = int(ref)
        cache = load_last_search()
        if not cache or idx < 1 or idx > len(cache):
            error_out(f"Index {idx} out of range ({len(cache)} results). Run 'zl search' first.", as_json)
            return
        entry = cache[idx - 1]
        book_id = entry["id"]
        if not as_json:
            console.print(f"[dim]#{idx} {entry['name']}[/dim]")
    else:
        book_id = ref

    async def _download():
        client = ZlibClient()
        await client.login()
        return await client.download_book(book_id, output)

    if not as_json:
        console.print("[dim]Fetching download link...[/dim]")
    try:
        filepath, size = run(_download())
        if as_json:
            json_out({"path": str(filepath), "size": size})
        else:
            console.print(f"[green]✓ Saved: {filepath}  ({format_size(size)})[/green]")
    except Exception as e:
        error_out(f"Download failed: {e}", as_json)


# ── info ───────────────────────────────────────────────────────────


@cli.command()
@click.argument("ref")
@click.option("--json", "as_json", is_flag=True, help="Output book metadata as JSON.")
def info(ref, as_json):
    """Show detailed metadata for a book.

    REF can be an index number from the last search or a book ID.
    Fetches full metadata including description, ISBN, publisher, and download availability.

    \b
    JSON output: object with fields:
      id, name, authors, year, publisher, language, extension, size,
      isbn, rating, description, download_url
    """
    if ref.isdigit():
        idx = int(ref)
        cache = load_last_search()
        if not cache or idx < 1 or idx > len(cache):
            error_out("Index out of range. Run 'zl search' first.", as_json)
            return
        book_id = cache[idx - 1]["id"]
    else:
        book_id = ref

    async def _fetch():
        client = ZlibClient()
        await client.login()
        return await client.fetch_book(book_id)

    try:
        book = run(_fetch())
    except Exception as e:
        error_out(f"Fetch failed: {e}", as_json)
        return

    if as_json:
        json_out(book_to_dict(book))
        return

    fields = [
        ("Title", book.get("name", "")),
        ("Authors", get_authors(book)),
        ("Year", book.get("year", "")),
        ("Publisher", book.get("publisher", "")),
        ("Language", book.get("language", "")),
        ("Format", book.get("extension", "")),
        ("Size", book.get("size", "")),
        ("ISBN", book.get("isbn", "")),
        ("Rating", book.get("rating", "")),
    ]

    for label, val in fields:
        if val:
            stdout_console.print(f"  [bold]{label}:[/bold] {val}")

    desc = book.get("description", "")
    if desc:
        stdout_console.print(f"\n  [dim]{desc[:300]}{'...' if len(desc) > 300 else ''}[/dim]")

    dl = book.get("download_url", "")
    if dl and "Unavailable" not in str(dl):
        console.print(f"\n  [green]Available[/green] — [dim]zl download {book_id}[/dim]")
    else:
        console.print("\n  [yellow]Download unavailable (may require Tor/proxy)[/yellow]")


# ── limits ─────────────────────────────────────────────────────────


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Output limits as JSON.")
def limits(as_json):
    """Show today's download quota and usage.

    \b
    JSON output: {"daily_allowed": 10, "daily_amount": 3, "daily_remaining": 7, "daily_reset": "..."}
    """

    async def _limits():
        client = ZlibClient()
        await client.login()
        return await client.get_limits()

    try:
        data = run(_limits())
    except Exception as e:
        error_out(f"Fetch failed: {e}", as_json)
        return

    if as_json:
        json_out(data if isinstance(data, dict) else {"raw": str(data)})
        return

    if isinstance(data, dict):
        stdout_console.print(f"  Daily allowed:   {data.get('daily_allowed', '?')}")
        stdout_console.print(f"  Used today:      {data.get('daily_amount', '?')}")
        stdout_console.print(f"  Remaining:       {data.get('daily_remaining', '?')}")
        reset = data.get("daily_reset", "")
        if reset:
            stdout_console.print(f"  Resets at:       {reset}")
    else:
        stdout_console.print(f"  {data}")


# ── history ────────────────────────────────────────────────────────


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Output history as JSON array.")
def history(as_json):
    """Show recent download history from your Z-Library account.

    \b
    JSON output: array of objects with fields: name, extension, url
    """

    async def _history():
        client = ZlibClient()
        await client.login()
        return await client.get_history()

    try:
        results = run(_history())
    except Exception as e:
        error_out(f"Fetch failed: {e}", as_json)
        return

    if not results:
        if as_json:
            json_out([])
        else:
            console.print("[yellow]No download history.[/yellow]")
        return

    if as_json:
        json_out([book_to_dict(b, index=i) for i, b in enumerate(results, 1)])
        return

    table = Table(title="Download History")
    table.add_column("#", style="cyan", width=3, justify="right")
    table.add_column("Title", style="bold", max_width=50, overflow="ellipsis")
    table.add_column("Ext", width=5, justify="center")

    for i, book in enumerate(results, 1):
        table.add_row(
            str(i),
            book.get("name", "Unknown"),
            book.get("extension", ""),
        )

    stdout_console.print(table)


# ── config ─────────────────────────────────────────────────────────


@cli.command("config")
@click.argument("key", required=False)
@click.argument("value", required=False)
@click.option("--json", "as_json", is_flag=True, help="Output config as JSON.")
def config_cmd(key, value, as_json):
    """View or set configuration.

    \b
    Config keys:
      download_dir   Download directory (default: ~/Downloads/zlib)
      proxy          Proxy URL (e.g. socks5://127.0.0.1:7890)
      email          Z-Library login email
      password       Z-Library password (masked in human output)

    \b
    Usage:
      zl config                          # show all
      zl config download_dir             # show one key
      zl config download_dir ~/Books     # set a key
      zl config --json                   # all config as JSON (password masked)
    """
    cfg = load_config()

    if key is None:
        safe_cfg = {k: ("****" if k == "password" else v) for k, v in cfg.items()}
        if as_json:
            safe_cfg["_config_file"] = str(CONFIG_FILE)
            json_out(safe_cfg)
        else:
            for k, v in safe_cfg.items():
                stdout_console.print(f"  [bold]{k}:[/bold] {v}")
            console.print(f"\n  [dim]Config file: {CONFIG_FILE}[/dim]")
        return

    if value is None:
        val = cfg.get(key)
        if val is None:
            error_out(f"Key not set: {key}", as_json)
        else:
            display = "****" if key == "password" else val
            if as_json:
                json_out({key: display})
            else:
                stdout_console.print(f"  {key} = {display}")
        return

    cfg[key] = value
    save_config(cfg)
    if as_json:
        json_out({"ok": True, key: value})
    else:
        stdout_console.print(f"[green]✓ {key} = {value}[/green]")


# ── entry point ────────────────────────────────────────────────────


def main():
    cli()
