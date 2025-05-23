import os
import json

output_file = os.environ.get("GITHUB_STEP_SUMMARY")
if not output_file:
    print("GITHUB_STEP_SUMMARY not set, not writing summary")

with open("coverage.json", mode="r", encoding="utf-8") as f:
    data = json.load(f)
    coverage = data["totals"]["percent_covered_display"]

content = "### Backend coverage \n" f"{coverage}% covered :eyeglasses:\n"

with open(output_file, mode="a", encoding="utf-8") as f:
    print(content, file=f)
