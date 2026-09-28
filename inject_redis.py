import redis
import json
import os

def main():
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        # Test connection
        r.ping()
        
        fixture_path = os.path.join(os.path.dirname(__file__), 'ml_adapter/fixtures/bay_area_fixture.json')
        with open(fixture_path, 'r') as f:
            data = json.load(f)
            
        r.set('ffwai:current_risk_map', json.dumps(data))
        print(f"Successfully injected {len(data.get('features', []))} features into Redis 'ffwai:current_risk_map'")
    except Exception as e:
        print(f"Error connecting to Redis or injecting data: {e}")

if __name__ == "__main__":
    main()
