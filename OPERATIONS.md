# Haven operating procedure

## Production checklist

1. Open Haven and create a plan.
2. Check the audience, title, prompt, and metadata. Approve the brief only when it has a clear audience need and a differentiated creative angle.
3. Generate music, listen to the complete source track, then build the video.
4. Review the final video and thumbnail. Haven's render QA confirms the file structure and duration; it does not replace human listening or visual review.
5. Approve the publication package and upload privately. Check YouTube processing, copyright checks, title, thumbnail, audience setting, and AI disclosure in Studio.
6. Publish only after the private review. Record performance after 24 hours, 7 days, and 28 days.

## Release gate

Do not publish if any of these are true:

- Audio contains unwanted vocals, artifacts, abrupt loops, clipping, or long silence.
- The visual loop is distracting, broken, or too repetitive for the intended duration.
- The title and thumbnail make a claim the video does not deliver.
- The music provider's current commercial-use terms are not confirmed.
- YouTube has reported a copyright, processing, or policy issue.

## Data and recovery

- `haven_config.json` is the active plan. It is saved atomically.
- `.haven/records/` contains one auditable record for each production; back it up with the project folder.
- `.haven/logs/haven.log` contains the operational timeline for builds and failures.
- `music/`, `visuals/`, `output/`, and `thumbs/` contain generated assets and are intentionally not version-controlled.
- Never commit `.localmusic_api_key`, `credentials/client_secret.json`, or `credentials/token.pickle`.

## Troubleshooting

- If a pipeline run fails, check `.haven/logs/haven.log` first.
- If you use `--skip-visual`, confirm `visuals/loop_<date>.mp4` already exists.
- If you use `--skip-thumb`, confirm `thumbs/haven_<date>.jpg` already exists.
- If a record is marked `failed`, fix the underlying issue, then rerun from an approved or failed state; Haven will record the retry in the content history.

## Before expanding automation

Run at least 10 reviewed releases. Use the saved performance observations to identify which audience, creative direction, title pattern, and thumbnail pattern deserve further investment. Do not add autonomous public publishing until that evidence exists.
