import pdfplumber
import hashlib
import re
from typing import List, Dict, Optional

def get_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()

def detect_level(heading: str) -> int:
    match = re.match(r'^(\d+(\.\d+)*)', heading.strip())
    if not match:
        return 0
    parts = match.group(1).split('.')
    return len(parts)

def parse_pdf(pdf_path: str) -> List[Dict]:
    nodes = []
    current_heading = None
    current_body_lines = []

    heading_pattern = re.compile(r'^(\d+(\.\d+)*\.?)\s+.+')

    def flush_node():
        if current_heading:
            body = ' '.join(current_body_lines).strip()
            level = detect_level(current_heading)
            path = current_heading.strip().split()[0].rstrip('.')
            nodes.append({
                "heading": current_heading.strip(),
                "level": level,
                "body": body,
                "path": path,
                "content_hash": get_hash(current_heading.strip() + body)
            })

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if heading_pattern.match(line):
                    flush_node()
                    current_heading = line
                    current_body_lines = []
                else:
                    if current_heading:
                        current_body_lines.append(line)

    flush_node()
    return nodes

def build_tree(nodes: List[Dict]) -> List[Dict]:
    stack = []
    for node in nodes:
        node['children'] = []
        node['parent_path'] = None
        while stack and stack[-1]['level'] >= node['level']:
            stack.pop()
        if stack:
            node['parent_path'] = stack[-1]['path']
        stack.append(node)
    return nodes
