# Requirements Analysis

## Version Conflicts Found:

1. **dbt-core & dbt-postgres**:
   - Main: >=1.7.4
   - Airflow: ==1.10.0
   - dbt-postgres: ==1.9.0
   - DBT: ==1.7.4

2. **slack-sdk**:
   - Alerting: ==3.27.1
   - Monitoring: ==3.26.2

3. **pydantic**:
   - Most files: ==2.5.3
   - Main: >=2.5.3

4. **pydantic-settings**:
   - Consumer/Producer: ==2.1.0
   - Main: >=1.1.0

## Common Dependencies Across Components:

### Core Dependencies (used by 3+ components):
- confluent-kafka==2.3.0 (producer, consumer, alerting, docker, scripts)
- psycopg2-binary==2.9.9 (consumer, docker, dbt, scripts)
- python-dotenv==1.0.0 (producer, consumer, alerting, scripts)
- pydantic==2.5.3 (producer, consumer, docker)
- httpx==0.26.0 (producer, docker, tests, scripts)
- requests==2.31.0 (main, monitoring, scripts)
- prometheus-client==0.19.0 (main, monitoring, docker)

### Component-Specific Dependencies:
- **Airflow**: apache-airflow-providers-*, dbt-core==1.10.0
- **DBT**: dbt-utils, dbt-expectations, mkdocs
- **Monitoring**: streamlit, plotly, opentelemetry, elasticsearch
- **Testing**: pytest ecosystem, testcontainers, locust
- **Scripts**: typer, alembic, fabric

## Recommendations:
1. Standardize DBT versions across all files
2. Align pydantic-settings versions
3. Update slack-sdk to consistent version
4. Create base requirements for common dependencies
5. Keep component-specific requirements minimal
