name: Update Dashboard

on:
  schedule:
    - cron: '0 7 * * *'
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Generate dashboard
        env:
          DATA_SOURCE:          databricks
          DATABRICKS_HOST:      ${{ secrets.DATABRICKS_HOST }}
          DATABRICKS_TOKEN:     ${{ secrets.DATABRICKS_TOKEN }}
          DATABRICKS_HTTP_PATH: ${{ secrets.DATABRICKS_HTTP_PATH }}
          OUTPUT_PATH:          dist/bolt_dashboard.html
        run: |
          mkdir -p dist
          python gen_dashboard.py

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token:   ${{ secrets.GITHUB_TOKEN }}
          publish_branch: gh-pages
          publish_dir:    dist
          commit_message: "chore: daily dashboard update [skip ci]"
