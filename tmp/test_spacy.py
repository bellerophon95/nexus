import spacy

nlp = spacy.load("en_core_web_sm")
text = "This is a sentence. This is another sentence. Dijkstra is here."
disabled_pipes = ["tagger", "parser", "ner", "attribute_ruler", "lemmatizer"]

print(f"Pipeline components: {nlp.pipe_names}")
doc = nlp(text, disable=disabled_pipes)

try:
    sents = list(doc.sents)
    print(f"Sentences found: {len(sents)}")
    for s in sents:
        print(f" - {s.text}")
except ValueError as e:
    print(f"Error accessing doc.sents: {e}")

# Try with sentencizer
if "sentencizer" not in nlp.pipe_names:
    nlp.add_pipe("sentencizer")
    print("\nAdded sentencizer.")

doc2 = nlp(text, disable=disabled_pipes)
sents2 = list(doc2.sents)
print(f"Sentences found with sentencizer: {len(sents2)}")
for s in sents2:
    print(f" - {s.text}")
