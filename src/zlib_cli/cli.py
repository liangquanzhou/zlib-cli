"""Z-Library CLI entry point."""

import asyncio
import click
from rich.console import Console
from rich.table import Table

from .config import (
    load_config,
    save_config,
    load_last_search,
    save_last_search,
    get_download_dir,
)
from .client import ZlibClient

console = Console()


def run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


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


# ── CLI group ──────────────────────────────────────────────────────


@click.group()
def cli():
    """zl - Z-Library CLI: search and download ebooks."""
    pass


# ── login ──────────────────────────────────────────────────────────


@cli.command()
@click.option("--email", prompt="Email", help="Z-Library / SingleLogin email")
@click.option(
    "--password", prompt="Password", hide_input=True, help="Z-Library password"
)
def login(email, password):
    """Save login credentials (verified on server)."""

    async def _verify():
        client = ZlibClient()
        if client.proxy_list:
            console.print(f"[dim]使用代理: {client.proxy_list[0]}[/dim]")
        await client.login(email, password)

    try:
        run(_verify())
    except Exception as e:
        console.print(f"[red]登录失败: {e}[/red]")
        console.print("[dim]提示: 如果网络超时，尝试设置代理: zl config proxy socks5://127.0.0.1:7890[/dim]")
        return

    config = load_config()
    config["email"] = email
    config["password"] = password
    save_config(config)
    console.print("[green]✓ 登录成功，凭据已保存。[/green]")


# ── search ─────────────────────────────────────────────────────────


@cli.command()
@click.argument("query")
@click.option("-l", "--lang", help="语言 (english / chinese / ...)")
@click.option("-e", "--ext", help="格式 (pdf / epub / mobi / ...)")
@click.option("--year-from", type=int, help="起始年份")
@click.option("--year-to", type=int, help="截止年份")
@click.option("-n", "--count", default=10, show_default=True, help="每页结果数")
@click.option("--exact", is_flag=True, help="精确匹配")
def search(query, lang, ext, year_from, year_to, count, exact):
    """Search for books. Example: zl search "clean code" -e pdf"""

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
        console.print(f"[red]搜索失败: {e}[/red]")
        return

    if not results:
        console.print("[yellow]未找到结果。[/yellow]")
        return

    table = Table(title=f"搜索: {query}", show_lines=False, padding=(0, 1))
    table.add_column("#", style="cyan", width=3, justify="right")
    table.add_column("标题", style="bold", max_width=45, overflow="ellipsis")
    table.add_column("作者", max_width=22, overflow="ellipsis")
    table.add_column("年份", width=4, justify="center")
    table.add_column("格式", width=5, justify="center")
    table.add_column("大小", width=8, justify="right")
    table.add_column("ID", style="dim", max_width=18)

    cache = []
    for i, book in enumerate(results, 1):
        url = book.get("url", "")
        book_id = extract_book_id(url)
        authors = get_authors(book)
        name = book.get("name", "Unknown")

        table.add_row(
            str(i),
            name,
            authors,
            str(book.get("year", "")),
            book.get("extension", ""),
            book.get("size", ""),
            book_id,
        )
        cache.append({"id": book_id, "name": name, "ext": book.get("extension", "")})

    save_last_search(cache)
    console.print(table)
    console.print(
        "\n[dim]下载: [bold]zl download <#>[/bold]（序号）或 "
        "[bold]zl download <ID>[/bold][/dim]"
    )


# ── download ───────────────────────────────────────────────────────


@cli.command()
@click.argument("ref")
@click.option("-o", "--output", help="输出目录")
def download(ref, output):
    """Download a book by # (from last search) or by book ID."""
    # Resolve ref → book_id
    if ref.isdigit():
        idx = int(ref)
        cache = load_last_search()
        if not cache or idx < 1 or idx > len(cache):
            console.print(
                f"[red]序号 {idx} 无效（共 {len(cache)} 条结果）。"
                "请先运行 zl search。[/red]"
            )
            return
        entry = cache[idx - 1]
        book_id = entry["id"]
        console.print(f"[dim]#{idx} {entry['name']}[/dim]")
    else:
        book_id = ref

    async def _download():
        client = ZlibClient()
        await client.login()
        return await client.download_book(book_id, output)

    console.print("[dim]正在获取下载链接...[/dim]")
    try:
        filepath, size = run(_download())
        console.print(
            f"[green]✓ 已保存: {filepath}  ({format_size(size)})[/green]"
        )
    except Exception as e:
        console.print(f"[red]下载失败: {e}[/red]")


# ── info ───────────────────────────────────────────────────────────


@cli.command()
@click.argument("ref")
def info(ref):
    """Show detailed info for a book by # or ID."""
    if ref.isdigit():
        idx = int(ref)
        cache = load_last_search()
        if not cache or idx < 1 or idx > len(cache):
            console.print("[red]序号无效。请先运行 zl search。[/red]")
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
        console.print(f"[red]获取失败: {e}[/red]")
        return

    fields = [
        ("标题", book.get("name", "")),
        ("作者", get_authors(book)),
        ("年份", book.get("year", "")),
        ("出版社", book.get("publisher", "")),
        ("语言", book.get("language", "")),
        ("格式", book.get("extension", "")),
        ("大小", book.get("size", "")),
        ("ISBN", book.get("isbn", "")),
        ("评分", book.get("rating", "")),
    ]

    for label, val in fields:
        if val:
            console.print(f"  [bold]{label}:[/bold] {val}")

    desc = book.get("description", "")
    if desc:
        console.print(f"\n  [dim]{desc[:300]}{'...' if len(desc) > 300 else ''}[/dim]")

    dl = book.get("download_url", "")
    if dl and "Unavailable" not in str(dl):
        console.print(f"\n  [green]可下载[/green] — [dim]zl download {book_id}[/dim]")
    else:
        console.print("\n  [yellow]下载不可用（可能需要 Tor/代理）[/yellow]")


# ── limits ─────────────────────────────────────────────────────────


@cli.command()
def limits():
    """Show today's download limits."""

    async def _limits():
        client = ZlibClient()
        await client.login()
        return await client.get_limits()

    try:
        data = run(_limits())
    except Exception as e:
        console.print(f"[red]获取失败: {e}[/red]")
        return

    if isinstance(data, dict):
        console.print(f"  每日额度: {data.get('daily_allowed', '?')}")
        console.print(f"  已使用:   {data.get('daily_amount', '?')}")
        console.print(f"  剩余:     {data.get('daily_remaining', '?')}")
        reset = data.get("daily_reset", "")
        if reset:
            console.print(f"  重置时间: {reset}")
    else:
        console.print(f"  {data}")


# ── history ────────────────────────────────────────────────────────


@cli.command()
def history():
    """Show recent download history."""

    async def _history():
        client = ZlibClient()
        await client.login()
        return await client.get_history()

    try:
        results = run(_history())
    except Exception as e:
        console.print(f"[red]获取失败: {e}[/red]")
        return

    if not results:
        console.print("[yellow]暂无下载记录。[/yellow]")
        return

    table = Table(title="下载历史")
    table.add_column("#", style="cyan", width=3, justify="right")
    table.add_column("标题", style="bold", max_width=50, overflow="ellipsis")
    table.add_column("格式", width=5, justify="center")

    for i, book in enumerate(results, 1):
        table.add_row(
            str(i),
            book.get("name", "Unknown"),
            book.get("extension", ""),
        )

    console.print(table)


# ── config ─────────────────────────────────────────────────────────


@cli.command("config")
@click.argument("key", required=False)
@click.argument("value", required=False)
def config_cmd(key, value):
    """Get/set config. Keys: download_dir, email. Example: zl config download_dir ~/Books"""
    cfg = load_config()

    if key is None:
        # Show all (mask password)
        for k, v in cfg.items():
            display = "****" if k == "password" else v
            console.print(f"  [bold]{k}:[/bold] {display}")
        console.print(f"\n  [dim]配置文件: {__import__('zlib_cli.config', fromlist=['CONFIG_FILE']).CONFIG_FILE}[/dim]")
        return

    if value is None:
        # Get single key
        val = cfg.get(key)
        if val is None:
            console.print(f"[yellow]未设置: {key}[/yellow]")
        else:
            display = "****" if key == "password" else val
            console.print(f"  {key} = {display}")
        return

    # Set
    cfg[key] = value
    save_config(cfg)
    console.print(f"[green]✓ {key} = {value}[/green]")


# ── entry point ────────────────────────────────────────────────────


def main():
    cli()
