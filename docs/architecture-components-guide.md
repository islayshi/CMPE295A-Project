# System Architecture Components Guide
**Project:** Fight Fire With AI  
**Purpose:** A technical reference guide for team members (Frontend, Backend, and ML) to understand the role, justification, and interactions of every major component in our system architecture.

---

## 1. Django (The Web Server & REST API)

### Role & Purpose
Django is the front door of our backend. Its primary job is to handle fast, synchronous HTTP requests from the React frontend, perform spatial queries (like A* evacuation routing), and return JSON responses in under 200 milliseconds. 

### Why We Chose It
* **"Batteries-Included" Framework:** Django provides built-in routing, ORM (Object-Relational Mapping), and security features out of the box, accelerating MVP development.
* **GeoDjango & PostGIS Support:** Django has native support for geographic data. This is critical for our project, as it allows us to perform complex spatial queries (e.g., "Find a path that avoids these fire risk polygons") directly in Python.
* **Python Parity:** Using Python on the backend ensures that both the Backend and ML teams are speaking the same programming language, reducing context switching.

### Interactions
* **React Frontend:** The frontend polls Django's REST API every 5 minutes (`GET /api/predictions/current/`).
* **Redis (Cache):** When polled, Django reads the latest predictions from the Redis in-memory cache to guarantee sub-100ms response times.
* **PostgreSQL (PostGIS):** Django queries the database to run spatial algorithms for dynamic evacuation routing.

---

## 2. Celery (The Background Task Orchestrator)

### Role & Purpose
Celery is our asynchronous task queue. It handles all the slow, heavy, "background" work that would otherwise freeze the Django web server. It consists of two parts:
1. **Celery Beat:** A cron-like scheduler that triggers workflows (e.g., "Start the daily inference pipeline at midnight").
2. **Celery Workers:** The processes that execute the tasks (harvesting data, uploading files, making HTTP requests).

### Why We Chose It
* **Decoupling I/O:** Fetching data from Google Earth Engine, NOAA, and NWS takes time. Celery moves this slow network I/O to the background.
* **Fault Tolerance & Resilience (AP Architecture):** Celery provides built-in exponential backoff. If the NOAA API is down, Celery automatically retries 3 times before failing gracefully. This ensures our system is highly resilient.
* **Database Protection:** Celery limits concurrency, acting as a shock absorber so massive ML tasks don't overwhelm our database connections.

### Interactions
* **Redis (Broker):** Celery Beat places task messages into Redis. Celery Workers pull tasks out of Redis to execute them.
* **External APIs:** Workers fetch weather, terrain, and vegetation data.
* **Amazon S3:** Workers aggregate the harvested data into `.npz` feature arrays and upload them to a shared S3 bucket for the ML team to use in model training.
* **FastAPI ML Adapter:** Workers trigger the ML inference by sending a `POST` request to FastAPI with the harvested data.
* **PostgreSQL & Redis:** After inference completes, Celery saves the historical GeoJSON to the database and updates the fast cache in Redis.

---

## 3. FastAPI (The ML Adapter & Anti-Corruption Layer)

### Role & Purpose
FastAPI acts as an isolated translation layer between the Backend (Django/Celery) and the Machine Learning models (U-Net, PINN, SageMaker). It receives standard JSON data, formats it into multi-dimensional mathematical Tensors, runs the inference, and translates the raw probabilities back into map-friendly GeoJSON polygons.

### Why We Chose It
* **Dependency Isolation ("Dependency Hell"):** ML models require massive libraries (PyTorch, TensorFlow, CUDA drivers). If we put this inside Django/Celery, our backend environment would become bloated and conflict-prone. FastAPI isolates the ML dependencies in their own clean environment.
* **API Contract (Team Boundaries):** It creates a clear boundary between teams. The Backend team just sends a JSON payload to a URL. The ML team owns the FastAPI service and can change the underlying models (U-Net, PINN, or SageMaker) without breaking the backend.
* **Performance:** FastAPI is incredibly fast and built natively for async Python, making it the industry standard for serving ML models.
* **Mock Mode:** Allows the backend team to build and test the entire system using a static GeoJSON response (`MOCK_INFERENCE=true`) while waiting for the ML team to finish training the models.

### Interactions
* **Celery:** Receives `POST /predict` containing harvested JSON features. Returns a GeoJSON FeatureCollection.
* **Amazon SageMaker:** Formats the backend data into tensors and invokes the SageMaker endpoint where the actual U-Net/PINN models are hosted.

---

## 4. Redis (The Message Broker & Fast Cache)

### Role & Purpose
Redis is an extremely fast, in-memory datastore. It serves two distinct purposes in our architecture:
1. **Message Broker:** The waiting room for Celery tasks.
2. **Fast Cache:** The storage location for the absolute latest fire prediction.

### Why We Chose It
* **Speed:** Because data lives in RAM rather than on a hard drive, read/write times are often under 1 millisecond.
* **Availability (The "A" in CAP Theorem):** Redis is the key to our system's Availability. If the ML inference fails, or if Celery crashes, Django can simply read the last known prediction from the Redis cache and serve it to the frontend with a `STALE` badge. The user is never left with a broken app.

### Interactions
* **Celery Beat:** Writes scheduled task messages into Redis.
* **Celery Workers:** Reads task messages from Redis. After generating a new prediction, overwrites the `current_risk_map` key.
* **Django:** Reads the `current_risk_map` key every time the React frontend polls the API.

---

## 5. PostgreSQL with PostGIS (The Primary Database)

### Role & Purpose
PostgreSQL is our persistent relational database. PostGIS is an extension that turns PostgreSQL into a powerful spatial database, allowing it to understand geometry (points, lines, polygons) and geography (Earth's curvature).

### Why We Chose It
* **Spatial Supremacy:** Standard databases only understand text and numbers. PostGIS understands coordinates. It allows us to ask questions like: *"Does this evacuation route line intersect with this fire risk polygon?"* directly in SQL.
* **Grid Architecture:** Our entire system relies on a 1x1 km Bay Area grid. PostGIS natively handles the indexing and querying of these 18,000 spatial grid cells.
* **Historical Permanence:** While Redis holds the *current* prediction, PostgreSQL stores the *entire history* of predictions, model performance metrics (ROC-AUC), and static terrain features (elevation, slope).

### Interactions
* **Django:** Queries PostGIS to execute the A* routing algorithm and serve historical performance metrics.
* **Celery:** Writes the final GeoJSON predictions into PostGIS for long-term storage after receiving them from FastAPI.
