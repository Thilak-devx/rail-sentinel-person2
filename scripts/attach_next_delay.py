import pandas as pd
import os

base = r"C:\Users\2026\OneDrive\Desktop\sih train"

# Step 1: Load current_delay_dataset
cd = pd.read_csv(os.path.join(base, "data", "processed", "current_delay_dataset.csv"))
print(f"Step 1 - Loaded current_delay_dataset: {len(cd)} rows")

# Step 2: Load delay lookup and rename for next-station target
dl = pd.read_csv(os.path.join(base, "data", "processed", "delay_lookup.csv"))
delay_next = dl.rename(
    columns={
        "station_code": "next_station_code",
        "arrival_delay_min": "target_next_arrival_delay_min",
    }
)
print(f"Step 2 - Renamed delay lookup columns: {list(delay_next.columns)}")

# Step 3: Verify uniqueness in renamed lookup
lookup_unique = delay_next.drop_duplicates(subset=["train_number", "date", "next_station_code"])
print(f"Step 3 - Uniqueness (train_number, date, next_station_code):")
print(f"  Original lookup rows: {len(delay_next)}")
print(f"  After dedup: {len(lookup_unique)}")
print(f"  Duplicates: {len(delay_next) - len(lookup_unique)}")

# Step 4: INNER merge current_delay_dataset with next delay lookup
merged = cd.merge(
    delay_next,
    on=["train_number", "date", "next_station_code"],
    how="inner",
)

print(f"\nStep 4 - INNER merge results:")
print(f"  current_delay_dataset rows: {len(cd)}")
print(f"  Matched rows: {len(merged)}")
print(f"  Output rows: {len(merged)}")

# Step 5: Verify logical key uniqueness AFTER merge
key_check = merged.duplicated(
    subset=["train_number", "date", "current_stn_serial", "next_stn_serial"]
).sum()
print(f"\nStep 5 - Logical key uniqueness (train_number, date, current_stn_serial, next_stn_serial):")
print(f"  Duplicates: {key_check}")
print(f"  Expected: 0")

# Step 6: Verify output rows <= 1,224,768
print(f"\nStep 6 - Row count check:")
print(f"  Output rows: {len(merged)}")
print(f"  Max allowed: 1224768")
print(f"  Within limit: {len(merged) <= 1224768}")

# Step 7: Validation checks
print(f"\n=== VALIDATION CHECKS ===")

# target delay never null
target_null = merged['target_next_arrival_delay_min'].isna().sum()
print(f"target_next_arrival_delay_min null count: {target_null}")

# current and next stations different
same_stn = (merged['current_station_code'] == merged['next_station_code']).sum()
print(f"current == next station: {same_stn}")

# current_stn_serial < next_stn_serial
serial_lt = (merged['current_stn_serial'] < merged['next_stn_serial']).sum()
print(f"current_stn_serial < next_stn_serial: {serial_lt} out of {len(merged)}")

# current delay stats
cur_min = merged['current_arrival_delay_min'].min()
cur_max = merged['current_arrival_delay_min'].max()
cur_mean = merged['current_arrival_delay_min'].mean()
cur_median = merged['current_arrival_delay_min'].median()
print(f"current_arrival_delay_min: min={cur_min}, max={cur_max}, mean={cur_mean:.2f}, median={cur_median:.2f}")

# target delay stats
tgt_min = merged['target_next_arrival_delay_min'].min()
tgt_max = merged['target_next_arrival_delay_min'].max()
tgt_mean = merged['target_next_arrival_delay_min'].mean()
tgt_median = merged['target_next_arrival_delay_min'].median()
print(f"target_next_arrival_delay_min: min={tgt_min}, max={tgt_max}, mean={tgt_mean:.2f}, median={tgt_median:.2f}")

# distance stats
dist_min = merged['distance_to_next_km'].min()
dist_max = merged['distance_to_next_km'].max()
dist_mean = merged['distance_to_next_km'].mean()
dist_median = merged['distance_to_next_km'].median()
print(f"distance_to_next_km: min={dist_min}, max={dist_max}, mean={dist_mean:.2f}, median={dist_median:.2f}")

# Special trains
print(f"\n=== SPECIAL TRAINS ===")
t16546 = merged[merged['train_number'] == 16546]
print(f"16546 rows: {len(t16546)}")
has_39_40 = ((t16546['current_stn_serial'] == 39) & (t16546['next_stn_serial'] == 40)).sum()
print(f"  16546 has 39->40: {has_39_40 > 0}")

t17029 = merged[merged['train_number'] == 17029]
print(f"17029 rows: {len(t17029)}")

t17030 = merged[merged['train_number'] == 17030]
print(f"17030 rows: {len(t17030)}")

# Step 8: Save output
output_path = os.path.join(base, "data", "processed", "eta_training_dataset.csv")
merged.to_csv(output_path, index=False)
print(f"\nStep 8 - Saved to: {output_path}")

# Step 9: Read back and report
read_back = pd.read_csv(output_path)
print(f"\n=== READ BACK VERIFICATION ===")
print(f"  Input rows (current_delay_dataset): {len(cd)}")
print(f"  Matched next-delay rows: {len(merged)}")
print(f"  Unmatched rows (current - matched): {len(cd) - len(merged)}")
print(f"  Output rows: {len(read_back)}")
print(f"  Duplicate logical keys: {read_back.duplicated(subset=['train_number', 'date', 'current_stn_serial', 'next_stn_serial']).sum()}")
print(f"  Null current delay: {read_back['current_arrival_delay_min'].isna().sum()}")
print(f"  Null target delay: {read_back['target_next_arrival_delay_min'].isna().sum()}")
print(f"  Current delay stats: min={read_back['current_arrival_delay_min'].min()}, max={read_back['current_arrival_delay_min'].max()}, mean={read_back['current_arrival_delay_min'].mean():.2f}, median={read_back['current_arrival_delay_min'].median():.2f}")
print(f"  Target delay stats: min={read_back['target_next_arrival_delay_min'].min()}, max={read_back['target_next_arrival_delay_min'].max()}, mean={read_back['target_next_arrival_delay_min'].mean():.2f}, median={read_back['target_next_arrival_delay_min'].median():.2f}")
print(f"  Distance stats: min={read_back['distance_to_next_km'].min()}, max={read_back['distance_to_next_km'].max()}, mean={read_back['distance_to_next_km'].mean():.2f}, median={read_back['distance_to_next_km'].median():.2f}")
print(f"  Current==Next station: {(read_back['current_station_code'] == read_back['next_station_code']).sum()}")
print(f"  current_stn_serial >= next_stn_serial: {(read_back['current_stn_serial'] >= read_back['next_stn_serial']).sum()}")

print(f"\n=== ALL DONE ===")
print(f"Output path: {output_path}")