# zl — Z-Library CLI

Search and download ebooks from [Z-Library](https://z-library.sk) in your terminal.

## Install

```bash
pip install zlib-cli
# or
uv pip install zlib-cli
```

## Quick Start

```bash
# Login (credentials saved locally)
zl login

# Search
zl search "clean code"
zl search "机器学习" -l chinese -e pdf

# Download by # from search results
zl download 3

# Download by book ID
zl download 5393918/a28f0c
```

## Commands

| Command | Description |
| --- | --- |
| `zl login` | Save Z-Library / SingleLogin credentials |
| `zl search <query>` | Search books (supports filters) |
| `zl download <#\|ID>` | Download by result # or book ID |
| `zl info <#\|ID>` | Show detailed book metadata |
| `zl limits` | Show daily download quota |
| `zl history` | Show download history |
| `zl config [key] [value]` | View or set configuration |

### Search Options

```
-l, --lang        Language filter (english, chinese, ...)
-e, --ext         Format filter (pdf, epub, mobi, ...)
--year-from       Minimum publication year
--year-to         Maximum publication year
-n, --count       Results per page (default: 10)
--exact           Exact match
```

## Proxy

`zl` auto-detects proxy from environment variables (`all_proxy`, `https_proxy`, `http_proxy`).

To set a persistent proxy:

```bash
zl config proxy socks5://127.0.0.1:7890
```

## Configuration

Config stored at `~/.config/zlib-cli/config.json` (chmod 600).

| Key | Description | Default |
| --- | --- | --- |
| `email` | Z-Library email | — |
| `password` | Z-Library password | — |
| `download_dir` | Download directory | `~/Downloads/zlib` |
| `proxy` | Proxy URL | auto-detect from env |

## License

MIT
