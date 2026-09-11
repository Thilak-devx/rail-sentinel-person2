"""Task 17B: Build leakage-safe section-level supervised dataset using vectorized pandas."""
import pandas as pd
import numpy as np
import os
import time

base = r"C:\Users\2026\OneDrive\Desktop\sih train\data\external\rstgcn\Indian-Railway-Network-and-Delays"

# =============================================================================
# CONFIGURATION
# =============================================================================

# Known trains with repeated station codes that need special handling
REPEATED_STATION_TRAINS = {"17029", "17030"}

# Station code that repeats in the above trains
REPEATED_STATION_CODE = "HG"

# Output paths
OUTPUT_CSV = os.path.join(base, "data", "processed", "eta_section_supervised.csv")
REPORT_MD = os.path.join(base, "docs", "eta_section_supervised_report.md")

# =============================================================================
# STEP 1 — BUILD ROUTE SECTIONS (vectorized)
# =============================================================================

print("=== STEP 1: Build route sections (vectorized) ===")

df_routes = pd.read_csv(os.path.join(base, "train_routes_Sep2024.csv"), dtype=str)
df_routes["trainNumber"] = df_routes["trainNumber"].astype(str)

# Normalize train numbers: strip leading zeros for numeric IDs
def normalize_train(t):
    if pd.isna(t):
        return np.nan
    s = str(t).strip()
    if s.isdigit():
        return str(int(s))
    return s

df_routes["train_norm"] = df_routes["trainNumber"].apply(normalize_train)

# Sort by train and stnSerialNumber
df_routes_sorted = df_routes.sort_values(["train_norm", "stnSerialNumber"]).copy()

# Create sections using groupby shift (VECTORIZED - no Python loops)
# For each row, get the next row's values within the same train
df_sec = df_routes_sorted.groupby("train_norm").apply(
    lambda g: g.iloc[[i, i+1] for i in range(len(g)-1)]
).explode(["train_norm"]).reset_index(drop=True)

# Actually, let me use a simpler approach with shift
df_routes_sorted = df_routes.sort_values(["train_norm", "stnSerialNumber"]).copy()

# Create section pairs using shift within groups
df_sec_current = df_routes_sorted.groupby("train_norm").apply(
    lambda g: g.head(len(g)-1).reset_index(drop=True)
).reset_index(drop=True)

# Get current and next values using shift
df_sec = df_routes_sorted.iloc[:len(df_routes_sorted)-1].copy()  # all but last row of each train group
# Actually this is getting complicated. Let me use a different vectorized approach.

# Create sections by grouping and using shift
df_routes_sorted = df_routes.sort_values(["train_norm", "stnSerialNumber"]).copy()
df_sec = pd.DataFrame()
df_sec["train"] = df_routes_sorted.groupby("train_norm").apply(
    lambda g: g["train_norm"].values[:-1]
).explode()
# This is getting messy. Let me use a cleaner approach.

print("  Using groupby shift approach...")
# Let me use a simple iterative approach but only over routes, not delays
# The task says no Python loops over delay observations, but route sections are 81K, which is manageable

# Actually, let me re-read the task: "Do NOT use Python iteration over route rows"
# But we need to create sections. Let me use groupby + shift which is vectorized.

# Create sections using a proper vectorized approach
df_routes_sorted = df_routes.sort_values(["train_norm", "stnSerialNumber"]).copy()

# Create index for each row within its train group
df_routes_sorted["section_idx"] = df_routes_sorted.groupby("train_norm").cumcount()
# Keep only rows that have a next station (exclude last station of each train)
df_sec = df_routes_sorted[df_routes_sorted["section_idx"] < df_routes_sorted.groupby("train_norm")["section_idx"].max() - 1].copy()

# Now assign current and next values using shift within groups
df_sec = df_sec.sort_values(["train_norm", "stnSerialNumber"]).copy()
df_sec["current_stn_serial"] = df_sec.groupby("train_norm")["stnSerialNumber"].shift(-1)  # WRONG - shift gives next, not current
# I'm making errors with the shift direction. Let me be more careful.

print("  Rebuilding section creation...")
# Clean approach: use numpy indexing after groupby
df_routes_sorted = df_routes.sort_values(["train_norm", "stnSerialNumber"]).copy()
grp = df_routes_sorted.groupby("train_norm")
indices = grp.cumcount()
# Keep all rows except the last one from each group
mask = indices < grp["section_idx"].max() - 1  # hmm this is still messy

print("  Need to fix section creation approach.")