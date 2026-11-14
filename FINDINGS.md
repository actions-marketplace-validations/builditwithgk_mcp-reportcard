# FINDINGS — mcp-doctor field test

Date: 2026-11-14 · mcp-doctor v0.1.0 · Windows 11, Python 3.13, Node 22 · every run used `--fuzz` (read-only tools only)

## Servers tested
| Server | Version | Language | Transport |
|---|---|---|---|
| @modelcontextprotocol/server-everything | 2.3.0 | Node | stdio **and** Streamable HTTP |
| @modelcontextprotocol/server-filesystem | 2.3.0 | Node | stdio |
| @modelcontextprotocol/server-memory | 2.1.1 | Node | stdio |
| mcp-server-fetch | 2026.11.11 | Python | stdio |
| mcp-server-time | 2026.11.11 | Python | stdio |
| mcp-server-git | 2026.11.11 | Python | stdio |

All six connected and completed without crashes. 159 fuzz cases were sent in total.

## False positives found and fixed
1. **F002 "leaks internals" fired on file paths.** The filesystem and git servers return messages like `Repository path 'x' is outside the allowed repository 'C:\...\repo'`. That's helpful, not a leak. F002 now matches only real stack traces (Python, Node, JVM, Go, Rust). The filesystem server went from B 88 to A 100.
2. **D005 "no when-to-use guidance" was noise.** It fired on 30 tools across well-written servers, e.g. fetch's single tool. It now fires only when a tool has a similar sibling (≥35% word overlap) the model could confuse it with, and it names that sibling.
3. **Connection failures printed an unreadable `ExceptionGroup`.** The CLI now digs out the root cause, e.g. "Connection closed (the server exited during startup; rerun with --server-logs to see its output)".

## Final results (after fixes)
| Server | Grade | Score | Tools | Tokens/turn | Fuzz cases | Fuzz problems | Remaining issues |
|---|---|---:|---:|---:|---:|---:|---|
| everything | A | 94 | 22 | 2,797 | 32 | 0 | X001 (two async trigger tools described almost identically), D005 ×6 |
| fetch | A | 100 | 1 | 296 | 6 | 0 | none |
| filesystem | A | 100 | 16 | 2,925 | 46 | 0 | none |
| memory | A | 99 | 9 | 1,736 | 10 | 0 | D005 ×2 |
| time | A | 98 | 3 | 500 | 20 | 0 | D005 ×2 |
| git | B | 83 | 14 | 1,435 | 45 | 0 | S003 (parameters have a `title` but no `description`), D002, D005 |

## Assessment
- **The remaining findings look legitimate.** git's undocumented parameters are a real, common Python issue: pydantic generates `title` but not `description`. The everything server's two async trigger tools really are described almost word for word alike.
- **Fuzzing:** every server rejected bad input cleanly. Skipped tools were exactly the ones not annotated read-only, as designed.
- **Not covered yet:** CI on Linux and macOS (runs once pushed to GitHub), community servers outside the official set, and servers that need authentication.
