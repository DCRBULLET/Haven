# 🌌 Haven

Haven turns a LocalMusic AI track into a long-form ambient YouTube video with generative visuals, a thumbnail, and a lightweight production-control loop.

## Open Haven

Double-click `Open Haven.command`. If Haven has not been set up yet, the launcher runs setup first and then opens Haven in your browser at `http://localhost:8501`.

## First-time setup

1. Install Python 3.10 or newer, then run `Open Haven.command`.
2. Get your LocalMusic AI API key.
3. In the Haven dashboard, open **Connect or replace key**, paste the key, and choose **Save key**.
4. Select **Create today’s plan**.
5. Review and approve the production brief.
6. Choose **Generate music**. Haven creates an instrumental LocalMusic AI track.
7. Choose **Build video**. Haven loops the track, renders the visuals, saves the video in `output/`, and runs render QA.
8. Review and approve the publication package before uploading.

Haven saves each production record locally in `.haven/records/`. It preserves the brief, asset hashes, basic render QA, AI-disclosure setting, publication status, and your performance observations.

`haven_config.json` is local working state and is intentionally ignored by version control. Use [haven_config.example.json](haven_config.example.json) as the safe starting template when setting up another machine.

Your API key is stored only in a private hidden file on your Mac and is never included in generated videos.

## Optional YouTube uploads

To upload, add a Google OAuth desktop-client file at `credentials/client_secret.json`, then run:

```bash
python3 haven_upload.py
```

The first run asks you to sign in to the YouTube channel you want to use. Uploads are private by default; use `--publish` only when you deliberately want an immediate public upload.

## Logs and recovery

Haven now writes an operational log to `.haven/logs/haven.log`. Use it first when a build or upload step fails.

If you run `python3 haven_pipeline.py --skip-visual` or `--skip-thumb`, Haven now requires the expected artifact to already exist on disk instead of failing later during render QA.

## Production records

Each plan is a local, reviewable production record. The dashboard requires a brief approval before music generation, validates the finished render before it becomes upload-ready, and lets you save performance observations for the next creative decision. Haven does not publish automatically.

See [the operating procedure](OPERATIONS.md) for the release checklist, data recovery, and the criteria for expanding automation.

## Folders

- `music/` — LocalMusic AI tracks
- `visuals/` — generated visual loops
- `output/` — completed videos
- `thumbs/` — generated thumbnails
