import json
from pathlib import Path
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
DATA = Path(__file__).parent / "data"


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


GOALS = {"internship": "land an internship", "job": "get a full-time job",
         "explore": "explore career paths", "grad": "prepare for grad school"}


def recommend(a):
    """Prototype matcher: simple rules. Replace this one function with the
    RAG pipeline later; the front end only needs the same JSON shape back."""
    comfort, challenges = a.get("comfort", {}), a.get("challenges", [])
    ranked = []
    for r in load("resources.json"):  # ties keep file order (networking first)
        score = 2 * any(c in challenges for c in r["helps_with"])
        score += a.get("goal") in r["goals"]
        score += int(comfort.get(r["activity"], 3)) <= 2  # relevant but intimidating
        ranked.append((score, r))
    ranked.sort(key=lambda x: -x[0])
    top = ranked[0][1]
    why = [f"Your goal is to {GOALS.get(a.get('goal'), 'move forward')}, and this directly supports it."]
    if top["helps_with"][0] in challenges:
        why.append(f"You said {top['challenge_label']} is one of your hardest parts.")
    if int(comfort.get(top["activity"], 3)) <= 2:
        why.append("It feels nerve-wracking right now, so we split it into small steps instead of a big leap.")
    brief = lambda r: {k: r[k] for k in ("id", "icon", "title", "blurb")}
    return {"primary": {**brief(top), "steps": len(top["quest"])}, "why": why,
            "others": [brief(r) for _, r in ranked[1:]]}


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/questions")
def questions():
    return jsonify(load("questions.json"))


@app.post("/api/match")
def match():
    return jsonify(recommend(request.get_json(force=True)))


@app.get("/api/resource/<rid>")
def resource(rid):
    found = next((r for r in load("resources.json") if r["id"] == rid), None)
    return (jsonify(found), 200) if found else (jsonify(error="not found"), 404)


if __name__ == "__main__":
    app.run(debug=True)
