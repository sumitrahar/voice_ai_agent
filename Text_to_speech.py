from resemble import Resemble
import json

Resemble.api_key('3LrqS69lQqcI2cmWGwQ6oAtt')

# Get your default Resemble project.
project_uuid = Resemble.v2.projects.all(1, 10)['items'][0]['uuid']

# Get your Voice uuid (first in the list).
voice_uuid = Resemble.v2.voices.all(1, 10)['items'][0]['uuid']

# Create the clip
body = "This is a test"
clip_response = Resemble.v2.clips.create_sync(
    project_uuid,
    voice_uuid,
    body,
    title=None,
    sample_rate=None,
    output_format=None,
    precision=None,
    include_timestamps=None,
    is_archived=None,
    raw=None
)

# 1) Print the entire response to see its structure:
print(json.dumps(clip_response, indent=2))

# 2) Or at least print its top‐level keys:
print("Top‐level keys:", clip_response.keys())
