from flask import Flask

app = Flask(__name__)


@app.route("/")
def index():
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Hello from Fabio</title>
  </head>
  <body>
    <h1>Hello from Fabio</h1>
  </body>
</html>"""


@app.route("/about")
def about():
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>About - Cost of Living Comparator</title>
  </head>
  <body>
    <h1>About</h1>
    <p>Cost of Living Comparator is a web application designed to help individuals, students, job seekers, and professionals compare living expenses across different cities and countries. Users can select two locations and instantly view side-by-side comparisons of key cost categories such as housing, transportation, groceries, utilities, dining, healthcare, and entertainment.</p>
    <p>The platform provides clear visual insights into how far a salary can go in each location, helping users make informed decisions about relocation, travel, study, or career opportunities. By integrating real-world cost data and customizable spending profiles, users can estimate monthly budgets based on their lifestyle and financial goals.</p>
    <p>Additional features include salary equivalence calculations, affordability scores, and personalized savings projections. Whether someone is planning an international move, evaluating a job offer, or simply exploring new destinations, the Cost of Living Comparator transforms complex financial information into an intuitive and actionable experience, enabling smarter decisions with confidence and transparency.</p>
  </body>
</html>"""


if __name__ == "__main__":
    app.run(debug=True)
