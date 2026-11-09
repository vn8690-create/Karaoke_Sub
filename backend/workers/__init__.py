"""
Background workers for long-running karaoke generation tasks.

Workers are triggered asynchronously to handle processing stages that
take several minutes or longer. Each worker:
- Updates job state and progress
- Stores intermediate files in GCS
- Handles errors gracefully
- Coordinates with other workers via job state
"""

