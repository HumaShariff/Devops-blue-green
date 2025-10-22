#!/bin/bash
set -e

# Start the container in detached mode
docker run -d -p 8199:8199 --name average-app-test average-app

# Give it a few seconds to start
sleep 3

# Run the smoke test
result=$(curl -s -X POST localhost:8199 -H "Content-Type: application/json" -d '{"numbers":[1,3,7,8]}')

# Stop and remove the container
docker stop average-app-test >/dev/null
docker rm average-app-test >/dev/null

# Check the result
if [ "$result" = "4" ]; then
  echo "Smoke test passed ✅"
else
  echo "Smoke test failed ❌ (Expected 4, got $result)"
  exit 1
fi

