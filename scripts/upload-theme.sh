#!/bin/bash
# Upload a theme to GCS
# Usage: BRANDING_DIR=/path/to/NomadBranding ./upload-theme.sh [theme_id]

set -e

THEME_ID="${1:-nomad}"
BUCKET="karaoke-gen-storage-nomadkaraoke"
THEMES_PATH="themes"

# BRANDING_DIR must be set via environment variable
BRANDING_DIR="${BRANDING_DIR:-}"

if [ -z "$BRANDING_DIR" ]; then
    echo "Error: BRANDING_DIR environment variable must be set"
    echo "Example: export BRANDING_DIR=/path/to/NomadBranding"
    exit 1
fi

if [ ! -d "$BRANDING_DIR" ]; then
    echo "Error: BRANDING_DIR does not exist: $BRANDING_DIR"
    exit 1
fi

echo "=== Uploading theme: $THEME_ID to gs://$BUCKET/$THEMES_PATH/ ==="
echo "Using branding assets from: $BRANDING_DIR"

# Create temporary directory for processing
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# Function to upload the Nomad theme
upload_nomad_theme() {
    echo ""
    echo "=== Setting up Nomad theme ==="

    THEME_PATH="$THEMES_PATH/nomad"

    # Create style_params.json with GCS paths
    cat > "$TEMP_DIR/style_params.json" << 'EOF'
{
  "intro": {
    "video_duration": 5,
    "existing_image": null,
    "background_color": "#000000",
    "background_image": "karaoke-title-screen-background-nomad-4k.png",
    "font": "AvenirNext-Bold.ttf",
    "artist_color": "#ffdf6b",
    "artist_text_transform": "uppercase",
    "title_color": "#ffffff",
    "title_gradient": null,
    "title_text_transform": "uppercase",
    "title_region": "370,980,3100,350",
    "artist_region": "370,1400,3100,450",
    "artist_gradient": null,
    "extra_text": null,
    "extra_text_color": "#ffffff",
    "extra_text_gradient": null,
    "extra_text_region": null,
    "extra_text_text_transform": "uppercase"
  },
  "karaoke": {
    "background_image": "karaoke-background-image-nomad-4k.png",
    "background_color": "#000000",
    "font_path": "AvenirNext-Bold.ttf",
    "font": "Avenir Next Bold",
    "ass_name": "Nomad",
    "primary_color": "112, 112, 247, 255",
    "secondary_color": "255, 255, 255, 255",
    "outline_color": "26, 58, 235, 255",
    "back_color": "0, 255, 0, 255",
    "bold": false,
    "italic": false,
    "underline": false,
    "strike_out": false,
    "scale_x": 100,
    "scale_y": 100,
    "spacing": 0,
    "angle": 0.0,
    "border_style": 1,
    "outline": 1,
    "shadow": 0,
    "margin_l": 0,
    "margin_r": 0,
    "margin_v": 0,
    "encoding": 0
  },
  "end": {
    "video_duration": 5,
    "existing_image": null,
    "background_color": "#000000",
    "background_image": "karaoke-background-image-nomad-4k.png",
    "font": "AvenirNext-Bold.ttf",
    "artist_color": "#ffdf6b",
    "artist_text_transform": "uppercase",
    "title_color": "#ffffff",
    "title_gradient": null,
    "title_text_transform": "uppercase",
    "title_region": "370,900,3100,350",
    "artist_region": "370,1450,3100,200",
    "artist_gradient": null,
    "extra_text": "THANK YOU FOR SINGING!",
    "extra_text_color": "#ff7acc",
    "extra_text_region": "370,400,3100,400",
    "extra_text_text_transform": "uppercase",
    "extra_text_gradient": null
  },
  "cdg": {
    "clear_mode": "eager",
    "sync_offset": 0,
    "lead_in_threshold": 300,
    "lead_in_duration": 30,
    "lead_in_total": 200,
    "lead_in_symbols": ["/>", ">", ">", ">"],
    "row": 4,
    "line_tile_height": 3,
    "lines_per_page": 4,
    "title_color": "#ffffff",
    "artist_color": "#ffdf6b",
    "background_color": "#111427",
    "border_color": "#111427",
    "active_fill": "#7070F7",
    "active_stroke": "#000000",
    "inactive_fill": "#ff7acc",
    "inactive_stroke": "#000000",
    "instrumental_font_color": "#ffdf6b",
    "font_path": "AvenirNext-Bold.ttf",
    "font_size": 18,
    "stroke_width": 0,
    "stroke_style": "octagon",
    "instrumental_gap_threshold": 1500,
    "instrumental_text": "INSTRUMENTAL",
    "instrumental_background": "cdg-instrumental-background-nomad-notes.png",
    "instrumental_transition": "topleftmusicalnotes",
    "title_screen_background": "cdg-title-screen-background-nomad-simple.png",
    "title_screen_transition": "largecentertexttoplogo",
    "title_artist_gap": 10,
    "intro_duration_seconds": 5.0,
    "first_syllable_buffer_seconds": 3.0,
    "outro_background": "cdg-title-screen-background-nomad-simple.png",
    "outro_transition": "largecentertexttoplogo",
    "outro_text_line1": "THANK YOU FOR SINGING!",
    "outro_text_line2": "nomadkaraoke.com",
    "outro_line1_color": "#ffffff",
    "outro_line2_color": "#ffdf6b",
    "outro_line1_line2_gap": 30
  }
}
EOF

    echo "Uploading style_params.json..."
    gsutil cp "$TEMP_DIR/style_params.json" "gs://$BUCKET/$THEME_PATH/style_params.json"

    # Validate all required branding files exist before uploading
    echo "Validating required branding files..."
    REQUIRED_FILES=(
        "$BRANDING_DIR/youtube-video-description.txt"
        "$BRANDING_DIR/AvenirNext-Bold.ttf"
        "$BRANDING_DIR/karaoke-title-screen-background-nomad-4k.png"
        "$BRANDING_DIR/karaoke-background-image-nomad-4k.png"
        "$BRANDING_DIR/cdg-instrumental-background-nomad-notes.png"
        "$BRANDING_DIR/cdg-title-screen-background-nomad-simple.png"
    )

    for file in "${REQUIRED_FILES[@]}"; do
        if [ ! -f "$file" ]; then
            echo "Error: Required file not found: $file"
            exit 1
        fi
    done
    echo "All required files found."

    echo "Uploading youtube_description.txt..."
    gsutil cp "$BRANDING_DIR/youtube-video-description.txt" "gs://$BUCKET/$THEME_PATH/youtube_description.txt"

    echo "Uploading assets..."
    # Font
    gsutil cp "$BRANDING_DIR/AvenirNext-Bold.ttf" "gs://$BUCKET/$THEME_PATH/assets/AvenirNext-Bold.ttf"

    # Background images
    gsutil cp "$BRANDING_DIR/karaoke-title-screen-background-nomad-4k.png" "gs://$BUCKET/$THEME_PATH/assets/karaoke-title-screen-background-nomad-4k.png"
    gsutil cp "$BRANDING_DIR/karaoke-background-image-nomad-4k.png" "gs://$BUCKET/$THEME_PATH/assets/karaoke-background-image-nomad-4k.png"

    # CDG assets
    gsutil cp "$BRANDING_DIR/cdg-instrumental-background-nomad-notes.png" "gs://$BUCKET/$THEME_PATH/assets/cdg-instrumental-background-nomad-notes.png"
    gsutil cp "$BRANDING_DIR/cdg-title-screen-background-nomad-simple.png" "gs://$BUCKET/$THEME_PATH/assets/cdg-title-screen-background-nomad-simple.png"

    # Create preview image (use an existing image as preview for now)
    echo "Uploading preview image..."
    gsutil cp "$BRANDING_DIR/karaoke-background-image-nomad-4k.png" "gs://$BUCKET/$THEME_PATH/preview.png"

    echo "Nomad theme uploaded successfully!"
}

# Function to upload the default theme (simple black background)
upload_default_theme() {
    echo ""
    echo "=== Setting up Default theme ==="

    THEME_PATH="$THEMES_PATH/default"

    # Create a simple default style_params.json (no custom assets)
    cat > "$TEMP_DIR/default_style_params.json" << 'EOF'
{
  "intro": {
    "video_duration": 5,
    "existing_image": null,
    "background_color": "#000000",
    "background_image": null,
    "font": null,
    "artist_color": "#ffffff",
    "artist_text_transform": "uppercase",
    "title_color": "#ffffff",
    "title_gradient": null,
    "title_text_transform": "uppercase",
    "title_region": "370,980,3100,350",
    "artist_region": "370,1400,3100,450"
  },
  "karaoke": {
    "background_image": null,
    "background_color": "#000000",
    "font_path": null,
    "font": null,
    "ass_name": "Default",
    "primary_color": "0, 255, 0, 255",
    "secondary_color": "255, 255, 255, 255",
    "outline_color": "0, 0, 0, 255",
    "back_color": "0, 0, 0, 255",
    "bold": false,
    "italic": false,
    "underline": false,
    "strike_out": false,
    "scale_x": 100,
    "scale_y": 100,
    "spacing": 0,
    "angle": 0.0,
    "border_style": 1,
    "outline": 2,
    "shadow": 0,
    "margin_l": 0,
    "margin_r": 0,
    "margin_v": 0,
    "encoding": 0
  },
  "end": {
    "video_duration": 5,
    "existing_image": null,
    "background_color": "#000000",
    "background_image": null,
    "font": null,
    "artist_color": "#ffffff",
    "artist_text_transform": "uppercase",
    "title_color": "#ffffff",
    "title_gradient": null,
    "title_text_transform": "uppercase",
    "title_region": "370,900,3100,350",
    "artist_region": "370,1450,3100,200",
    "extra_text": null
  },
  "cdg": {
    "clear_mode": "eager",
    "sync_offset": 0,
    "lead_in_threshold": 300,
    "lead_in_duration": 30,
    "lead_in_total": 200,
    "lead_in_symbols": ["/>", ">", ">", ">"],
    "row": 4,
    "line_tile_height": 3,
    "lines_per_page": 4,
    "title_color": "#ffffff",
    "artist_color": "#ffffff",
    "background_color": "#000000",
    "border_color": "#000000",
    "active_fill": "#00ff00",
    "active_stroke": "#000000",
    "inactive_fill": "#ffffff",
    "inactive_stroke": "#000000",
    "instrumental_font_color": "#ffff00",
    "font_path": null,
    "font_size": 18,
    "stroke_width": 1,
    "stroke_style": "octagon",
    "instrumental_gap_threshold": 1500,
    "instrumental_text": "INSTRUMENTAL",
    "instrumental_background": null,
    "instrumental_transition": "default",
    "title_screen_background": null,
    "title_screen_transition": "default",
    "title_artist_gap": 10,
    "intro_duration_seconds": 5.0,
    "first_syllable_buffer_seconds": 3.0,
    "outro_background": null,
    "outro_transition": "default",
    "outro_text_line1": "THANK YOU FOR SINGING!",
    "outro_text_line2": "",
    "outro_line1_color": "#ffffff",
    "outro_line2_color": "#ffffff",
    "outro_line1_line2_gap": 30
  }
}
EOF

    echo "Uploading default style_params.json..."
    gsutil cp "$TEMP_DIR/default_style_params.json" "gs://$BUCKET/$THEME_PATH/style_params.json"

    echo "Default theme uploaded successfully!"
}

# Function to create/update the theme metadata
create_metadata() {
    echo ""
    echo "=== Creating theme metadata ==="

    cat > "$TEMP_DIR/_metadata.json" << 'EOF'
{
  "version": 1,
  "themes": [
    {
      "id": "nomad",
      "name": "Nomad Karaoke",
      "description": "Professional karaoke style with golden artist text, purple sung lyrics, and beautiful backgrounds",
      "is_default": true
    },
    {
      "id": "default",
      "name": "Classic",
      "description": "Simple black background with white text and green highlighted lyrics",
      "is_default": false
    }
  ]
}
EOF

    echo "Uploading _metadata.json..."
    gsutil cp "$TEMP_DIR/_metadata.json" "gs://$BUCKET/$THEMES_PATH/_metadata.json"

    echo "Metadata created successfully!"
}

# Main execution
case "$THEME_ID" in
    "nomad")
        upload_nomad_theme
        create_metadata
        ;;
    "default")
        upload_default_theme
        create_metadata
        ;;
    "all")
        upload_nomad_theme
        upload_default_theme
        create_metadata
        ;;
    "metadata")
        create_metadata
        ;;
    *)
        echo "Unknown theme: $THEME_ID"
        echo "Usage: $0 [nomad|default|all|metadata]"
        exit 1
        ;;
esac

echo ""
echo "=== Theme upload complete! ==="
echo "Verify with: gsutil ls -r gs://$BUCKET/$THEMES_PATH/"
