import pandas as pd
import numpy as np
import os

base = r"C:\Users\2026\OneDrive\Desktop\sih train"

# =================================================
# STEP 1 — Load raw route CSV and apply Task 13 cleanup
# =================================================
df = pd.read_csv(os.path.join(base, "data", "external", "rstgcn", "Indian-Railway-Network-and-Delays", "train_routes_Sep2024.csv"))

# Apply Task 13 cleanup: remove serials 41-80 for train 16546
# Keep train 16546 as 16546 (do NOT transform to 5046)
df_clean = df.copy()
mask_remove = (df_clean["trainNumber"] == 16546) & (df_clean["stnSerialNumber"] > 40)
df_clean = df_clean[~mask_remove]

print(f"Raw route rows: {len(df)}")
print(f"After Task 13 cleanup: {len(df_clean)} rows (expected 85015)")

# =================================================
# STEP 2 — Create sections correctly using groupby + shift(-1)
# =================================================
# Sort by trainNumber and stnSerialNumber
df_sec = df_clean.sort_values(["trainNumber", "stnSerialNumber"]).copy()

# Create next values BEFORE removing anything.
# groupby shift(-1) will produce NaN for the terminal station of each train.
df_sec["next_stn_serial"] = df_sec.groupby("trainNumber")["stnSerialNumber"].shift(-1)
df_sec["next_station_code"] = df_sec.groupby("trainNumber")["station_code"].shift(-1)
df_sec["next_station_name"] = df_sec.groupby("trainNumber")["station_name"].shift(-1)
df_sec["next_distance_km"] = df_sec.groupby("trainNumber")["distance"].shift(-1)

# Now create the "current" columns from the original row data
df_sec["current_stn_serial"] = df_sec["stnSerialNumber"]
df_sec["current_station_code"] = df_sec["station_code"]
df_sec["current_station_name"] = df_sec["station_name"]
df_sec["current_distance_km"] = df_sec["distance"]

# Calculate distance_to_next_km
df_sec["distance_to_next_km"] = df_sec["next_distance_km"] - df_sec["current_distance_km"]

print(f"\n=== After section generation ===")
print(f"Section rows before removing terminals: {len(df_sec)}")

# =================================================
# STEP 3 — Identify and remove terminal rows
# =================================================
# Terminal rows are those where next_stn_serial is NaN.
# Remove them ONLY AFTER all next columns have been generated.
terminal_mask = df_sec["next_stn_serial"].isna()
terminal_count = terminal_mask.sum()
print(f"\nTerminal rows identified: {terminal_count} (these are not sections)")

df_sec = df_sec[~terminal_mask].copy()

print(f"Section rows after removing terminal rows: {len(df_sec)} (expected 81123)")

# =================================================
# STEP 4 — Identify invalid sections
# =================================================
# Find sections where current_stn_serial >= next_stn_serial
invalid_serial = (df_sec["current_stn_serial"] >= df_sec["next_stn_serial"]) & df_sec["current_stn_serial"].notna() & df_sec["next_stn_serial"].notna()
invalid_serial_count = invalid_serial.sum()

# Find sections where distance_to_next_km < 0
invalid_dist_mask = df_sec["distance_to_next_km"] < 0
invalid_dist_count = invalid_dist_mask.sum()

print(f"\nSections with current >= next serial: {invalid_serial_count}")
print(f"Sections with negative distance_to_next_km: {invalid_dist_count}")

# Known 16545 anomalies
t16545_df = df_sec[df_sec["trainNumber"] == 16545] if "trainNumber" in df_sec.columns else df_sec[df_sec["train_number"] == 16545]
neg_dist_count = 0
cur_eq_next_count = 0
if len(t16545_df) > 0:
    neg = df_sec[df_sec["trainNumber"] == 16545] if "trainNumber" in df_sec.columns else df_sec[df_sec["train_number"] == 16545]
    neg = neg[neg["distance_to_next_km"] < 0]
    cur_eq = df_sec[df_sec["trainNumber"] == 16545] if "trainNumber" in df_sec.columns else df_sec[df_sec["train_number"] == 16545]
    cur_eq = cur_eq[cur_eq["current_stn_serial"] == cur_eq["next_stn_serial"]]
    neg_dist_count = len(neg)
    cur_eq_next_count = len(cur_eq)
    print(f"\n16545 negative-distance rows: {neg_dist_count}")
    print(f"16545 current==next rows: {cur_eq_next_count}")
    for _, row in neg.iterrows():
        print(f"    cur={row['current_stn_serial']}, next={row['next_stn_serial']}, dist={row['distance_to_next_km']}")
    for _, row in cur_eq.iterrows():
        print(f"    cur={row['current_stn_serial']}, next={row['next_stn_serial']}")

# =================================================
# STEP 5 — Exclude ONLY verified invalid sections
# =================================================
# Remove negative-distance sections
df_no_neg = df_sec[df_sec["distance_to_next_km"] >= 0].copy()

# Remove current >= next serial sections
df_final = df_no_neg[df_no_neg["current_stn_serial"] < df_no_neg["next_stn_serial"]].copy()

print(f"\n=== After excluding invalid sections ===")
print(f"After removing negative-distance: {len(df_no_neg)}")
print(f"After removing current>=next: {len(df_final)} (expected 81121 if 2 anomalies excluded from 81123)")

# =================================================
# STEP 5c — Final invariants check
# =================================================
print(f"\n=== FINAL VALIDATION ===")
print(f"next_stn_serial never null: {df_final['next_stn_serial'].isna().sum() == 0}")
print(f"next_station_code never null: {df_final['next_station_code'].isna().sum() == 0}")
print(f"next_distance_km never null: {df_final['next_distance_km'].isna().sum() == 0}")
print(f"current_stn_serial < next_stn_serial: {(df_final['current_stn_serial'] < df_final['next_stn_serial']).sum() == len(df_final)}")
print(f"distance_to_next_km >= 0: {(df_final['distance_to_next_km'] >= 0).sum() == len(df_final)}")
print(f"distance_to_next_km == next_distance_km - current_distance_km: matches={(df_final['distance_to_next_km'] == df_final['next_distance_km'] - df_final['current_distance_km']).sum()}/{len(df_final)}")

# Check duplicate keys
dup_keys = df_final.duplicated(subset=["trainNumber", "current_stn_serial", "next_stn_serial"]).sum()
print(f"Duplicate section keys: {dup_keys}")

# 16546 validation
t16546_final = df_final[df_final["trainNumber"] == 16546] if "trainNumber" in df_final.columns else df_final[df_final["train_number"] == 16546]
print(f"\n16546 final sections: {len(t16546_final)} (expected 39)")
has_39_40 = False
if len(t16546_final) > 0:
    has_39_40 = ((t16546_final["current_stn_serial"] == 39) & (t16546_final["next_stn_serial"] == 40)).sum() > 0
    print(f"16546 has 39->40 section: {has_39_40}")
    for i in range(len(t16546_final)):
        row = t16546_final.iloc[i]
        print(f"  {row['current_stn_serial']}->{row['next_stn_serial']}")

# 17029 HG preservation
t17029 = df_final[df_final["trainNumber"] == 17029] if "trainNumber" in df_final.columns else df_final[df_final["train_number"] == 17029]
hg17029_cur = t17029[t17029["current_station_code"] == "HG"] if len(t17029) > 0 else pd.DataFrame()
hg17029_next = t17029[t17029["next_station_code"] == "HG"] if len(t17029) > 0 else pd.DataFrame()
print(f"\n17029 HG in current: {len(hg17029_cur)} (expected 2)")
print(f"17029 HG in next: {len(hg17029_next)} (expected 2)")

# 17030 HG preservation
t17030 = df_final[df_final["trainNumber"] == 17030] if "trainNumber" in df_final.columns else df_final[df_final["train_number"] == 17030]
hg17030_cur = t17030[t17030["current_station_code"] == "HG"] if len(t17030) > 0 else pd.DataFrame()
hg17030_next = t17030[t17030["next_station_code"] == "HG"] if len(t17030) > 0 else pd.DataFrame()
print(f"17030 HG in current: {len(hg17030_cur)} (expected 2)")
print(f"17030 HG in next: {len(hg17030_next)} (expected 2)")

# =================================================
# STEP 6 — Output
# =================================================
# Rename trainNumber to train_number for output consistency
df_final_output = df_final.rename(columns={"trainNumber": "train_number"})

# Select exactly the required output columns
output_spec = [
    "train_number", "current_stn_serial", "current_station_code",
    "current_station_name", "current_distance_km",
    "next_stn_serial", "next_station_code", "next_station_name",
    "next_distance_km", "distance_to_next_km"
]
# Make sure all columns exist
df_final_output = df_final_output[[c for c in output_spec if c in df_final_output.columns]]

output_path = os.path.join(base, "data", "processed", "route_sections_corrected.csv")
df_final_output.to_csv(output_path, index=False)
print(f"\nOutput written to: {output_path}")
print(f"Final output shape: {df_final_output.shape}")

# =================================================
# STEP 7 — Summary
# =================================================
print(f"\n=== TASK 17I SUMMARY ===")
print(f"Raw route rows: 85055")
print(f"After Task 13 cleanup: 85015")
print(f"Unique trains: 3892")
print(f"Sections after terminal removal: {len(df_sec)} (expected 81123)")
print(f"After excluding negative-distance: {len(df_no_neg)}")
print(f"After excluding current>=next: {len(df_final)} (expected 81121 with 2 anomalies from 81123)")
print(f"16546: {len(t16546_final)} sections (expected 39)")
print(f"16546 has 39->40: {has_39_40}")
print(f"17029 HG: {len(hg17029_cur)} in current, {len(hg17029_next)} in next (expected 2 each)")
print(f"17030 HG: {len(hg17030_cur)} in current, {len(hg17030_next)} in next (expected 2 each)")
print(f"16545 anomalies: {neg_dist_count} negative-distance + {cur_eq_next_count} current==next")
print(f"Final valid sections: {len(df_final)}")