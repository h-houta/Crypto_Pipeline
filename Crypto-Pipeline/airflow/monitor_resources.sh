#!/bin/bash

# Airflow Resource Monitoring Script
# This script monitors resource usage and alerts when thresholds are exceeded

echo "=== Airflow Resource Monitor ==="
echo "Timestamp: $(date)"
echo ""

# Check container status
echo "=== Container Status ==="
docker-compose -f docker-compose-airflow.yml ps

echo ""
echo "=== Resource Usage ==="
docker stats --no-stream | grep -E "(airflow|postgres|redis)" | awk '{printf "%-30s %8s %12s %8s\n", $2, $3, $4, $5}'

echo ""
echo "=== System Load ==="
uptime

echo ""
echo "=== Memory Usage ==="
vm_stat | grep -E "(Pages free|Pages active|Pages wired down|Pages purgeable)"

echo ""
echo "=== Port Status ==="
echo "Webserver (8081): $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/health 2>/dev/null || echo "DOWN")"
echo "Nginx (80): $(curl -s -o /dev/null -w "%{http_code}" http://localhost:80 2>/dev/null || echo "DOWN")"

echo ""
echo "=== Health Checks ==="
# Check if containers are responding
for container in airflow-webserver airflow-scheduler postgres-airflow redis; do
    if docker-compose -f docker-compose-airflow.yml ps $container | grep -q "Up"; then
        echo "✅ $container: UP"
    else
        echo "❌ $container: DOWN"
    fi
done

echo ""
echo "=== Recommendations ==="
# Check CPU usage
cpu_usage=$(docker stats --no-stream | grep airflow-scheduler | awk '{print $3}' | sed 's/%//')
if (( $(echo "$cpu_usage > 80" | bc -l) )); then
    echo "⚠️  High CPU usage detected: ${cpu_usage}%"
    echo "   Consider reducing DAG complexity or increasing CPU limits"
fi

# Check memory usage
mem_usage=$(docker stats --no-stream | grep airflow-webserver | awk '{print $4}' | sed 's/MiB//')
if (( $(echo "$mem_usage > 700" | bc -l) )); then
    echo "⚠️  High memory usage detected: ${mem_usage}MiB"
    echo "   Consider increasing memory limits or optimizing DAGs"
fi

echo ""
echo "=== End of Report ==="
