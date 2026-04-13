# Core Stack Network Map

```mermaid
graph TD
    op-connect-api --> admin-api
    corvus-neo4j --> corvus
    milvus-etcd --> milvus-standalone
    milvus-minio --> milvus-standalone
    postgres --> prefect-server
    prefect-server --> prefect-worker
```
