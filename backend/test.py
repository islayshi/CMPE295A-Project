import requests
import re
import json

def test_direct_directory_scrape(channel="07", sector="psw"):
    base_url = f"https://cdn.star.nesdis.noaa.gov/GOES18/ABI/SECTOR/{sector}/{channel}/"
    print(f"📡 Scraping NOAA directory directly: {base_url}\n")
    
    try:
        res = requests.get(base_url, timeout=10)
        print(f"HTTP Response Status: {res.status_code}")
        
        if res.ok:
            # Extract all .jpg image references from the HTML directory index
            jpg_files = sorted(set(re.findall(r'href="([^"]+\.jpg)"', res.text)))
            
            # Filter out non-timestamped files like 'latest.jpg' or thumbnails
            valid_jpgs = [f for f in jpg_files if "latest" not in f and "thumbnail" not in f]
            print(f"Found {len(valid_jpgs)} raw image frames on NOAA CDN.")
            
            unique_frames = []
            for fname in valid_jpgs:
                # NOAA filename pattern: YYYYDDDHHMM_GOES18-ABI-psw-07-600x600.jpg
                match = re.search(r'(\d{4})(\d{3})(\d{2})(\d{2})_', fname)
                if match:
                    hour, minute = match.group(3), match.group(4)
                    time_label = f"{hour}:{minute} UTC"
                else:
                    time_label = "Scan"
                    
                unique_frames.append({
                    "time": time_label,
                    "url": base_url + fname
                })

            # Subsample down to 12 frames spaced roughly 2 hours apart
            if len(unique_frames) > 12:
                step = max(1, len(unique_frames) // 12)
                sampled = unique_frames[::step][:12]
            else:
                sampled = unique_frames

            print(f"\n--- Parsed {len(sampled)} Sampled Frames ---")
            print(json.dumps(sampled[:3], indent=2))
            return sampled
        else:
            print("Failed to reach NOAA directory.")
            
    except Exception as e:
        print(f"Error scraping NOAA directory: {e}")

if __name__ == "__main__":
    test_direct_directory_scrape()