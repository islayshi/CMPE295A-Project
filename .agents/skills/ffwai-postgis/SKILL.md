---
name: ffwai-postgis
description: Expert guidelines for managing spatial data and complex routing queries using PostgreSQL and PostGIS in the Fight Fire With AI project.
---

## When this skill should be used
- When designing database schemas that involve spatial data (points, lines, polygons) for fires, routes, or assets.
- When writing or optimizing complex spatial SQL queries (e.g., intersection, containment, distance).
- When implementing geospatial routing algorithms (e.g., pgRouting) to calculate safe evacuation paths.
- When managing spatial indexes and database performance for GIS operations.

## When this skill should NOT be used
- When writing standard non-spatial Django ORM queries (use `ffwai-django-celery`).
- When setting up basic caching mechanisms (use `ffwai-redis`).
- When dealing with raster image processing for ML (use `ffwai-fastapi`).

## Purpose
This skill focuses on leveraging PostgreSQL and the PostGIS extension to handle the heavy lifting of spatial analysis and storage. For "Fight Fire With AI", this database is the source of truth for geographical data, active fire boundaries, and the road network used for safe evacuation routing.

## Capabilities
- Defining optimal PostGIS geometry and geography types based on precision requirements.
- Writing raw spatial SQL queries for advanced operations not fully supported by Django ORM.
- Utilizing pgRouting for calculating optimal paths avoiding hazard zones.
- Tuning PostgreSQL parameters (`shared_buffers`, `work_mem`) specifically for GIS workloads.

## Best Practices for Fight Fire With AI
- **Geospatial Routing Considerations:** When calculating evacuation routes, always incorporate the dynamic fire perimeter polygons as impassable obstacles. Use pgRouting to find paths that maximize distance from the fire front while minimizing travel time.
- **Indexing is Critical:** Ensure every spatial column has a GIST index. Regularly monitor and run `VACUUM ANALYZE` on highly dynamic spatial tables (like updated fire perimeters) to keep index statistics fresh.
- **Geometry vs. Geography:** Use the `Geometry` type (typically projected in Web Mercator, SRID 3857, or a local projection) for planar operations and fast bounding-box queries. Use `Geography` (SRID 4326) only when precise distance calculations over large areas of the globe are strictly necessary.
- **Batch Processing:** When importing large sets of sensor data or satellite polygons, use bulk insert operations and temporarily disable constraints or indexes if necessary, rebuilding them afterward to maintain performance.
- **Offload from Django:** For highly complex spatial joins or routing that spans multiple tables, write a custom PL/pgSQL function or a raw SQL view in PostGIS, rather than trying to force the Django ORM to handle it.
