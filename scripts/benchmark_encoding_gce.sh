#!/bin/bash
# GCE Encoding Benchmark Script
# Run on the encoding-worker VM to benchmark FFmpeg encoding performance
#
# Usage:
#   gcloud compute scp scripts/benchmark_encoding_gce.sh encoding-worker:/tmp/ --zone=us-central1-a --project=nomadkaraoke
#   gcloud compute ssh encoding-worker --zone=us-central1-a --project=nomadkaraoke --command="bash /tmp/benchmark_encoding_gce.sh"

set -e

echo "============================================================"
echo "GCE Encoding Performance Benchmark"
echo "============================================================"

# System info
echo ""
echo "System Information:"
echo "  Hostname:     $(hostname)"
echo "  Platform:     $(uname -s) $(uname -r)"
echo "  CPU:          $(grep 'model name' /proc/cpuinfo | head -1 | cut -d: -f2 | xargs)"
echo "  CPU Count:    $(nproc)"
echo "  Memory:       $(free -h | grep Mem | awk '{print $2}')"
echo "  FFmpeg:       $(ffmpeg -version 2>&1 | head -1)"

# Setup directories
BENCHMARK_DIR="/tmp/benchmark_data"
OUTPUT_DIR="/tmp/benchmark_output"
GCS_BUCKET="karaoke-gen-storage-nomadkaraoke"
TEST_JOB_ID="fddad04d"

mkdir -p "$BENCHMARK_DIR" "$OUTPUT_DIR"
rm -rf "$OUTPUT_DIR"/*

# Download test files
echo ""
echo "============================================================"
echo "Downloading test files from GCS..."
echo "============================================================"

download_if_missing() {
    local gcs_path=$1
    local local_path=$2
    if [ -f "$local_path" ]; then
        echo "  [cached] $(basename $local_path)"
    else
        echo "  Downloading $(basename $local_path)..."
        gsutil -q cp "$gcs_path" "$local_path"
    fi
}

download_if_missing "gs://$GCS_BUCKET/jobs/$TEST_JOB_ID/lyrics/karaoke.ass" "$BENCHMARK_DIR/karaoke.ass"
download_if_missing "gs://$GCS_BUCKET/jobs/$TEST_JOB_ID/screens/title.mov" "$BENCHMARK_DIR/title.mov"
download_if_missing "gs://$GCS_BUCKET/jobs/$TEST_JOB_ID/screens/end.mov" "$BENCHMARK_DIR/end.mov"
download_if_missing "gs://$GCS_BUCKET/jobs/$TEST_JOB_ID/stems/instrumental_clean.flac" "$BENCHMARK_DIR/instrumental_clean.flac"
download_if_missing "gs://$GCS_BUCKET/jobs/$TEST_JOB_ID/stems/vocals_clean.flac" "$BENCHMARK_DIR/vocals.flac"
download_if_missing "gs://$GCS_BUCKET/themes/nomad/assets/karaoke-background-image-nomad-4k.png" "$BENCHMARK_DIR/background.png"
download_if_missing "gs://$GCS_BUCKET/themes/nomad/assets/AvenirNext-Bold.ttf" "$BENCHMARK_DIR/font.ttf"

echo "  All files downloaded successfully."

# Time a command and report results (using python3 for math since bc not available)
benchmark() {
    local name=$1
    shift
    echo ""
    echo "  Running: $name"
    local start=$(date +%s%N)

    if "$@" > /dev/null 2>&1; then
        local end=$(date +%s%N)
        local duration=$(python3 -c "print(f'{($end - $start) / 1000000000:.2f}')")
        local output_file=$(echo "$@" | grep -oP '(?<= )[^ ]+$' || echo "")
        local size="0"
        if [ -f "$output_file" ]; then
            local bytes=$(stat -c%s "$output_file" 2>/dev/null || echo "0")
            size=$(python3 -c "print(f'{$bytes / 1048576:.1f}')")
        fi
        echo "    Duration: ${duration}s, Output: ${size}MB - OK"
        echo "$name|$duration|$size|OK" >> "$OUTPUT_DIR/results.txt"
    else
        local end=$(date +%s%N)
        local duration=$(python3 -c "print(f'{($end - $start) / 1000000000:.2f}')")
        echo "    Duration: ${duration}s - FAILED"
        echo "$name|$duration|0|FAILED" >> "$OUTPUT_DIR/results.txt"
    fi
}

echo ""
echo "============================================================"
echo "Running Encoding Benchmarks"
echo "============================================================"

# Stage 1: Preview Video (480x270 with ASS overlay)
# Matches LocalPreviewEncodingService settings
benchmark "Stage 1: Preview Video (480x270 ASS)" \
    ffmpeg -y -hide_banner -loglevel error -r 24 \
    -loop 1 -i "$BENCHMARK_DIR/background.png" \
    -i "$BENCHMARK_DIR/vocals.flac" \
    -vf "scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2,ass=$BENCHMARK_DIR/karaoke.ass" \
    -c:a aac -b:a 96k \
    -c:v libx264 -preset superfast -crf 28 \
    -pix_fmt yuv420p -movflags +faststart -threads 0 -shortest \
    "$OUTPUT_DIR/preview.mp4"

# Stage 2: With Vocals Video (4K with ASS overlay)
# This is the HEAVIEST operation - matches VideoGenerator._build_ffmpeg_command
benchmark "Stage 2: With Vocals Video (4K ASS) - HEAVIEST" \
    ffmpeg -y -hide_banner -loglevel error -r 30 \
    -loop 1 -i "$BENCHMARK_DIR/background.png" \
    -i "$BENCHMARK_DIR/vocals.flac" \
    -c:a flac \
    -vf "scale=3840:2160:force_original_aspect_ratio=decrease,pad=3840:2160:(ow-iw)/2:(oh-ih)/2,ass=$BENCHMARK_DIR/karaoke.ass" \
    -c:v libx264 -preset fast -b:v 5000k -minrate 5000k -maxrate 20000k -bufsize 10000k \
    -shortest \
    "$OUTPUT_DIR/with_vocals.mkv"

# Stage 3: Remux with Instrumental
# Matches LocalEncodingService.remux_with_instrumental
benchmark "Stage 3: Remux with Instrumental" \
    ffmpeg -y -hide_banner -loglevel error \
    -i "$OUTPUT_DIR/with_vocals.mkv" \
    -i "$BENCHMARK_DIR/instrumental_clean.flac" \
    -map 0:v -map 1:a -c copy \
    -movflags +faststart \
    "$OUTPUT_DIR/karaoke.mp4"

# Stage 4a: Convert Title MOV to MP4
# Matches LocalEncodingService.convert_mov_to_mp4
benchmark "Stage 4a: Convert Title MOV to MP4" \
    ffmpeg -y -hide_banner -loglevel error \
    -i "$BENCHMARK_DIR/title.mov" \
    -c:v libx264 -c:a copy -movflags +faststart \
    "$OUTPUT_DIR/title.mp4"

# Stage 4b: Convert End MOV to MP4
benchmark "Stage 4b: Convert End MOV to MP4" \
    ffmpeg -y -hide_banner -loglevel error \
    -i "$BENCHMARK_DIR/end.mov" \
    -c:v libx264 -c:a copy -movflags +faststart \
    "$OUTPUT_DIR/end.mp4"

# Stage 5: Lossless 4K Concat
# Matches LocalEncodingService.encode_lossless_mp4
benchmark "Stage 5: Lossless 4K Concat (title+karaoke+end)" \
    ffmpeg -y -hide_banner -loglevel error \
    -i "$OUTPUT_DIR/title.mp4" \
    -i "$OUTPUT_DIR/karaoke.mp4" \
    -i "$OUTPUT_DIR/end.mp4" \
    -filter_complex "[0:v:0][0:a:0][1:v:0][1:a:0][2:v:0][2:a:0]concat=n=3:v=1:a=1[outv][outa]" \
    -map "[outv]" -map "[outa]" \
    -c:v libx264 -c:a pcm_s16le \
    -movflags +faststart \
    "$OUTPUT_DIR/final_lossless_4k.mp4"

# Stage 6: Lossy 4K
# Matches LocalEncodingService.encode_lossy_mp4
benchmark "Stage 6: Lossy 4K (AAC audio)" \
    ffmpeg -y -hide_banner -loglevel error \
    -i "$OUTPUT_DIR/final_lossless_4k.mp4" \
    -c:v copy -c:a aac -ar 48000 -b:a 320k \
    -movflags +faststart \
    "$OUTPUT_DIR/final_lossy_4k.mp4"

# Stage 7: MKV with FLAC
# Matches LocalEncodingService.encode_lossless_mkv
benchmark "Stage 7: MKV (FLAC audio)" \
    ffmpeg -y -hide_banner -loglevel error \
    -i "$OUTPUT_DIR/final_lossless_4k.mp4" \
    -c:v copy -c:a flac \
    "$OUTPUT_DIR/final_lossless_4k.mkv"

# Stage 8: 720p Downscale
# Matches LocalEncodingService.encode_720p
benchmark "Stage 8: 720p Downscale" \
    ffmpeg -y -hide_banner -loglevel error \
    -i "$OUTPUT_DIR/final_lossless_4k.mp4" \
    -c:v libx264 -vf "scale=1280:720" -b:v 2000k -preset medium -tune animation \
    -c:a aac -ar 48000 -b:a 128k \
    -movflags +faststart \
    "$OUTPUT_DIR/final_lossy_720p.mp4"

# Print results
echo ""
echo "============================================================"
echo "BENCHMARK RESULTS"
echo "============================================================"
echo ""
echo "Operation                                          Duration    Size    Status"
echo "---------------------------------------------------------------------------------"

total_time="0"
while IFS='|' read -r name duration size status; do
    printf "%-50s %8ss %8sMB %s\n" "$name" "$duration" "$size" "$status"
    if [ "$status" = "OK" ]; then
        total_time=$(python3 -c "print(f'{float(\"$total_time\") + float(\"$duration\"):.2f}')")
    fi
done < "$OUTPUT_DIR/results.txt"

echo "---------------------------------------------------------------------------------"
printf "%-50s %8ss\n" "TOTAL (successful operations)" "$total_time"

echo ""
echo "Results saved to: $OUTPUT_DIR/results.txt"
