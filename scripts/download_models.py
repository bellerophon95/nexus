from sentence_transformers import SentenceTransformer


def download_models():
    """
    Downloads and caches the required ML models into the standard
    HuggingFace/SentenceTransformers cache directories.
    """
    model_name = "all-MiniLM-L6-v2"
    print(f"Downloading SentenceTransformer model: {model_name}...")

    # This will download the model to the default cache directory (~/.cache/huggingface/hub)
    # or the specified TRANSFORMERS_CACHE environment variable.
    SentenceTransformer(model_name)

    print("Model download complete.")


if __name__ == "__main__":
    download_models()
