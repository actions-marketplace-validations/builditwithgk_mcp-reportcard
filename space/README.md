---
title: mcp-doctor
emoji: 🩺
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: true
license: mit
short_description: Health check and report card for MCP server tools
tags:
  - mcp
  - mcp-server
  - model-context-protocol
  - linter
  - fuzzing
  - llm
  - ai-agents
  - developer-tools
---

# 🩺 mcp-doctor

**A health check for MCP servers.** Paste a server's `tools/list` JSON and get a graded report card — tool names, descriptions, input schemas, safety annotations and token cost per turn, with a concrete fix for every issue.

- **Source & docs:** https://github.com/builditwithgk/mcp-doctor
- **This Space** runs the static checks only: it never connects to servers, calls tools or contacts an LLM, and nothing you paste is stored. For live checks and fuzzing of a server's error handling, use the CLI.

Built by [Gopi K Aitham (builditwithgk)](https://github.com/builditwithgk) — available for freelance and contract work on AI, agent, and MCP tooling.
