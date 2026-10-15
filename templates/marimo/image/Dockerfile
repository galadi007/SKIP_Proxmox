FROM python:3.12-slim

RUN useradd -m -u 1000 marimo

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY --chmod=755 entrypoint.sh /entrypoint.sh

USER marimo

WORKDIR /home/marimo/work

EXPOSE 2718
ENTRYPOINT ["/entrypoint.sh"]
