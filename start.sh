#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

CONTAINER_NAME="scraper-app"
PORT=8501

echo "============================================="
echo "Starting the Docker container: $CONTAINER_NAME..."
echo "============================================="

# Check if the container is already running
if [ "$(docker inspect -f '{{.State.Running}}' $CONTAINER_NAME 2>/dev/null)" = "true" ]; then
    echo "The container '$CONTAINER_NAME' is already running!"
else
    # Check if the container exists (stopped)
    if [ "$(docker ps -a -q -f name=^/${CONTAINER_NAME}$)" ]; then
        echo "Starting stopped container '$CONTAINER_NAME'..."
        docker start $CONTAINER_NAME
    else
        echo "Container '$CONTAINER_NAME' does not exist."
        echo "Please run './build.sh' first to build and initialize the container."
        exit 1
    fi
fi

echo "============================================="
echo "Success! The application is running."
echo "You can access the Streamlit UI at:"
echo "👉 http://localhost:$PORT"
echo "============================================="
