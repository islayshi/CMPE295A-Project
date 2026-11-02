import os

# Enable in-memory SpatiaLite and LocMemCache for test suite runs unless explicitly overridden
os.environ.setdefault("USE_SPATIALITE", "1")
