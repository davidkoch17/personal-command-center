"""Finance build-check: categorize + summarize new rows without writing anything."""
import pandas as pd
from pathlib import Path

base = Path(r"C:\Users\david\OneDrive\David_Work_OS\2_Personal\09_Finance Tracker\Finance Tracker")
src = base / "00_Input" / "2026-07-13_All_Sources_Consolidated.xlsx"

KEYWORD_MAP = [
    ("WOLT", "Restaurants"), ("FREENOW", "Transport"), ("LIME*RIDE", "Transport"),
    ("LIME*PRIME", "Transport"), ("BOLT OPERATIONS", "Transport"), ("UBER", "Transport"),
    ("MILES MOBILITY", "Transport"), ("VOI ", "Transport"), ("ENTERPRISE RENT", "Transport"),
    ("3CPAYMENT", "Transport"), ("DB VERTRIEB", "Transport"), ("RASTST", "Restaurants"),
    ("REWE", "Groceries"), ("EDEKA", "Groceries"), ("ALDI", "Groceries"),
    ("LIDL", "Groceries"), ("DM-DROGERIE", "Groceries"), ("ROSSMANN", "Groceries"),
    ("PUBLIX", "Groceries"), ("BROETCHENMA", "Groceries"), ("MEYER FEINKOST", "Groceries"),
    ("PATUARY", "Groceries"), ("HOFLINGER", "Groceries"),
    ("MCDONALD", "Restaurants"), ("BURGER KING", "Restaurants"), ("CHIPOTLE", "Restaurants"),
    ("CHICK-FIL-A", "Restaurants"), ("RAISING CANE", "Restaurants"), ("PANDA EXPRESS", "Restaurants"),
    ("SWEETGREEN", "Restaurants"), ("WENDY", "Restaurants"), ("SHAKE SHACK", "Restaurants"),
    ("PLAYA BOWLS", "Restaurants"), ("PLANK CAFE", "Restaurants"), ("SHUKA BAR", "Restaurants"),
    ("NAMY FOOD", "Restaurants"), ("PIZZERIA", "Restaurants"), ("MILLE LIRE", "Restaurants"),
    ("FORTY FOUR", "Restaurants"), ("CONDESA", "Restaurants"), ("MONZA CAFFE", "Restaurants"),
    ("HA LONG BAY", "Restaurants"), ("RESIDENZ HEINZ WINKLER", "Restaurants"),
    ("5TH AVENUE COFFEE", "Restaurants"), ("OBRIANS", "Restaurants"), ("CALAVERAS", "Restaurants"),
    ("FK BOCA", "Restaurants"),
    ("LUFTHANSA", "Travel"), ("AIRALO", "Travel"), ("BOOKING.COM", "Travel"),
    ("HOTEL ON BOOKING", "Travel"), ("AIRBNB", "Travel"),
    ("EXXON", "Transport"), ("SHELL SERVICE", "Transport"),
    ("APPLE.COM/BILL", "Subscriptions"), ("NETFLIX", "Subscriptions"), ("SPOTIFY", "Subscriptions"),
    ("ANTHROPIC", "Subscriptions"), ("HOSTINGER", "Subscriptions"), ("MONATSGEB", "Subscriptions"),
    ("AMAZON", "Shopping"), ("IKEA", "Shopping"), ("SATURN", "Shopping"),
    ("WESTWING", "Shopping"), ("COOLBLUE", "Shopping"), ("JOOP", "Shopping"),
    ("EMMA", "Shopping"), ("SEPHORA", "Shopping"), ("FOTO-VIDEO", "Shopping"),
    ("ATELIERZICK", "Shopping"),
    ("NICE FRISEUR", "Health"), ("CLEVER FIT", "Health"),
    ("HOBEX", "Entertainment"), ("LIV 296", "Entertainment"), ("UNVRS", "Entertainment"),
    ("RED REEF GOLF", "Entertainment"), ("GOLF COURSE", "Entertainment"),
    ("TELEKOM", "Utilities"), ("AXA", "Other"),
]


def categorize(desc: str) -> str:
    du = desc.upper()
    for kw, cat in KEYWORD_MAP:
        if kw.upper() in du:
            return cat
    return "Other"


# Amex
amex = pd.read_excel(src, sheet_name="Amex")
amex["Date"] = pd.to_datetime(amex["Datum"], dayfirst=True)
amex_new = amex[(amex["Date"] >= "2026-06-01") & (amex["Note"] == "purchase")].copy()
amex_rows = []
for _, r in amex_new.iterrows():
    cat = categorize(str(r["Beschreibung"]))
    amex_rows.append({
        "Date": r["Date"], "Month": r["Date"].strftime("%Y-%m"),
        "Description": str(r["Beschreibung"])[:50].strip(),
        "Amount": round(float(r["Betrag_EUR"]), 2),
        "Category": cat, "Card": "Amex", "Notes": "",
    })

# TF_Bank
tfb = pd.read_excel(src, sheet_name="TF_Bank")
tfb["Date"] = pd.to_datetime(tfb["Date"])
tfb_new = tfb[(tfb["Date"] >= "2026-06-01") & (tfb["Type"] == "purchase")].copy()
tfb_rows = []
for _, r in tfb_new.iterrows():
    merchant = str(r["Merchant"])
    cat = categorize(merchant + " " + str(r["Description"]))
    amount = abs(float(r["Rechnungsbetrag_EUR"]))
    tfb_rows.append({
        "Date": r["Date"], "Month": r["Date"].strftime("%Y-%m"),
        "Description": merchant[:50].strip(),
        "Amount": round(amount, 2),
        "Category": cat, "Card": "TF Bank", "Notes": "",
    })

# Haspa direct debits (new only; Jun 1 + Jun 2 already loaded)
haspa_rows = [
    {"Date": pd.Timestamp("2026-06-16"), "Month": "2026-06", "Description": "Netflix Services Germany",
     "Amount": 19.99, "Category": "Subscriptions", "Card": "Haspa", "Notes": ""},
    {"Date": pd.Timestamp("2026-06-17"), "Month": "2026-06", "Description": "Telekom Mobilfunk",
     "Amount": 34.95, "Category": "Utilities", "Card": "Haspa", "Notes": ""},
    {"Date": pd.Timestamp("2026-06-22"), "Month": "2026-06", "Description": "Spotify AB",
     "Amount": 12.99, "Category": "Subscriptions", "Card": "Haspa", "Notes": ""},
    {"Date": pd.Timestamp("2026-06-29"), "Month": "2026-06", "Description": "AXA Haftpflicht Erstbeitrag",
     "Amount": 48.29, "Category": "Other", "Card": "Haspa", "Notes": ""},
    {"Date": pd.Timestamp("2026-07-02"), "Month": "2026-07", "Description": "Leo Nehmzow Miete 07",
     "Amount": 1135.25, "Category": "Rent", "Card": "Haspa", "Notes": "First rent Jul 2026"},
]

all_rows = sorted(amex_rows + tfb_rows + haspa_rows, key=lambda x: x["Date"])
df = pd.DataFrame(all_rows)

print("=== TRANSACTION SUMMARY ===")
print(f"Total new rows: {len(df)}")
print()

for month in ["2026-06", "2026-07"]:
    sub = df[df["Month"] == month]
    print(f"--- {month} ({len(sub)} rows, total cards: {sub['Card'].nunique()}) ---")
    by_cat = sub.groupby("Category")["Amount"].sum().sort_values(ascending=False)
    for cat, amt in by_cat.items():
        print(f"  {cat:<22} {amt:>9.2f}")
    print(f"  {'TOTAL':<22} {sub['Amount'].sum():>9.2f}")
    print()

# Flag items needing manual review
print("=== ITEMS TO CONFIRM ===")
flags = df[df["Category"] == "Other"].copy()
for _, r in flags.iterrows():
    print(f"  {str(r['Date'])[:10]}  {r['Card']:<8}  {r['Amount']:>8.2f}  {r['Description'][:45]}")

print()
# PAYPAL *INFO
paypal_info = df[df["Description"].str.contains("PAYPAL.*INFO|PayPal.*INFO", case=False, regex=True)]
print("PAYPAL *INFO rows:")
print(paypal_info[["Date", "Card", "Amount", "Description"]].to_string())
print()

# leonehmzow
leo = df[df["Description"].str.contains("leonehmzow", case=False)]
print("PAYPAL *leonehmzow rows:")
print(leo[["Date", "Card", "Amount", "Description"]].to_string())
print()

# Bank sheet reconciliation for June
print("=== BANK SHEET JUNE UPDATE ===")
print("Current row 17 values:")
print("  Salary In:        0.00 (unchanged - no payroll visible)")
print("  Other Income:  2475.00 -> new items:")
print("    + Gabriele Koch 485.30 (Jun 29, Anzug+Handtuecher)")
print("    + PayPal Europe  690.34 (Jun 30, incoming unknown)")
print("  Other Income new total: 3650.64")
print("  Card 1 (Amex):     0.00 -> 1901.40 (Jun 29 payment)")
print("  Card 2 (TF Bank): 1231.00 -> 1676.44 (+ Jun 18 payment 445.44)")
print("  Other Out:         99.80 -> 216.02 (+Netflix 19.99 +Telekom 34.95 +Spotify 12.99 +AXA 48.29)")
print("  Internal Transfer:  0.00 -> 1194.48 (David Koch net: +278.15 +915.85 +1800.48 -1800.00)")
print()
print("New Net Flow = 0 + 3650.64 + 1194.48 - 1901.40 - 1676.44 - 216.02 = 1051.26")
print("Estimated June-30 Ending Balance = 397.80 (May) + 1051.26 = 1449.06")
print("(matches truncated ABSCHLUSS note '1.449,..')")
print()
print("=== BANK SHEET JULY (NEW ROW) ===")
print("  Salary In:         ? (need David to confirm)")
print("  Other Income:     85.00 (Stefan 25 Jul 1 + PayPal incoming 60 Jul 13)")
print("  Rent Out:       1135.25 (Leo Nehmzow Jul 2)")
print("  Card 1 (Amex):     0.00 (no Amex payment to Haspa in Jul data)")
print("  Card 2 (TF Bank): 250.00 (Jul 6 payment)")
print("  Other Out:         0.00 (no further Haspa debits in Jul data)")
print("  Internal Transfer: 0.00")
print("  Ending Balance:    ? (need David to check Haspa app)")
print()
est_jun = 1449.06
net_flow_jul = 85 - 1135.25 - 250
est_jul = est_jun + net_flow_jul
print(f"  Estimated Jul-13 balance (if no salary) = {est_jun} + {net_flow_jul} = {est_jul:.2f}")
print()
print("=== INVESTMENTS_TR July snapshot ===")
print("  BYD (ADR)          103.1246 qty  @ 9.16 EUR = 944.62 EUR")
print("  Alibaba Group (ADR)  7.549298 qty @ 98.80 EUR = 745.87 EUR")
print("  Alphabet: 0 (sold)")
print()
print("=== INVESTMENTS_CRYPTO July snapshot ===")
print("  Solana (SOL)   1.42462 qty @ 65.62 EUR = 93.48 EUR")
