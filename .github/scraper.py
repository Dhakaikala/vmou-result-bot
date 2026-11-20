name: VMOU Notices & Regional Updates Bot

on:
  schedule:
    - cron: '*/30 * * * *'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  run-vmou-bot:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Dependencies
        run: |
          pip install requests beautifulsoup4

      - name: Run VMOU Notice Bot
        env:
          BOT_TOKEN: ${{ secrets.BOT_TOKEN }}
        run: |
          python scraper.py

      - name: Save Seen VMOU Notices State
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "Update last_seen.json [skip ci]"
          branch: main
