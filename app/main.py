from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db, init_db
from app.models import Document, Node, Selection, SelectionItem
from app.llm import generate_test_cases
from pydantic import BaseModel
from typing import List
from datetime import datetime
import json
import os
import uuid

app = FastAPI(title="CT-200 QA API")

GENERATIONS_FILE = "generations.json"

def load_generations():
    if not os.path.exists(GENERATIONS_FILE):
        return []
    with open(GENERATIONS_FILE, "r") as f:
        return json.load(f)

def save_generations(data):
    with open(GENERATIONS_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def root():
    return {"message": "CT-200 QA API is running"}

@app.get("/sections")
def list_sections(version: int = None, db: Session = Depends(get_db)):
    query = db.query(Node).filter(Node.level == 1)
    if version:
        query = query.filter(Node.version == version)
    else:
        latest = db.query(Document).order_by(Document.version.desc()).first()
        if latest:
            query = query.filter(Node.version == latest.version)
    nodes = query.all()
    return [{"id": n.id, "heading": n.heading, "version": n.version, "hash": n.content_hash} for n in nodes]

@app.get("/node/{node_id}")
def get_node(node_id: int, db: Session = Depends(get_db)):
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return {
        "id": node.id,
        "heading": node.heading,
        "level": node.level,
        "body": node.body,
        "path": node.path,
        "version": node.version,
        "content_hash": node.content_hash,
        "parent_id": node.parent_id,
        "children": [{"id": c.id, "heading": c.heading} for c in node.children]
    }

@app.get("/search")
def search(q: str, db: Session = Depends(get_db)):
    nodes = db.query(Node).filter(
        Node.heading.contains(q) | Node.body.contains(q)
    ).all()
    return [{"id": n.id, "heading": n.heading, "version": n.version} for n in nodes]

@app.get("/diff/{node_path}")
def diff_node(node_path: str, db: Session = Depends(get_db)):
    nodes = db.query(Node).filter(Node.path == node_path).order_by(Node.version).all()
    if len(nodes) < 2:
        return {"status": "no change or only one version"}
    v1, v2 = nodes[0], nodes[-1]
    changed = v1.content_hash != v2.content_hash
    return {
        "path": node_path,
        "changed": changed,
        "v1_hash": v1.content_hash,
        "v2_hash": v2.content_hash,
        "v1_body": v1.body if changed else None,
        "v2_body": v2.body if changed else None
    }

# --- Selection API ---
class SelectionRequest(BaseModel):
    name: str
    node_ids: List[int]

@app.post("/selections")
def create_selection(req: SelectionRequest, db: Session = Depends(get_db)):
    existing = db.query(Selection).filter(Selection.name == req.name).first()
    if existing:
        return {"message": "Selection already exists", "selection_id": existing.id}

    selection = Selection(name=req.name)
    db.add(selection)
    db.flush()

    for node_id in req.node_ids:
        node = db.query(Node).filter(Node.id == node_id).first()
        if not node:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
        item = SelectionItem(
            selection_id=selection.id,
            node_id=node.id,
            version=node.version,
            content_hash=node.content_hash
        )
        db.add(item)

    db.commit()
    return {"message": "Selection created", "selection_id": selection.id}

@app.get("/selections/{selection_id}")
def get_selection(selection_id: int, db: Session = Depends(get_db)):
    selection = db.query(Selection).filter(Selection.id == selection_id).first()
    if not selection:
        raise HTTPException(status_code=404, detail="Selection not found")
    items = []
    for item in selection.items:
        node = db.query(Node).filter(Node.id == item.node_id).first()
        items.append({
            "node_id": item.node_id,
            "version": item.version,
            "heading": node.heading if node else None,
            "content_hash": item.content_hash
        })
    return {"id": selection.id, "name": selection.name, "items": items}

# --- LLM Generation API ---
class GenerateRequest(BaseModel):
    selection_id: int

@app.post("/generate")
def generate(req: GenerateRequest, db: Session = Depends(get_db)):
    selection = db.query(Selection).filter(Selection.id == req.selection_id).first()
    if not selection:
        raise HTTPException(status_code=404, detail="Selection not found")

    text_parts = []
    node_hashes = {}
    for item in selection.items:
        node = db.query(Node).filter(Node.id == item.node_id).first()
        if node:
            text_parts.append(f"{node.heading}\n{node.body}")
            node_hashes[str(node.id)] = node.content_hash

    full_text = "\n\n".join(text_parts)
    result = generate_test_cases(full_text)

    generation = {
        "id": str(uuid.uuid4()),
        "selection_id": req.selection_id,
        "selection_name": selection.name,
        "node_hashes": node_hashes,
        "result": result,
        "created_at": datetime.utcnow().isoformat()
    }

    generations = load_generations()
    generations.append(generation)
    save_generations(generations)

    return {"generation_id": generation["id"], "result": result}

# --- Retrieval + Staleness API ---
@app.get("/generations/{selection_id}")
def get_generations(selection_id: int, db: Session = Depends(get_db)):
    generations = load_generations()
    results = []
    for doc in generations:
        if doc["selection_id"] != selection_id:
            continue
        stale_nodes = []
        for node_id_str, old_hash in doc.get("node_hashes", {}).items():
            current_node = db.query(Node).filter(
                Node.id == int(node_id_str)
            ).order_by(Node.version.desc()).first()
            if current_node and current_node.content_hash != old_hash:
                stale_nodes.append({
                    "node_id": node_id_str,
                    "heading": current_node.heading,
                    "status": "STALE"
                })
        doc["staleness"] = {
            "is_stale": len(stale_nodes) > 0,
            "stale_nodes": stale_nodes
        }
        results.append(doc)
    return results
