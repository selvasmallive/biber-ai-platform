#!/usr/bin/env bash
set -e

echo "=== Starting BIBER starter stack ==="

if [ ! -f .env ]; then
  echo ".env not found. Creating from .env.example"
  cp .env.example .env
fi

docker compose up -d --build

echo
echo "Services:"
docker compose ps

echo
echo "API docs should be available at:"
echo "http://localhost:8000/docs"
echo
echo "Adminer DB viewer:"
echo "http://localhost:8080"
