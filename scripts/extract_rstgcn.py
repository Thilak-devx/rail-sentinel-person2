"""Extract RSTGCN dataset ZIP and inspect contents."""

import zipfile
import os

zip_path = r"C:/Users/2026/OneDrive/Desktop/sih train/data/external/rstgcn/Indian-Railway-Network-and-Delays.zip"
extract_to = r"C:/Users/2026/OneDrive/Desktop/sih train/data/external/rstgcn"

print(f"Extracting {zip_path} to {extract_to}")

with zipfile.ZipFile(zip_path, "r") as zf:
    names = zf.namelist()
    print(f"ZIP has {len(names)} entries")
    print("First 20 entries:")
    for name in names[:20]:
        print(f"  {name}")
    
    # Extract all
    zf.extractall(extract_to)
    print(f"\nExtracted to {extract_to}")
    
    # List extracted files
    extracted = os.listdir(extract_to)
    print(f"\nExtracted files/directories: {extracted}")
    
    # If there's a subdirectory, list its contents
    if len(extracted) == 1 and os.path.isdir(os.path.join(extract_to, extracted[0])):
        sub = os.path.join(extract_to, extracted[0])
        print(f"\nContents of {extracted[0]}:")
        print(os.listdir(sub))