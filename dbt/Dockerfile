FROM python:3.11-slim-bookworm
RUN pip install --no-cache-dir "dbt-core==1.12.6" "dbt-postgres==1.11.0"
WORKDIR /app/dbt
ENV DBT_PROFILES_DIR=/app/dbt
CMD ["dbt", "build"]
