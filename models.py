from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    nodes = relationship("Node", back_populates="document")

class Node(Base):
    __tablename__ = "nodes"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    version = Column(Integer, default=1)
    heading = Column(String)
    level = Column(Integer)
    body = Column(Text)
    path = Column(String)
    content_hash = Column(String)
    parent_id = Column(Integer, ForeignKey("nodes.id"), nullable=True)
    document = relationship("Document", back_populates="nodes")
    children = relationship(
        "Node",
        primaryjoin="Node.parent_id == Node.id",
        foreign_keys="Node.parent_id",
        backref="parent",
        remote_side="[Node.id]"
    )

class Selection(Base):
    __tablename__ = "selections"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    items = relationship("SelectionItem", back_populates="selection")

class SelectionItem(Base):
    __tablename__ = "selection_items"
    id = Column(Integer, primary_key=True)
    selection_id = Column(Integer, ForeignKey("selections.id"))
    node_id = Column(Integer, ForeignKey("nodes.id"))
    version = Column(Integer)
    content_hash = Column(String)
    selection = relationship("Selection", back_populates="items")