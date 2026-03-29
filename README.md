# zl — Z-Library CLI

Search and download ebooks from [Z-Library](https://z-library.sk) in your terminal.

Designed for both human and AI agent use.

## Install

```bash
brew install liangquanzhou/tap/zl
# or
pip install zlib-cli
```

## Quick Start

```bash
# Login (one-time, credentials saved locally)
zl login

# Search
zl search "clean code"
zl search "机器学习" -l chinese -e pdf

# Download by index from search results
zl download 3

# Download by book ID
zl download 5393918/a28f0c
```

## Commands

| Command | Description |
| --- | --- |
| `zl login` | Authenticate and save credentials |
| `zl search <query>` | Search books by title, author, or ISBN |
| `zl download <#\|ID>` | Download by result index or book ID |
| `zl info <#\|ID>` | Show detailed book metadata |
| `zl limits` | Show daily download quota and usage |
| `zl history` | Show download history |
| `zl config [key] [value]` | View or set configuration |

### Search Options

```
-l, --lang        Language filter (english, chinese, russian, ...)
-e, --ext         Format filter (pdf, epub, mobi, djvu, fb2, azw3, txt)
--year-from       Minimum publication year (inclusive)
--year-to         Maximum publication year (inclusive)
-n, --count       Number of results (default: 10)
--exact           Exact title match only
```

## Agent Integration

Pass `--json` to any command for structured JSON output on stdout. All human-readable messages go to stderr, so stdout is always clean JSON.

```bash
# Search → JSON array
zl search "clean code" --json
# [{"index": 1, "id": "5393918/a28f0c", "name": "Clean Code", "authors": "...", ...}]

# Download → JSON object
zl download 1 --json
# {"path": "/Users/you/Downloads/zlib/Clean Code.pdf", "size": 4231680}

# Limits → JSON object
zl limits --json
# {"daily_allowed": 10, "daily_amount": 3, "daily_remaining": 7}

# Errors are also JSON in --json mode
# {"error": "Login failed: ..."}
```

## Proxy

Auto-detects `all_proxy`, `https_proxy`, `http_proxy` from environment.

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
