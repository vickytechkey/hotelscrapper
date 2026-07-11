#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

CONTAINER_NAME="scraper-app"
IMAGE_NAME="hotel-scraper-app"
PORT=8501

echo "============================================="
echo "Stopping & removing existing container if any..."
echo "============================================="
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

echo "============================================="
echo "Building the Docker image: $IMAGE_NAME..."
echo "============================================="
docker build -t $IMAGE_NAME .

echo "============================================="
echo "Running the container: $CONTAINER_NAME..."
echo "============================================="
# Ensure results folder exists locally to mount
mkdir -p results

docker run -d \
  -p $PORT:8501 \
  -v "$(pwd)/results:/app/results" \
  --name $CONTAINER_NAME \
  $IMAGE_NAME

echo "============================================="
echo "Success! The application is running."
echo "You can access the Streamlit UI at:"
echo "👉 http://localhost:$PORT"
echo "============================================="
