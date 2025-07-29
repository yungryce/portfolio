#!/usr/bin/env bash

# Start timer
START_TIME=$(date +%s)

# Start orchestration for repo_context_orchestrator and get instanceId
START_RESPONSE=$(curl -s -X POST "http://localhost:7071/api/orchestrators/repo_context_orchestrator" \
  -H "Content-Type: application/json" \
  -d '{"username": "yungryce"}')
echo "Orchestration start response: $START_RESPONSE"

# Extract instanceId and statusQueryGetUri from response
INSTANCE_ID=$(echo "$START_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))")
STATUS_URL=$(echo "$START_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('statusQueryGetUri', ''))")

if [ -z "$INSTANCE_ID" ]; then
  echo "Failed to start orchestration or extract instanceId."
  echo "$START_RESPONSE"
  exit 1
fi

echo "Started orchestration. Instance ID: $INSTANCE_ID"

if [ -z "$STATUS_URL" ]; then
  echo "No statusQueryGetUri found in response, using default URL."
  STATUS_URL="http://localhost:7071/api/instances/$INSTANCE_ID"
fi

# Wait for orchestration to complete (poll status endpoint)
while true; do
  STATUS_RESPONSE=$(curl -s "$STATUS_URL")
  STATUS=$(echo "$STATUS_RESPONSE" | grep -oP '"runtimeStatus":"\K[^"]+')
  if [ "$STATUS" == "Completed" ]; then
    echo "Orchestration completed."
    break
  elif [ "$STATUS" == "Failed" ] || [ "$STATUS" == "Terminated" ]; then
    echo "Orchestration failed or terminated."
    echo "$STATUS_RESPONSE"
    exit 1
  else
    echo "Orchestration status: $STATUS. Waiting..."
    sleep 2
  fi
done

# End timer and print duration
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
echo "Orchestration duration: ${DURATION} seconds"

# Make request to portfolio_query with instance_id and statusQueryGetUri
curl -X POST "http://localhost:7071/api/ai" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"what are some of his devops projects?\", \"username\": \"yungryce\", \"instance_id\": \"$INSTANCE_ID\", \"status_query_url\": \"$STATUS_URL\"}"