# Personal Dashboard

Personal Dashboard is a single-page Flask app that gathers the five things you check every day into one place, so you can stop hopping between tabs. Open it in the morning and you get the current weather for your location, headlines from a handful of RSS feeds you choose, and the status of a project you are tracking, such as the latest build result, open issues, or the most recent commit. Each section sits in its own card on one clean page, and everything refreshes when you reload it, with no accounts, database, or build step to maintain. The server fetches each source when the page loads, so what you see is always current, and a failing source never takes down the rest of the page. Sources and settings live in one small configuration file, which makes it easy to swap a feed, change your city, or add a new card of your own.

## What's on the page

| Card | Source | Needs a key? |
| --- | --- | --- |
| Weather | [Open-Meteo](https://open-meteo.com/) | No |
| Headlines | RSS feeds of your choice | No |
| Reading list | A second set of RSS feeds | No |
| Project status | GitHub API (public repos) | No |
| Quick links | Your own list | No |

## Requirements

- Python 3.10 or newer
- `git` and `pip`

## Install

```bash
# 1. Get the code
git clone https://github.com/your-username/personal-dashboard.git
cd personal-dashboard

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

`requirements.txt` contains `Flask`, `requests`, and `feedparser`.

## Configure

Open `config.py` and set the things that are yours:

```python
LOCATION = {"name": "Dublin", "lat": 53.35, "lon": -6.26}

FEEDS = [
    "https://example.com/feed.xml",
    "https://another-site.com/rss",
]

PROJECT = {"repo": "owner/repo"}   # GitHub repository to track

LINKS = [
    ("Calendar", "https://calendar.google.com"),
    ("Mail", "https://mail.google.com"),
]
```

## Run

```bash
flask --app app run
```

Then open <http://127.0.0.1:5000> in your browser.

For development with auto-reload and the debugger:

```bash
flask --app app run --debug
```

To make it reachable from other devices on your network, add `--host 0.0.0.0`.

## Project layout

```
personal-dashboard/
├── app.py              # Flask app and data fetching
├── config.py           # Your location, feeds, project, and links
├── requirements.txt
└── templates/
    └── index.html      # The single dashboard page
```

## Adding a card

1. Write a small function in `app.py` that returns the data for your card.
2. Pass its result to the template in the `index` route.
3. Add a matching `<section class="card">` block to `templates/index.html`.

## License

MIT
