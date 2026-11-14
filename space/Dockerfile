# Hugging Face Space (Docker SDK) for the MCP Doctor web demo.
# Build context is the repo root:  docker build -f space/Dockerfile -t mcp-doctor-web .
FROM python:3.12-slim

# Spaces run containers as user 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    TIKTOKEN_CACHE_DIR=/home/user/.cache/tiktoken
WORKDIR /home/user/app

RUN pip install --no-cache-dir --user "flask>=3.0" "gunicorn>=22" "tiktoken>=0.7" \
 && python -c "import tiktoken; tiktoken.get_encoding('o200k_base')"

COPY --chown=user src/ src/
COPY --chown=user examples/ examples/
COPY --chown=user web/ web/

EXPOSE 7860
CMD ["gunicorn", "--chdir", "web", "--bind", "0.0.0.0:7860", "--workers", "2", "--timeout", "30", "app:app"]
