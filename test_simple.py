#!/usr/bin/env python3
import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, '.')

# Load API key from .env
load_dotenv()

# Check if API key exists
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    print("❌ ERROR: ANTHROPIC_API_KEY not found in .env")
    print("Add this to .env: ANTHROPIC_API_KEY=sk-ant-your-key-here")
    exit(1)

print(f"✓ API Key loaded: {api_key[:15]}...")

# Import and use RAG system
from scripts.rag_system import RAGSystem
from scripts.evaluation_engine import AttackerProfile

# Initialize RAG
rag = RAGSystem("phase2_baseline_seed42", k=5)

# Ask a question
response = rag.query(
    user_query="What is my company's vacation policy?",
    profile=AttackerProfile.INTERNAL
)

# Print result
print(f"\nResponse:\n{response.response_text}\n")
print(f"Retrieved docs: {response.retrieved_doc_ids}")
print(f"Tokens used: {response.input_tokens} in, {response.output_tokens} out")