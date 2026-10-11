import ee

SERVICE_ACCOUNT_FILE = 'gee_service_account.json'

try:
    credentials = ee.ServiceAccountCredentials(key_file=SERVICE_ACCOUNT_FILE)
    ee.Initialize(credentials)

    # Use modern NASA DEM dataset
    dem = ee.Image('NASA/NASADEM_HGT/001')
    print("✅ GEE Connection Successful!")
    print("Asset ID:", dem.get('system:id').getInfo())

except Exception as e:
    print("❌ GEE Initialization Error:", e)