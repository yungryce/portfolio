#!/usr/bin/env bash

# ./starter.sh
# ./starter.sh --query-type web
# ./starter.sh --custom "Show me projects that use Docker"
# ./starter.sh --force --verbose

# Define color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
USERNAME="yungryce"
FORCE_REFRESH=false
API_BASE="http://localhost:7071"
VERBOSE=false
QUERY_TYPE="devops"

# Sample queries for testing
QUERIES=(
  "what are some of his devops projects?"
  "Show me data structure projects"
  "What web development projects are in the portfolio?"
  "Find projects using Azure or AWS cloud services"
  "Tell me about Python projects that use machine learning"
)

# Function to print usage information
usage() {
  echo -e "${BLUE}Portfolio API Test Script${NC}"
  echo
  echo "Usage: ./starter.sh [options]"
  echo
  echo "Options:"
  echo "  -u, --username USERNAME    GitHub username (default: yungryce)"
  echo "  -f, --force                Force refresh orchestration even if cache exists"
  echo "  -q, --query-type TYPE      Query type to use (default: devops)"
  echo "                             Options: devops, data, web, cloud, ml"
  echo "  -c, --custom \"QUERY\"       Use a custom query string instead of presets"
  echo "  -v, --verbose              Enable verbose output"
  echo "  -h, --help                 Display this help message"
  echo
  echo "Example:"
  echo "  ./starter.sh --username yungryce --query-type web"
  exit 1
}

# Function to check if API is running
check_api() {
  if ! curl -s "$API_BASE/api/api-version" > /dev/null; then
    echo -e "${RED}Error: API is not running at $API_BASE${NC}"
    echo "Make sure you've started the API with 'func start'"
    exit 1
  fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -u|--username)
      USERNAME="$2"
      shift 2
      ;;
    -f|--force)
      FORCE_REFRESH=true
      shift
      ;;
    -q|--query-type)
      case $2 in
        devops) QUERY_TYPE="devops"; QUERY_INDEX=0 ;;
        data) QUERY_TYPE="data"; QUERY_INDEX=1 ;;
        web) QUERY_TYPE="web"; QUERY_INDEX=2 ;;
        cloud) QUERY_TYPE="cloud"; QUERY_INDEX=3 ;;
        ml) QUERY_TYPE="ml"; QUERY_INDEX=4 ;;
        *)
          echo -e "${RED}Invalid query type: $2${NC}"
          usage
          ;;
      esac
      shift 2
      ;;
    -c|--custom)
      CUSTOM_QUERY="$2"
      shift 2
      ;;
    -v|--verbose)
      VERBOSE=true
      shift
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      usage
      ;;
  esac
done

# Set the query based on selection or custom value
if [[ -n "$CUSTOM_QUERY" ]]; then
  QUERY="$CUSTOM_QUERY"
  echo -e "${BLUE}Using custom query:${NC} $QUERY"
else
  QUERY="${QUERIES[$QUERY_INDEX]}"
  echo -e "${BLUE}Using $QUERY_TYPE query:${NC} $QUERY"
fi

# Start timer for overall execution
OVERALL_START_TIME=$(date +%s)

# Prepare orchestration request payload
if $FORCE_REFRESH; then
  REQUEST_PAYLOAD="{\"username\": \"$USERNAME\", \"force_refresh\": true}"
  echo -e "${YELLOW}Forcing refresh of repository data${NC}"
else
  REQUEST_PAYLOAD="{\"username\": \"$USERNAME\"}"
fi

echo -e "${BLUE}Starting orchestration for user:${NC} $USERNAME"

# Start timer for orchestration
ORCH_START_TIME=$(date +%s)

# Request orchestration
echo -e "${BLUE}Requesting repo context...${NC}"
START_RESPONSE=$(curl -s -X POST "$API_BASE/api/orchestrator_start" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_PAYLOAD")

if $VERBOSE; then
  echo -e "${BLUE}Full orchestration response:${NC}"
  echo "$START_RESPONSE" | python3 -m json.tool
fi

# Check if response is valid JSON
if ! echo "$START_RESPONSE" | python3 -c "import sys, json; json.load(sys.stdin)" > /dev/null 2>&1; then
  echo -e "${RED}Error: Invalid JSON response${NC}"
  echo "$START_RESPONSE"
  exit 1
fi

# Check if response indicates cached data
CACHED_STATUS=$(echo "$START_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null)

if [ "$CACHED_STATUS" == "cached" ]; then
  echo -e "${GREEN}Cache exists, using cached repository data${NC}"
  
  # Extract cache info
  CACHE_KEY=$(echo "$START_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('cache_key', ''))" 2>/dev/null)
  REPOS_COUNT=$(echo "$START_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('repos_count', ''))" 2>/dev/null)
  echo -e "${BLUE}Cache key:${NC} $CACHE_KEY"
  echo -e "${BLUE}Repositories:${NC} $REPOS_COUNT"
  
  # End timer for cache retrieval
  ORCH_END_TIME=$(date +%s)
  ORCH_DURATION=$((ORCH_END_TIME - ORCH_START_TIME))
  echo -e "${GREEN}Cache retrieval completed in ${ORCH_DURATION} seconds${NC}"
  
  # Set request payload for AI query without instance_id
  AI_REQUEST_PAYLOAD="{\"query\": \"$QUERY\", \"username\": \"$USERNAME\"}"
else
  # If not cached, extract instanceId and statusQueryGetUri from response
  INSTANCE_ID=$(echo "$START_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))")
  STATUS_URL=$(echo "$START_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('statusQueryGetUri', ''))")

  if [ -z "$INSTANCE_ID" ]; then
    echo -e "${RED}Failed to start orchestration or extract instanceId${NC}"
    echo "$START_RESPONSE"
    exit 1
  fi

  echo -e "${GREEN}Started orchestration${NC}"
  echo -e "${BLUE}Instance ID:${NC} $INSTANCE_ID"

  if [ -z "$STATUS_URL" ]; then
    echo -e "${YELLOW}Warning: No statusQueryGetUri found, using default URL${NC}"
    STATUS_URL="$API_BASE/api/instances/$INSTANCE_ID"
  fi

  # Wait for orchestration to complete (poll status endpoint)
  echo -e "${BLUE}Waiting for orchestration to complete...${NC}"
  POLL_COUNT=0
  while true; do
    STATUS_RESPONSE=$(curl -s "$STATUS_URL")
    STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('runtimeStatus', ''))" 2>/dev/null)
    
    if [ "$STATUS" == "Completed" ]; then
      echo -e "${GREEN}Orchestration completed successfully${NC}"
      break
    elif [ "$STATUS" == "Failed" ] || [ "$STATUS" == "Terminated" ]; then
      echo -e "${RED}Orchestration $STATUS${NC}"
      if $VERBOSE; then
        echo "$STATUS_RESPONSE" | python3 -m json.tool
      else
        echo -e "${RED}Error details:${NC}"
        echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('output', ''))" 2>/dev/null
      fi
      exit 1
    else
      POLL_COUNT=$((POLL_COUNT + 1))
      echo -e "${BLUE}Status:${NC} $STATUS (poll #$POLL_COUNT)"
      sleep 2
    fi
  done

  # End timer for orchestration
  ORCH_END_TIME=$(date +%s)
  ORCH_DURATION=$((ORCH_END_TIME - ORCH_START_TIME))
  echo -e "${GREEN}Orchestration completed in ${ORCH_DURATION} seconds${NC}"

  # Set request payload for AI query with instance_id
  AI_REQUEST_PAYLOAD="{\"query\": \"$QUERY\", \"username\": \"$USERNAME\", \"instance_id\": \"$INSTANCE_ID\", \"status_query_url\": \"$STATUS_URL\"}"
fi

# Start timer for AI query
AI_START_TIME=$(date +%s)

# Make request to AI endpoint
echo -e "${BLUE}Sending query to AI endpoint:${NC} '$QUERY'"
AI_RESPONSE=$(curl -s -X POST "$API_BASE/api/ai" \
  -H "Content-Type: application/json" \
  -d "$AI_REQUEST_PAYLOAD")

# End timer for AI query
AI_END_TIME=$(date +%s)
AI_DURATION=$((AI_END_TIME - AI_START_TIME))

# Check if AI response is valid JSON
if ! echo "$AI_RESPONSE" | python3 -c "import sys, json; json.load(sys.stdin)" > /dev/null 2>&1; then
  echo -e "${RED}Error: Invalid JSON response from AI endpoint${NC}"
  echo "$AI_RESPONSE"
  exit 1
fi

# Extract and display AI response
AI_TEXT=$(echo "$AI_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('response', 'No response'))" 2>/dev/null)
REPOS_USED=$(echo "$AI_RESPONSE" | python3 -c "import sys, json; repos = json.load(sys.stdin).get('repositories_used', []); print(', '.join([r.get('name', 'Unknown') for r in repos]))" 2>/dev/null)

echo -e "${BLUE}Repositories used:${NC} $REPOS_USED"
echo -e "${BLUE}AI Response:${NC}"
echo -e "${GREEN}$AI_TEXT${NC}"
echo -e "${GREEN}AI query completed in ${AI_DURATION} seconds${NC}"

# Calculate and display total execution time
OVERALL_END_TIME=$(date +%s)
OVERALL_DURATION=$((OVERALL_END_TIME - OVERALL_START_TIME))
echo -e "${GREEN}Total execution time: ${OVERALL_DURATION} seconds${NC}"

# Write response to file for reference if verbose
if $VERBOSE; then
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  OUTPUT_FILE="ai_response_${TIMESTAMP}.json"
  echo "$AI_RESPONSE" > "$OUTPUT_FILE"
  echo -e "${BLUE}Full response saved to:${NC} $OUTPUT_FILE"
fi