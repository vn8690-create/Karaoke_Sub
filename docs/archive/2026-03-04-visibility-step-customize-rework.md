# Visibility Step & Customize Rework

**Date:** 2026-03-04
**Branch:** feat/sess-20260304-1700-visibility-step-customize

## Overview

Rework the guided job creation flow to add a separate "Visibility" step before "Customize & Create", dedicated to deciding whether the created video should be published or private. Then rework the "Customize & Create" step based on the chosen visibility.

## New "Visibility" Step

On this step, we simply let the user choose between public or private, but we use it as an opportunity to ensure the user definitely understands what will happen.

### Published (Public)

Explain that "published" means:

- The resulting karaoke video will be automatically uploaded to the Nomad Karaoke YouTube channel (with a link to https://www.youtube.com/@nomadkaraoke/videos for them to check that out)
- It will also be uploaded to a Google Drive which is shared with various karaoke venues, meaning the song will be available to sing at a variety of karaoke bars/venues around the world
- The user will get all the source files and highest quality output formats via a Dropbox folder link too, which they can download for their safekeeping
- We should encourage the user to choose this option as it's the most convenient way to make their song available to sing (via YouTube) and they'll be helping out other fans of the same song, bringing joy to people all over the world who love that song

### Private

Explain that "private" means:

- The resulting karaoke video will NOT be uploaded to YouTube or Google Drive, and will only be provided via a Dropbox folder / via this site, for the user to download and use however they see fit
- If the user wants to perform the track at a venue, they'll be responsible for providing the files to the host at that venue
- If the user wants to upload the video to their own YouTube channel they can do so, but they likely won't be able to monetise it (the song licenses/copyrights are still owned by record labels in most cases)
- If the user wants to customise the video styles (e.g. background image, colors), they can do this if they choose private delivery

## Reworked "Customize & Create" Step

Once we have the new "Visibility" step in the flow, we also need to rework the "Customize & Create" flow:

### Remove Private Checkbox

The "private" checkbox on the current Customize & Create step is replaced by the new Visibility step.

### Conditional Options Based on Visibility

Since we'll now know already whether the video is private or public, we can show only the options which are allowed:

- **For public videos**: Only the title card artist/title should be customisable
- **For private videos**: Allow customising almost anything

### Side-by-Side Preview Canvases

Show the two preview canvases (title screen, main karaoke) side by side in this part of the flow, not below each other, so the user doesn't need to scroll down.

### Remove Redundant Thumbnails

Uploaded images for custom backgrounds don't need thumbnails - that's redundant since they're shown on the preview canvas(es).

### Improved Karaoke Preview Canvas

The text in the karaoke preview canvas needs to be centered in the thumbnail and show 4 lines so it's more similar to how the actual karaoke videos get rendered (see reference screenshot of actual video output).

### New Style Customisation Options

There should be a way to change more aspects of the styles:

- Change the text color and/or highlight color of the karaoke lyrics
- Use a solid color background (rather than an image) for either the title screen or karaoke video (or both with different colors)
- Add a few preset color buttons for both of these, including one which is the "green screen" color

## Reference Screenshots

- Current "Customize & Create" UI: see attached screenshot showing the existing layout with private checkbox, stacked canvases, and current style options
- Actual karaoke video output: see attached screenshot showing how lyrics appear in real videos (4 centered lines with highlight color)
