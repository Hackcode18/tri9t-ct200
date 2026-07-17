from app.ingest import ingest_document

print("Ingesting V1...")
ingest_document("data/ct200_manual.pdf")

print("Ingesting V2...")
ingest_document("data/ct200_manual_v2.pdf")