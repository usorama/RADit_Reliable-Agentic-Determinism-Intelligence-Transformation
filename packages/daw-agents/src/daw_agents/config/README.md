# Configuration Module

This module contains configuration management for the DAW (Deterministic Agentic Workbench) system.

## Redis Configuration

### Overview

The Redis configuration module (`redis.py`) manages connections to Redis for dual-purpose use:

1. **Celery Broker** (Database 0): Message queue for background task execution
2. **LangGraph Checkpoints** (Database 1): State persistence for agent workflow recovery

### Architecture Decision

Using separate Redis databases instead of separate Redis instances provides:
- **Operational Efficiency**: Single container, single deployment, reduced overhead
- **Data Isolation**: Separate logical databases prevent key collisions
- **Independent Management**: Each use case can be scaled independently via LRU eviction

### Configuration

#### Environment Variables

```env
REDIS_HOST=localhost           # Redis server hostname
REDIS_PORT=6379              # Redis server port
REDIS_PASSWORD=secure_pass   # Redis authentication password (optional)
```

#### Docker Compose

Redis service is configured in `docker-compose.yml` with:
- Memory limit: 256MB with allkeys-lru eviction policy
- Persistence: Enabled with RDB snapshots
- Security: Password authentication
- Health checks: Redis ping validation

### Usage

#### Synchronous Client

```python
from config.redis import get_redis_client, RedisConfig

# Get client for Celery broker (database 0)
client = get_redis_client(db=0)
client.set("task_id", "task_data")
value = client.get("task_id")

# Get client for LangGraph checkpoints (database 1)
client = get_redis_client(db=1)
client.set("workflow_state", "{...}")
```

#### Asynchronous Client

```python
from config.redis import get_async_redis_client, RedisConfig

# Get async client for use in async contexts
client = await get_async_redis_client(db=0)
await client.set("task_id", "task_data")
value = await client.get("task_id")
await client.aclose()
```

#### URL Generation for Frameworks

```python
from config.redis import RedisConfig

config = RedisConfig()

# For Celery configuration
broker_url = config.celery_broker_url
# Output: redis://:password@localhost:6379/0

# For LangGraph configuration
checkpoint_url = config.langgraph_url
# Output: redis://:password@localhost:6379/1
```

### Database Allocation

| Database | Purpose | Use Case |
|----------|---------|----------|
| 0 | Celery Message Broker | Task queue, task status, worker state |
| 1 | LangGraph Checkpoints | Agent workflow state, decision trees, context |

### Performance Considerations

1. **Memory Limit (256MB)**:
   - Estimated for development/small production workloads
   - Increase `docker-compose.yml` `--maxmemory` for larger deployments
   - Monitor with `redis-cli INFO memory`

2. **Eviction Policy (allkeys-lru)**:
   - Least Recently Used keys are evicted when memory limit is reached
   - Suitable for both cache (Celery tasks) and persistent state (LangGraph)
   - For critical LangGraph state, consider increasing memory or using persistence

3. **Persistence (RDB Snapshots)**:
   - Enabled with `--appendonly yes`
   - Data survives container restarts
   - Configure backup retention in deployment

### Monitoring

#### Health Check

```bash
# Check Redis status
docker compose exec redis redis-cli ping
# Output: PONG

# Check database size
docker compose exec redis redis-cli INFO keyspace

# Check memory usage
docker compose exec redis redis-cli INFO memory
```

#### Debugging

```bash
# Connect to Redis CLI
docker compose exec redis redis-cli

# View Celery tasks (database 0)
SELECT 0
KEYS celery-*

# View LangGraph checkpoints (database 1)
SELECT 1
KEYS langgraph-*
```

### Integration Points

1. **Celery Configuration**:
   ```python
   from celery import Celery
   from config.redis import RedisConfig

   config = RedisConfig()
   app = Celery(__name__)
   app.conf.broker_url = config.celery_broker_url
   ```

2. **LangGraph Configuration**:
   ```python
   from langgraph.checkpoint import RedisSaver
   from config.redis import RedisConfig

   config = RedisConfig()
   saver = RedisSaver(url=config.langgraph_url)
   ```

### Testing

All Redis configuration is tested with:
- Unit tests for URL generation
- Environment variable loading
- Database separation verification
- Integration scenarios

```bash
# Run tests
pytest tests/config/test_redis.py -v
```

### Migration & Upgrades

When upgrading Redis or changing configuration:

1. Backup existing Redis data:
   ```bash
   docker compose exec redis redis-cli --rdb /data/backup.rdb
   ```

2. Stop services:
   ```bash
   docker compose stop
   ```

3. Update configuration/image
4. Start services:
   ```bash
   docker compose up -d
   ```

### Security

- **Authentication**: Redis requires password authentication
- **Network**: Redis is only exposed on `localhost:6379` by default
- **TLS**: For production, consider using Redis with TLS support
- **Firewall**: Restrict Redis access via network policies

### References

- [Redis Documentation](https://redis.io/documentation)
- [Redis Persistence](https://redis.io/topics/persistence)
- [Celery Documentation](https://docs.celeryproject.io/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
