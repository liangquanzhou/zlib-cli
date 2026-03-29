"""Async Z-Library client wrapper with download support."""

import os
import re
import aiohttp
import zlibrary
from pathlib import Path

from .config import load_config, get_download_dir

# Match zlibrary's own User-Agent and timeout settings
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
    )
}
_TIMEOUT = aiohttp.ClientTimeout(total=300, connect=0, sock_connect=120, sock_read=300)


def sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in filenames."""
    name = re.sub(r'[\\/:*?"<>|]', "", name)
    name = name.strip(". ")
    return name[:200] if name else "book"


def _detect_proxy() -> list[str] | None:
    """Auto-detect proxy from env vars or config."""
    config = load_config()
    proxy = config.get("proxy")
    if proxy:
        return [proxy]

    # Check standard env vars (prefer socks5 for aiohttp-socks)
    for var in ("all_proxy", "ALL_PROXY", "https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY"):
        val = os.environ.get(var)
        if val:
            return [val]
    return None


class ZlibClient:
    """Wrapper around AsyncZlib with credential management and download."""

    def __init__(self):
        proxy_list = _detect_proxy()
        self.lib = zlibrary.AsyncZlib(proxy_list=proxy_list)
        self.proxy_list = proxy_list
        self._logged_in = False

    async def login(self, email: str | None = None, password: str | None = None):
        config = load_config()
        email = email or config.get("email")
        password = password or config.get("password")
        if not email or not password:
            raise RuntimeError("未找到登录凭据，请先运行: zl login")
        await self.lib.login(email, password)
        self._logged_in = True

    async def _ensure_login(self):
        if not self._logged_in:
            await self.login()

    async def search(self, query: str, **kwargs) -> list:
        await self._ensure_login()
        paginator = await self.lib.search(q=query, **kwargs)
        return paginator.result

    async def fetch_book(self, book_id: str) -> dict:
        await self._ensure_login()
        book = await self.lib.get_by_id(book_id)
        return book

    async def download_book(
        self,
        book_id: str,
        output_dir: str | None = None,
    ) -> tuple[Path, int]:
        """Download a book. Returns (filepath, bytes_downloaded)."""
        await self._ensure_login()
        book = await self.lib.get_by_id(book_id)

        download_url = book.get("download_url", "")
        if not download_url or "Unavailable" in str(download_url):
            raise RuntimeError(
                "该书下载不可用（可能需要 Tor）。\n"
                f"尝试在浏览器中打开: https://{self.lib.mirror}{book.get('url', '')}"
            )

        # Build full URL
        if not download_url.startswith("http"):
            download_url = f"https://{self.lib.mirror}{download_url}"

        # Use the cookies dict from zlibrary (same approach as lib._r)
        cookies = getattr(self.lib, "cookies", None)
        if not cookies:
            raise RuntimeError(
                "无法获取认证 cookies，请尝试重新登录: zl login\n"
                f"或在浏览器中手动下载: {download_url}"
            )

        dest = Path(output_dir) if output_dir else get_download_dir()
        dest.mkdir(parents=True, exist_ok=True)

        name = sanitize_filename(book.get("name", "book"))
        ext = book.get("extension", "pdf")
        filepath = dest / f"{name}.{ext}"

        # Avoid overwriting: append (1), (2), ...
        counter = 1
        base = filepath
        while filepath.exists():
            filepath = base.with_stem(f"{base.stem} ({counter})")
            counter += 1

        downloaded = 0
        connector = None
        if self.proxy_list:
            from aiohttp_socks import ChainProxyConnector
            connector = ChainProxyConnector.from_urls(self.proxy_list)
        async with aiohttp.ClientSession(
            headers=_HEADERS,
            cookie_jar=aiohttp.CookieJar(unsafe=True),
            cookies=cookies,
            timeout=_TIMEOUT,
            connector=connector,
        ) as session:
            async with session.get(download_url, allow_redirects=True) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"下载失败: HTTP {resp.status}")
                with open(filepath, "wb") as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        f.write(chunk)
                        downloaded += len(chunk)

        return filepath, downloaded

    async def get_limits(self) -> dict:
        await self._ensure_login()
        return await self.lib.profile.get_limits()

    async def get_history(self) -> list:
        await self._ensure_login()
        paginator = await self.lib.profile.download_history()
        return paginator.result
