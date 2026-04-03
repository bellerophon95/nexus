import os

from backend.ingestion.pipeline import run_ingestion_pipeline

# Create a dummy test file
test_file = "tmp/test_ingestion.txt"
os.makedirs("tmp", exist_ok=True)
# Ensure the test file exists if not already present
if not os.path.exists(test_file):
    with open(test_file, "w") as f:
        f.write("Initial test content for Nexus.")

print(f"Running pipeline for {test_file}...")
try:
    result = run_ingestion_pipeline(test_file, title="Test AI Doc")
    print("Pipeline Result:")
    print(result)
except Exception as e:
    print(f"Pipeline failed with error: {e}")
