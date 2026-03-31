#!/bin/bash
IMAGE_NAME="nexus-backend-local"

echo "🔍 Starting Container Audit for: $IMAGE_NAME"

# 1. Check for shared libraries
echo "--- Checking Shared Libraries ---"
docker run --rm $IMAGE_NAME find /usr/lib -name "libgthread-2.0.so.0" | grep "libgthread"
if [ $? -eq 0 ]; then
    echo "✅ libgthread-2.0.so.0 found."
else
    echo "❌ libgthread-2.0.so.0 MISSING."
    exit 1
fi

# 2. Check for X11/Xrender (often needed by poppler/opencv)
docker run --rm $IMAGE_NAME find /usr/lib -name "libXrender.so.1" | grep "libXrender"
if [ $? -eq 0 ]; then
    echo "✅ libXrender.so.1 found."
else
    echo "❌ libXrender.so.1 MISSING."
    exit 1
fi

# 3. Test Runtime Import for PDF Partitioning
echo "--- Testing Python Runtime Imports ---"
docker run --rm $IMAGE_NAME python3 -c "import unstructured.partition.pdf; print('✅ Successfully imported unstructured.partition.pdf')"
if [ $? -ne 0 ]; then
    echo "❌ Python import failed. Linkage issue likely."
    exit 1
fi

echo "🚀 ALL AUDITS PASSED. Image is safe for AWS deployment."
