#!/bin/bash
# Benchmark Candidate GCE Instance Types
#
# This script creates temporary VMs with different instance types,
# runs the encoding benchmark on each, and collects results.
#
# Usage:
#   ./scripts/benchmark_candidates.sh [candidate_number]
#
#   # Run specific candidate (1-5)
#   ./scripts/benchmark_candidates.sh 1
#
#   # Run all candidates
#   ./scripts/benchmark_candidates.sh all

set -e

PROJECT="nomadkaraoke"
ZONE="us-central1-a"
BENCHMARK_SCRIPT="benchmark_encoding_gce.sh"
RESULTS_DIR="benchmark_results"

# Candidate configurations
# Format: "name:machine_type"
CANDIDATES=(
    "c4d-highcpu-16:c4d-highcpu-16"
    "c4-highcpu-16:c4-highcpu-16"
    "c4-highcpu-32:c4-highcpu-32"
    "c3d-highcpu-30:c3d-highcpu-30"
    "c4a-highcpu-16:c4a-highcpu-16"
    "c4d-highcpu-32:c4d-highcpu-32"
)

# Create results directory
mkdir -p "$RESULTS_DIR"

# Function to create a benchmark VM
create_vm() {
    local name=$1
    local machine_type=$2
    local vm_name="benchmark-${name}"

    echo "Creating VM: $vm_name ($machine_type)..."

    # Determine disk type based on machine type
    # C4, C4D, C4A all require hyperdisk-balanced
    local disk_type="pd-balanced"
    if [[ "$machine_type" == c4* ]]; then
        disk_type="hyperdisk-balanced"
    fi

    # Check if ARM (c4a) - needs different image
    if [[ "$machine_type" == c4a* ]]; then
        # ARM-based instance needs ARM image
        gcloud compute instances create "$vm_name" \
            --project="$PROJECT" \
            --zone="$ZONE" \
            --machine-type="$machine_type" \
            --image-family="debian-12-arm64" \
            --image-project="debian-cloud" \
            --boot-disk-size="100GB" \
            --boot-disk-type="$disk_type" \
            --scopes="storage-ro" \
            --metadata="startup-script=apt-get update && apt-get install -y python3 wget && wget -q https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz -O /tmp/ffmpeg.tar.xz && tar -xf /tmp/ffmpeg.tar.xz -C /tmp && cp /tmp/ffmpeg-*-arm64-static/ffmpeg /usr/local/bin/ && cp /tmp/ffmpeg-*-arm64-static/ffprobe /usr/local/bin/"
    else
        # x86 instance
        gcloud compute instances create "$vm_name" \
            --project="$PROJECT" \
            --zone="$ZONE" \
            --machine-type="$machine_type" \
            --image-family="debian-12" \
            --image-project="debian-cloud" \
            --boot-disk-size="100GB" \
            --boot-disk-type="$disk_type" \
            --scopes="storage-ro" \
            --metadata="startup-script=apt-get update && apt-get install -y python3 wget && wget -q https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -O /tmp/ffmpeg.tar.xz && tar -xf /tmp/ffmpeg.tar.xz -C /tmp && cp /tmp/ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ && cp /tmp/ffmpeg-*-amd64-static/ffprobe /usr/local/bin/"
    fi

    echo "Waiting for VM to be ready..."
    sleep 30

    # Wait for FFmpeg to be installed
    local max_attempts=20
    local attempt=0
    while ! gcloud compute ssh "$vm_name" --zone="$ZONE" --project="$PROJECT" --command="which ffmpeg" &>/dev/null; do
        attempt=$((attempt + 1))
        if [ $attempt -ge $max_attempts ]; then
            echo "ERROR: FFmpeg not ready after $max_attempts attempts"
            return 1
        fi
        echo "  Waiting for FFmpeg installation... (attempt $attempt/$max_attempts)"
        sleep 15
    done

    echo "VM ready: $vm_name"
}

# Function to run benchmark on a VM
run_benchmark() {
    local name=$1
    local vm_name="benchmark-${name}"
    local result_file="$RESULTS_DIR/${name}_results.txt"

    echo ""
    echo "============================================================"
    echo "Running benchmark on: $vm_name"
    echo "============================================================"

    # Copy benchmark script to VM
    gcloud compute scp "scripts/$BENCHMARK_SCRIPT" "${vm_name}:/tmp/" \
        --zone="$ZONE" --project="$PROJECT"

    # Run benchmark and capture output
    gcloud compute ssh "$vm_name" --zone="$ZONE" --project="$PROJECT" \
        --command="bash /tmp/$BENCHMARK_SCRIPT" | tee "$result_file"

    echo ""
    echo "Results saved to: $result_file"
}

# Function to delete a VM
delete_vm() {
    local name=$1
    local vm_name="benchmark-${name}"

    echo "Deleting VM: $vm_name..."
    gcloud compute instances delete "$vm_name" \
        --zone="$ZONE" --project="$PROJECT" --quiet || true
}

# Function to run a single candidate
run_candidate() {
    local index=$1
    local candidate="${CANDIDATES[$index]}"
    local name="${candidate%%:*}"
    local machine_type="${candidate##*:}"

    echo ""
    echo "########################################################"
    echo "# Candidate $((index + 1)): $name ($machine_type)"
    echo "########################################################"

    # Create VM
    if ! create_vm "$name" "$machine_type"; then
        echo "ERROR: Failed to create VM for $name"
        return 1
    fi

    # Run benchmark
    if ! run_benchmark "$name"; then
        echo "ERROR: Benchmark failed for $name"
        delete_vm "$name"
        return 1
    fi

    # Delete VM
    delete_vm "$name"

    echo ""
    echo "Candidate $name completed successfully!"
}

# Function to parse results and create summary
create_summary() {
    echo ""
    echo "============================================================"
    echo "BENCHMARK SUMMARY"
    echo "============================================================"
    echo ""
    echo "Instance Type           | Total Time | vs Baseline | With Vocals | Concat | 720p"
    echo "------------------------|------------|-------------|-------------|--------|------"

    # Baseline (from existing encoding-worker)
    echo "c4-standard-8 (baseline)|    666.19s |       1.00x |     324.16s | 164.86s| 50.20s"

    # Parse each result file
    for candidate in "${CANDIDATES[@]}"; do
        local name="${candidate%%:*}"
        local result_file="$RESULTS_DIR/${name}_results.txt"

        if [ -f "$result_file" ]; then
            # Extract total time
            local total=$(grep "TOTAL" "$result_file" | awk '{print $NF}' | tr -d 's')
            # Extract individual stage times
            local with_vocals=$(grep "Stage 2:" "$result_file" | awk -F'|' '{print $2}' | tr -d 's ' 2>/dev/null || echo "-")
            local concat=$(grep "Stage 5:" "$result_file" | awk -F'|' '{print $2}' | tr -d 's ' 2>/dev/null || echo "-")
            local p720=$(grep "Stage 8:" "$result_file" | awk -F'|' '{print $2}' | tr -d 's ' 2>/dev/null || echo "-")

            if [ -n "$total" ]; then
                local ratio=$(python3 -c "print(f'{666.19 / float(\"$total\"):.2f}x')" 2>/dev/null || echo "-")
                printf "%-24s|%11ss |%12s |%12ss |%7ss|%6ss\n" "$name" "$total" "$ratio" "$with_vocals" "$concat" "$p720"
            else
                printf "%-24s|         -  |           - |           - |      - |     -\n" "$name"
            fi
        else
            printf "%-24s|         -  |           - |           - |      - |     - (no results)\n" "$name"
        fi
    done

    echo ""
    echo "Results saved to: $RESULTS_DIR/"
}

# Main
main() {
    local target="${1:-help}"

    case "$target" in
        1|2|3|4|5|6)
            run_candidate $((target - 1))
            ;;
        all)
            echo "Running all 5 candidates..."
            for i in {0..4}; do
                run_candidate $i
            done
            create_summary
            ;;
        summary)
            create_summary
            ;;
        help|*)
            echo "Usage: $0 [candidate_number|all|summary]"
            echo ""
            echo "Candidates:"
            for i in "${!CANDIDATES[@]}"; do
                local candidate="${CANDIDATES[$i]}"
                local name="${candidate%%:*}"
                local machine_type="${candidate##*:}"
                echo "  $((i + 1)): $name ($machine_type)"
            done
            echo ""
            echo "Commands:"
            echo "  1-5     Run specific candidate"
            echo "  all     Run all candidates sequentially"
            echo "  summary Show results summary"
            echo ""
            echo "Example:"
            echo "  $0 1        # Run c4d-highcpu-16"
            echo "  $0 all      # Run all candidates"
            ;;
    esac
}

main "$@"
