FROM python:3.13.9-slim-trixie

WORKDIR /app

# System dependencies for building Python wheels (e.g., psycopg, Pillow)
# and Node.js for Tailwind CSS build
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl ca-certificates gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Python runtime defaults
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install pip dependencies
RUN pip install --upgrade pip
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install npm dependencies for Tailwind build
COPY backend/package*.json ./
RUN npm ci

# Create non-root user
RUN addgroup --system app && adduser --system --ingroup app app

# Copy project code after dependencies for better caching
COPY --chown=app:app backend /app

RUN npm run build:css


RUN mkdir -p /app/staticfiles /app/logs && chown -R app:app /app/staticfiles /app/logs

EXPOSE 8000

RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["daphne", "co2mmute.asgi:application", "--bind", "0.0.0.0", "--port", "8000"]
