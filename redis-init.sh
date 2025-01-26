#!/bin/sh

# Start Redis server in the background
redis-server --save 20 1 --loglevel warning &

# Wait for Redis to be ready
until redis-cli ping; do
  echo "Waiting for Redis to be ready..."
  sleep 1
done

# Function to set nested JSON values recursively
set_json_values() {
    local json_string=$1

    json_string="${json_string#?}"
    json_string="${json_string%?}"
    json_string=$(echo "$json_string" | sed 's/"//g')
    
    IFS=','  # Use a comma as the delimiter

    for pair in $json_string; do
        # Extract key and value by splitting on the colon
        key=$(echo "$pair" | cut -d':' -f1 | sed 's/^ *//;s/ *$//')  # Trim spaces from key
        value=$(echo "$pair" | cut -d':' -f2 | sed 's/^ *//;s/ *$//')  # Trim spaces from value

        # Store the key-value pair in Redis
        redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" SET "$key" "$value"
        echo "Stored $key=$value in Redis"
    done
}

# Initialize Redis with default values from environment variable
if [ -n "$REDIS_DEFAULTS" ]; then
    echo "Initializing Redis with default values..."
    set_json_values "$REDIS_DEFAULTS"
fi

# Keep the container running with Redis in the foreground
wait