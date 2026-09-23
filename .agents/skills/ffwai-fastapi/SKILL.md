---
name: ffwai-fastapi
description: Expert guidelines for designing and integrating the FastAPI Machine Learning Adapter in the Fight Fire With AI project.
---

## When this skill should be used
- When building or modifying the FastAPI service that serves ML models for fire detection, prediction, or satellite imagery analysis.
- When defining the API contracts (OpenAPI/Swagger) between the Django monolith and the ML adapter.
- When optimizing inference performance (e.g., using ONNX, TensorRT, or async model loading).
- When configuring deployment environments specifically for GPU-accelerated workloads.

## When this skill should NOT be used
- When implementing core business logic, user management, or long-term data persistence (use `ffwai-django-celery` and `ffwai-postgis`).
- When handling general-purpose async background tasks not related to ML (use `ffwai-django-celery`).

## Purpose
This skill covers the development of a high-performance, specialized FastAPI microservice that acts as an adapter for Machine Learning workloads. In the "Fight Fire With AI" architecture, this service abstracts the complexity of ML inference (e.g., PyTorch, TensorFlow) away from the main Django application, providing clean, fast endpoints for prediction.

## Capabilities
- Designing non-blocking, async API endpoints for ML inference.
- Managing ML model lifecycles (loading, versioning, unloading) within a web server environment.
- Validating complex input data (e.g., arrays, tensors, images) using Pydantic.
- Exposing hardware utilization (GPU memory, inference latency) via health check endpoints.

## Best Practices for Fight Fire With AI
- **ML Adapter Bridging:** The FastAPI service should remain strictly isolated from the PostgreSQL database. It should accept input data (e.g., image URLs, sensor payloads, or raw matrices) via HTTP/REST from the Django/Celery backend, and return JSON predictions (e.g., bounding boxes, risk scores). 
- **Async and Concurrency:** Use FastAPI's asynchronous capabilities (`async def`) when downloading images or making external calls. However, actual ML inference is CPU/GPU bound; ensure inference is run in a `ThreadPoolExecutor` or `ProcessPoolExecutor` to avoid blocking the event loop.
- **Pydantic Validation:** Strictly define the input and output schemas for all ML endpoints using Pydantic. This ensures the Django backend sends correctly formatted data and provides automatic API documentation (Swagger UI) for developers.
- **Resource Management:** ML models can be large. Load models into memory once at application startup using FastAPI's lifespan events, rather than per-request. Monitor memory usage to prevent out-of-memory errors during concurrent requests.
- **Statelessness:** The FastAPI service must be entirely stateless. It should not track which user requested a prediction or store the results long-term. All state and routing logic must be handled by the Django backend upon receiving the FastAPI response.
