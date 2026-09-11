"""Download RSTGCN dataset from GitHub."""

import requests
import json
import os

base = "C:/Users/2026/OneDrive/Desktop/sih train"

# Create output directory
output_dir = os.path.join(base, "data", "external", "rstgcn")
os.makedirs(output_dir, exist_ok=True)

# Download directory listing from GitHub API
print("Fetching RSTGCN dataset from GitHub...")
headers = {"Accept": "application/vnd.github+v3+json"}
url = "https://api.github.com/repos/KoyenaChowdhury/RSTGCN/contents"

try:
    r = requests.get(headers=headers, url=url, timeout=30)
    if r.status_code != 200:
        print(f"GitHub API error: {r.status_code}")
        print(r.text[:500])
    else:
        items = r.json()
        print(f"Found {len(items)} items in repository")
        
        # Download each file
        for item in items:
            if item.get('type') == 'file':
                download_url = item.get('download_url')
                if download_url:
                    fname = item['name']
                    fpath = os.path.join(output_dir, fname)
                    print(f"Downloading {fname} ({item.get('size', 0)} bytes)...")
                    try:
                        dl_r = requests.get(download_url, timeout=60)
                        if dl_r.status_code == 200:
                            with open(fpath, 'wb') as f:
                                f.write(dl_r.content)
                            print(f"  Saved to {fpath}")
                        else:
                            print(f"  Failed to download: status {dl_r.status_code}")
                    except Exception as e:
                        print(f"  Error: {e}")
                else:
                    print(f"  No download_url for {item['name']}")
        
        # Also check for .zip release
        print("\nChecking for releases...")
        rel_r = requests.get(headers=headers, url="https://api.github.com/repos/KoyenaChowdhury/RSTGCN/releases", timeout=15)
        if rel_r.status_code == 200:
            releases = rel_r.json()
            for rel in rels[:3]:  # Show first 3 releases
                print(f"  Release: {rel.get('name', 'uncategorized')} - {rel.get('tag_name', 'no tag')}")
        else:
            print(f"  No releases accessible: status {rel_r.status_code}")
            
except Exception as e:
    print(f"Error: {e}")
    print("Trying alternative: direct download from known path...")
    
    # Try direct download of known dataset structure
    # The paper describes the dataset structure, so we know what to expect
    print("\nDataset structure from paper:")
    print("  - 1,282,326 train records")
    print("  - 3,892 long-distance trains")
    print("  - 4,735 stations")
    print("  - Period: September 1-30, 2024")
    print("  - Columns: Date, Train No., Train Name, Code, Station, Dist.,")
    print("    Sch. Arr., Act. Arr., Arr. Delay, Sch. Dep., Act. Dep., Dep. Delay")
    print("  - Format: CSV or similar tabular format")
    
    # Create a placeholder dataset description
    print("\nNote: Manual download may be required from GitHub:")
    print("  https://github.com/KoyenaChowdhury/RSTGCN")
    print("  Place files under: data/external/rstgcn/")
PYEOF