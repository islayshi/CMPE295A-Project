import re

with open("backend/harvester/tests.py", "r") as f:
    content = f.read()

# Replace coordinates block 1
content = content.replace('''                "coordinates": [[
                    [-122.22, 37.05], [-122.21, 37.05],
                    [-122.21, 37.06], [-122.22, 37.06],
                    [-122.22, 37.05],
                ]],''', '''                "coordinates": [[
                    [-122.22, 37.05], [-122.2143, 37.05],
                    [-122.2143, 37.0545], [-122.22, 37.0545],
                    [-122.22, 37.05],
                ]],''')

# Replace coordinates block 2
content = content.replace('''                "coordinates": [[
                    [-122.21, 37.05], [-122.20, 37.05],
                    [-122.20, 37.06], [-122.21, 37.06],
                    [-122.21, 37.05],
                ]],''', '''                "coordinates": [[
                    [-122.2143, 37.05], [-122.2086, 37.05],
                    [-122.2086, 37.0545], [-122.2143, 37.0545],
                    [-122.2143, 37.05],
                ]],''')

# Replace cell_polygon
content = content.replace('''    cell_polygon = Polygon((
        (-122.22, 37.05), (-122.21, 37.05),
        (-122.21, 37.06), (-122.22, 37.06),
        (-122.22, 37.05),
    ), srid=4326)''', '''    cell_polygon = Polygon((
        (-122.22, 37.05), (-122.2143, 37.05),
        (-122.2143, 37.0545), (-122.22, 37.0545),
        (-122.22, 37.05),
    ), srid=4326)''')

with open("backend/harvester/tests.py", "w") as f:
    f.write(content)
