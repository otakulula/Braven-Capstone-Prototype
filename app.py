import json
import os
from functools import cache
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from pydantic import BaseModel, Field

app = Flask(__name__)
DATA = Path(__file__).parent / "data"

# AI path runs only when a Groq key exists. Set USE_AI=0 to force the rule-based path.
USE_AI = bool(os.getenv("GROQ_API_KEY")) and os.getenv("USE_AI", "1") != "0"
LLM_MODEL = "llama-3.3-70b-versatile"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # runs locally, free

GOALS = {"internship": "land an internship", "job": "get a full-time job",
         "explore": "explore career paths", "grad": "prepare for grad school"}


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def brief(r):
    return {k: r[k] for k in ("id", "icon", "title", "blurb")}

# ---------------------------------------------------------------- rule-based
def rule_based(a):
    """Fallback matcher: simple rules, no network needed."""
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
    return {"primary": {**brief(top), "steps": len(top["quest"])}, "why": why,
            "others": [brief(r) for _, r in ranked[1:]], "source": "rules", "needs_review": False}


# ------------------------------------------------------------------ RAG / AI
class Pick(BaseModel):
    resource_id: str = Field(description="Exact id of ONE resource from the context")
    why: list[str] = Field(description="2-3 short, warm reasons, addressed to the Fellow as 'you'")
    confidence: float = Field(description="0 to 1; low if nothing fits well")


PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You match Braven Fellows to ONE career resource. Choose only from the resources "
     "below and use the exact id shown in brackets. Write 2-3 short, warm reasons "
     "addressed to the Fellow as 'you'. If a resource feels intimidating to them, say "
     "it will be broken into small steps. Set a low confidence if nothing fits well."
     "\n\nResources:\n{context}"),
    ("human", "Fellow profile:\n{profile}"),
])


@cache
def get_ai():
    """Build the vector store and chain once, on first use."""
    store = Chroma(collection_name="braven",
                   embedding_function=HuggingFaceEmbeddings(model_name=EMBED_MODEL),
                   persist_directory=str(Path(__file__).parent / "chroma_db"))
    # Only resources with a quest path are playable in the prototype. Remove the
    # filter once every resource has its own steps. Ids make re-ingesting safe.
    playable = [r for r in load("resources.json") if r["quest"]]
    store.add_documents(
        [Document(page_content=(f"{r['title']}. {r['blurb']} Helps with: "
                                f"{', '.join(r['helps_with'])}. Good for goals: {', '.join(r['goals'])}."),
                  metadata={"id": r["id"]}) for r in playable],
        ids=[r["id"] for r in playable])
    llm = ChatGroq(model=LLM_MODEL, temperature=0).with_structured_output(Pick)
    return store, PROMPT | llm


def profile_text(a):
    comfort = ", ".join(f"{k} {v}/5" for k, v in a.get("comfort", {}).items())
    return (f"Goal: {GOALS.get(a.get('goal'), 'unknown')}. Field: {a.get('field', 'unknown')}. "
            f"Hardest challenges: {', '.join(a.get('challenges', [])) or 'none given'}. "
            f"Comfort (1 = very nervous, 5 = very comfortable): {comfort}. "
            f"Time per week: {a.get('time')}. Preferred format: {a.get('format')}.")


def recommend_ai(a):
    store, chain = get_ai()
    profile = profile_text(a)
    docs = store.similarity_search(profile, k=3)
    context = "\n\n".join(f"[{d.metadata['id']}] {d.page_content}" for d in docs)
    pick = chain.invoke({"context": context, "profile": profile})

    resources = {r["id"]: r for r in load("resources.json")}
    top = resources.get(pick.resource_id)
    if not top or not top["quest"]:  # model invented or chose an id we can't play
        raise ValueError(f"bad resource_id: {pick.resource_id}")
    return {"primary": {**brief(top), "steps": len(top["quest"])},
            "why": pick.why[:3],
            "others": [brief(r) for rid, r in resources.items() if rid != top["id"]],
            "source": "ai", "needs_review": pick.confidence < 0.6}


def recommend(a):
    if USE_AI:
        try:
            return recommend_ai(a)
        except Exception as e:  # rate limit, bad output, no network, etc.
            app.logger.warning("AI path failed, using rules: %s", e)
    return rule_based(a)


# -------------------------------------------------------------------- routes
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