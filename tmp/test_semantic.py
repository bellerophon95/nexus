import spacy
from sentence_transformers import SentenceTransformer
import numpy as np

# Load spaCy
nlp = spacy.load("en_core_web_sm")

# Load Sentence Transformer
model = SentenceTransformer('all-MiniLM-L6-v2')

text = "This is the first sentence. This is the second sentence. And here is a third one for good measure."
doc = nlp(text)
sentences = [sent.text.strip() for sent in doc.sents]

print(f"Sentences: {sentences}")

embeddings = model.encode(sentences)
print(f"Embeddings shape: {embeddings.shape}")

# Calculate cosine similarities between adjacent sentences
similarities = []
for i in range(len(embeddings) - 1):
    sim = np.dot(embeddings[i], embeddings[i+1]) / (np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[i+1]))
    similarities.append(sim)

print(f"Similarities: {similarities}")
