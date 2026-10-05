---
name: ffwai-postgis
description: Expert guidelines for managing spatial data and complex GIS queries using PostgreSQL and PostGIS in the Fight Fire With AI project.
---

## When this skill should be used
- When designing database schemas that involve spatial data (points, lines, polygons) for fire perimeters, grids, or emergency POIs.
- When writing or optimizing complex spatial SQL queries (e.g., intersection, containment, distance, zone warnings).
- When managing spatial indexes and database performance for GIS operations.

## When this skill should NOT be used
- When writing standard non-spatial Django ORM queries (use `ffwai-django-celery`).
- When setting up basic caching mechanisms (use `ffwai-redis`).
- When dealing with raster image processing for ML (use `ffwai-fastapi`).

## Purpose
This skill focuses on leveraging PostgreSQL and the PostGIS extension to handle the heavy lifting of spatial analysis and storage. For "Fight Fire With AI", this database is the source of truth for geographical data, active fire boundaries, Bay Area grid cells, and emergency shelter POIs.

## Capabilities
- Defining optimal PostGIS geometry and geography types based on precision requirements.
- Writing raw spatial SQL queries for advanced operations not fully supported by Django ORM.
- Spatial joins, bounding-box intersections, and nearest-neighbor distance lookups.
- Tuning PostgreSQL parameters (`shared_buffers`, `work_mem`) specifically for GIS workloads.

## Best Practices for Fight Fire With AI
- **Spatial Analysis & Zone Intersections:** When evaluating hazard zones, intersect dynamic fire risk polygons with grid cells and emergency shelter locations. Use PostGIS spatial indexing (`ST_Intersects`, `ST_DWithin`) to quickly identify affected zones.
- **Indexing is Critical:** Ensure every spatial column has a GIST index. Regularly monitor and run `VACUUM ANALYZE` on highly dynamic spatial tables (like updated fire perimeters) to keep index statistics fresh.
- **Geometry vs. Geography:** Use the `Geometry` type (typically projected in Web Mercator, SRID 3857, or WGS84 SRID 4326 for planar operations) for fast bounding-box queries. Use `Geography` (SRID 4326) only when precise spherical distance calculations over large areas of the globe are strictly necessary.
- **Batch Processing:** When importing large sets of sensor data or satellite polygons, use bulk insert operations and temporarily disable constraints or indexes if necessary, rebuilding them afterward to maintain performance.
- **Offload from Django:** For highly complex spatial joins spanning multiple tables, write a custom PL/pgSQL function or a raw SQL view in PostGIS, rather than trying to force the Django ORM to handle it.
