# Hello from Fabio

A minimal Flask 3 web app. It serves one page at `/` that says "Hello from Fabio".

## Install

Requires Python 3.9 or newer.

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Then open <http://127.0.0.1:5000/> in your browser. Press `Ctrl+C` to stop.

## Notes

- `app.py` runs with `debug=True` for local development. Turn it off before deploying.
- If port 5000 is taken, change the last line of `app.py` to `app.run(debug=True, port=5001)`.
# lowcode-project

What would you build if it took an evening instead of a quarter?

Cost of Living Comparator is a web application designed to help individuals, students, job seekers, and professionals compare living expenses across different cities and countries. Users can select two locations and instantly view side-by-side comparisons of key cost categories such as housing, transportation, groceries, utilities, dining, healthcare, and entertainment.

The platform provides clear visual insights into how far a salary can go in each location, helping users make informed decisions about relocation, travel, study, or career opportunities. By integrating real-world cost data and customizable spending profiles, users can estimate monthly budgets based on their lifestyle and financial goals.

Additional features include salary equivalence calculations, affordability scores, and personalized savings projections. Whether someone is planning an international move, evaluating a job offer, or simply exploring new destinations, the Cost of Living Comparator transforms complex financial information into an intuitive and actionable experience, enabling smarter decisions with confidence and transparency.
