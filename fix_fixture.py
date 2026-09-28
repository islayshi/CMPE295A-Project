import json

file_path = "ml_adapter/fixtures/bay_area_fixture.json"
with open(file_path, "r") as f:
    data = json.load(f)

for feature in data["features"]:
    coords = feature["geometry"]["coordinates"][0]
    sw_lon, sw_lat = coords[0]
    
    # 500m in degrees (approx)
    d_lon = 0.0057
    d_lat = 0.0045
    
    se_lon, se_lat = round(sw_lon + d_lon, 4), sw_lat
    ne_lon, ne_lat = round(sw_lon + d_lon, 4), round(sw_lat + d_lat, 4)
    nw_lon, nw_lat = sw_lon, round(sw_lat + d_lat, 4)
    
    feature["geometry"]["coordinates"] = [[
        [sw_lon, sw_lat],
        [se_lon, se_lat],
        [ne_lon, ne_lat],
        [nw_lon, nw_lat],
        [sw_lon, sw_lat]
    ]]

with open(file_path, "w") as f:
    json.dump(data, f, indent=2)
print("Updated fixture.")
