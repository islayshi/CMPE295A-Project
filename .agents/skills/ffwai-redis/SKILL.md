---
name: ffwai-redis
description: Expert guidelines for utilizing Redis as a message broker and caching layer in the Fight Fire With AI project.
---

## When this skill should be used
- When configuring or optimizing Redis for use as the Celery message broker.
- When designing caching strategies for frequently accessed, computationally expensive data (e.g., active fire perimeters, static ML routing maps).
- When implementing pub/sub mechanisms for real-time alerts or websockets.
- When handling rate-limiting or distributed locking.

## When this skill should NOT be used
- When persisting critical, long-term spatial or relational data (use `ffwai-postgis` and `ffwai-django-celery`).
- When writing the application logic of Celery tasks themselves (use `ffwai-django-celery`).

## Purpose
This skill outlines how to leverage Redis effectively to ensure the "Fight Fire With AI" backend remains responsive and highly performant. Redis is critical for decoupling services (via Celery), managing real-time data streams, and reducing the load on the PostgreSQL database during high-traffic emergency events.

## Capabilities
- Configuring Redis connection pools and timeouts for high availability.
- Designing efficient key namespaces and TTL (Time-To-Live) strategies.
- Utilizing advanced Redis data structures (Hashes, Sorted Sets, Streams) for specific use cases like real-time leaderboards or event timelines.
- Implementing distributed locks to prevent race conditions in critical workflows.

## Best Practices for Fight Fire With AI
- **Broker Reliability:** When used as a Celery broker, ensure Redis is configured with appropriate persistence (RDB/AOF) if message loss is unacceptable, though prioritizing queue performance is often key. Monitor memory usage carefully to prevent OOM evictions of active tasks.
- **Caching Geospatial Results:** Complex PostGIS queries (e.g., routing away from fires) are expensive. Cache the results of these queries in Redis using a consistent hashing of the request parameters. Set an appropriate TTL based on the volatility of the fire event (e.g., 5-15 minutes).
- **Rate Limiting:** Implement strict rate limiting using Redis for public-facing APIs to protect the backend and ML services from being overwhelmed during a crisis.
- **Real-time Notifications:** Use Redis Pub/Sub or Redis Streams to push real-time updates (like new fire detections or evacuation orders) to connected clients without polling the database.
