FROM python:3.12-slim AS build
RUN python -m venv /venv
COPY app/requirements.txt .
RUN /venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser /var/log/nginx /var/lib/nginx
COPY --from=build /venv /venv
COPY app/ /app/
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY --chmod=755 start.sh /start.sh
ENV PATH="/venv/bin:$PATH" PYTHONUNBUFFERED=1
USER appuser
EXPOSE 8080
CMD ["/start.sh"]
