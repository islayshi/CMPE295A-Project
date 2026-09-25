from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from telemetry.models import EmergencyShelter

class Command(BaseCommand):
    help = 'Seeds emergency shelters in the SF Bay Area for evacuation routing.'

    def handle(self, *args, **options):
        shelters = [
            {
                "name": "Chabot College Emergency Shelter",
                "lat": 37.6253, "lon": -122.1068,
                "address": "25555 Hesperian Blvd, Hayward, CA 94545",
                "county": "Alameda", "capacity": 500
            },
            {
                "name": "San Jose Convention Center",
                "lat": 37.3293, "lon": -121.8890,
                "address": "150 W San Carlos St, San Jose, CA 95113",
                "county": "Santa Clara", "capacity": 2000
            },
            {
                "name": "Oakland Coliseum",
                "lat": 37.7516, "lon": -122.2005,
                "address": "7000 Coliseum Way, Oakland, CA 94621",
                "county": "Alameda", "capacity": 5000
            },
            {
                "name": "San Mateo County Event Center",
                "lat": 37.5458, "lon": -122.2988,
                "address": "1346 Saratoga Dr, San Mateo, CA 94403",
                "county": "San Mateo", "capacity": 1500
            },
            {
                "name": "Santa Cruz County Fairgrounds",
                "lat": 36.9427, "lon": -121.7275,
                "address": "2601 E Lake Ave, Watsonville, CA 95076",
                "county": "Santa Cruz", "capacity": 1000
            },
            {
                "name": "Cow Palace Arena",
                "lat": 37.7082, "lon": -122.4206,
                "address": "2600 Geneva Ave, Daly City, CA 94014",
                "county": "San Mateo", "capacity": 3000
            }
        ]

        created_count = 0
        for s in shelters:
            obj, created = EmergencyShelter.objects.get_or_create(
                name=s["name"],
                defaults={
                    "location": Point(s["lon"], s["lat"], srid=4326),
                    "address": s["address"],
                    "county": s["county"],
                    "capacity": s["capacity"],
                    "source": "FEMA"
                }
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {created_count} shelters (total {EmergencyShelter.objects.count()}).'))
