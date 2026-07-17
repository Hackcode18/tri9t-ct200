from app.parser import parse_pdf, build_tree
from app.models import Document, Node
from app.database import SessionLocal, init_db

def ingest_document(pdf_path: str, doc_name: str = "CT-200 Manual"):
    init_db()
    db = SessionLocal()

    # Check if document exists
    existing = db.query(Document).filter(Document.name == doc_name).order_by(Document.version.desc()).first()
    new_version = 1 if not existing else existing.version + 1

    # Create document record
    doc = Document(name=doc_name, version=new_version)
    db.add(doc)
    db.flush()

    # Parse PDF
    raw_nodes = parse_pdf(pdf_path)
    tree_nodes = build_tree(raw_nodes)

    # Save nodes
    path_to_db_id = {}
    for node in tree_nodes:
        parent_id = None
        if node['parent_path']:
            parent_id = path_to_db_id.get(node['parent_path'])

        db_node = Node(
            document_id=doc.id,
            version=new_version,
            heading=node['heading'],
            level=node['level'],
            body=node['body'],
            path=node['path'],
            content_hash=node['content_hash'],
            parent_id=parent_id
        )
        db.add(db_node)
        db.flush()
        path_to_db_id[node['path']] = db_node.id

    db.commit()
    db.close()
    print(f"Ingested version {new_version} with {len(tree_nodes)} nodes.")
    return new_version
