---
name: ffwai-django-celery
description: Expert guidelines and best practices for developing with the Django + Celery Monolith backend in the Fight Fire With AI project.
---

## When this skill should be used
- When designing or modifying Django models, views, or URLs for the core backend.
- When creating, updating, or debugging Celery tasks and workflows for asynchronous processing (e.g., triggering ML jobs, background notifications).
- When interacting with the Django ORM to store or retrieve operational data, user data, or event metadata.
- When structuring monolithic backend components to handle high-availability requirements during emergency/fire response scenarios.

## When this skill should NOT be used
- When performing heavy machine learning inference or training (use `ffwai-fastapi` instead).
- When writing raw spatial SQL queries or focusing purely on GIS routing (use `ffwai-postgis` instead).
- When configuring the underlying caching layer or message broker settings directly (use `ffwai-redis` instead).

## Purpose
This skill provides the architectural guidelines for maintaining a robust, scalable, and resilient core backend using Django and Celery. In the "Fight Fire With AI" project, the backend must efficiently orchestrate between user requests, spatial databases, and external ML services without blocking, ensuring reliable operation under high load.

## Capabilities
- Architecting Django models with optimal indexing and relations.
- Structuring Celery tasks for maximum reliability, including retries, dead-letter queues, and rate-limiting.
- Query optimization using Django ORM (e.g., `select_related`, `prefetch_related`).
- Designing robust API endpoints (Django REST Framework) that communicate with the frontend and ML adapters.
- Implementing Django 5.x Async Views and ASGI deployment for high concurrency scenarios.
- Utilizing advanced PostgreSQL features (e.g., `JSONField`) alongside PostGIS spatial fields.
- Ensuring data integrity with robust transaction management (`transaction.atomic`) for complex workflows.

## Best Practices for Fight Fire With AI
- **Asynchronous ML Orchestration:** The Django backend should *never* block waiting for the FastAPI ML adapter to finish inference. Always use Celery tasks to trigger ML endpoints, poll for status (if required), or handle webhooks when the ML adapter finishes processing imagery or predictions.
- **Resilience and Retries:** Fire emergency data must not be lost. Configure Celery tasks with exponential backoff and reliable retry mechanisms for any network-dependent actions (e.g., pushing notifications or syncing with external services).
- **ORM Optimization:** When querying fire incident events or user locations, avoid N+1 query problems. Ensure models interacting with the PostGIS database use the correct spatial fields (`django.contrib.gis.db.models`) and use spatial lookups efficiently.
- **Stateless Tasks:** Ensure Celery tasks are completely stateless and idempotent, allowing them to be safely retried in case of worker failure or scaling events.
- **Service Layer Pattern:** Keep DRF views and serializers lightweight (strictly for routing and validation). Move complex business logic, such as aggregating predictions or staging data for the ML adapter, into dedicated service modules.
- **Async REST Polling Endpoints:** Use `async def` views for frontend REST polling endpoints to handle high-volume telemetry traffic without blocking synchronous WSGI threads during an emergency.
- **Atomic Harvester Operations:** Wrap Celery data harvesting tasks (GOES-18, VIIRS) in `transaction.atomic()` to guarantee that partial or corrupted spatial data is never exposed to the A* routing engine if a task crashes.

## Testing & Quality
- Enforce comprehensive testing using `pytest-django` across all backend components.
- Utilize `factory_boy` to generate reliable mock spatial data (points, polygons) to thoroughly test PostGIS queries without needing a live production database.
- Require unit tests for Celery task failure states (e.g., simulating HTTP 500 errors from the FastAPI ML adapter) to guarantee that exponential backoff and retry logic functions properly under stress.
