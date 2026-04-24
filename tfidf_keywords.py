import argparse
import csv
import math
import os
import re
from collections import Counter, defaultdict

DEFAULT_CZECH_STOPWORDS = {
    "a", "aby", "ahoj", "aj", "ale", "ano", "asi", "b", "bez", "by", "byl", "byla",
    "byli", "bylo", "co", "chtěl", "chtěla", "chce", "do", "ho", "i", "jsme", "jsou",
    "jsi", "jsem", "k", "kde", "ke", "když", "když", "ma", "me", "mne", "mně", "mi",
    "mimo", "moc", "mu", "můj", "můj", "myslím", "na", "nad", "nam", "nám", "nato",
    "ne", "nebo", "než", "nich", "nov", "o", "ob", "od", "on", "ona", "oni", "ono",
    "proto", "pro", "proč", "s", "sa", "se", "si", "svůj", "ta", "tak", "taky", "te",
    "tebe", "teď", "ten", "to", "tobě", "tom", "tomu", "toto", "trochu", "tu", "tuto",
    "ty", "u", "v", "ve", "vedle", "vi", "však", "vy", "z", "za", "že", "žádný",
    "ale", "ano", "by", "co", "do", "i", "jak", "já", "jsme", "jsou", "k", "ke", "na",
    "ne", "nebo", "pod", "po", "pra", "pro", "se", "si", "tak", "to", "ve", "vy", "za",
}

WORD_RE = re.compile(r"[a-záčďéěíňóřšťúůýž]+", re.IGNORECASE)


def normalize_text(text):
    return text.lower()


def load_stoplist(path):
    stopwords = set()
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            token = line.strip().lower()
            if token and not token.startswith("#"):
                stopwords.add(token)
    return stopwords


def build_stoplist(stoplist_file=None):
    stopwords = set(DEFAULT_CZECH_STOPWORDS)
    if stoplist_file:
        stopwords.update(load_stoplist(stoplist_file))
    return stopwords


def tokenize(text, stopwords):
    text = normalize_text(text)
    return [token for token in WORD_RE.findall(text) if token not in stopwords]


def load_documents(directory):
    docs = []
    for filename in sorted(os.listdir(directory)):
        if not filename.lower().endswith(".txt"):
            continue
        path = os.path.join(directory, filename)
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            docs.append((filename, f.read()))
    return docs


def compute_tfidf(documents, stopwords):
    doc_term_counts = []
    df = Counter()

    for _, text in documents:
        tokens = tokenize(text, stopwords)
        term_counts = Counter(tokens)
        doc_term_counts.append(term_counts)
        for term in term_counts.keys():
            df[term] += 1

    total_docs = len(documents)
    tfidf_scores = []

    for term_counts in doc_term_counts:
        scores = {}
        total_terms = sum(term_counts.values())
        for term, count in term_counts.items():
            tf = count / total_terms if total_terms else 0.0
            idf = math.log((total_docs + 1) / (df[term] + 1)) + 1
            scores[term] = tf * idf
        tfidf_scores.append(scores)

    return tfidf_scores


def extract_top_keywords(documents, tfidf_scores, top_n):
    rows = []
    for (filename, _), scores in zip(documents, tfidf_scores):
        top_terms = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_n]
        for rank, (term, score) in enumerate(top_terms, start=1):
            rows.append({
                "filename": filename,
                "rank": rank,
                "keyword": term,
                "score": f"{score:.6f}",
            })
    return rows


def write_csv(rows, output_path):
    fieldnames = ["filename", "rank", "keyword", "score"]
    with open(output_path, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Extract TF-IDF keywords from Czech Gutenberg text files.")
    parser.add_argument("--input-dir", required=True, help="Directory with cleaned text files")
    parser.add_argument("--output-file", default="tfidf_keywords.csv", help="CSV file to write keyword rankings")
    parser.add_argument("--top-n", type=int, default=10, help="Number of top keywords per document")
    parser.add_argument("--stoplist-file", help="Optional file containing additional stopwords, one per line")
    args = parser.parse_args()

    documents = load_documents(args.input_dir)
    if not documents:
        print(f"No text files found in {args.input_dir}")
        return

    stopwords = build_stoplist(args.stoplist_file)
    tfidf_scores = compute_tfidf(documents, stopwords)
    rows = extract_top_keywords(documents, tfidf_scores, args.top_n)
    write_csv(rows, args.output_file)
    print(f"TF-IDF keywords written to {args.output_file}")


if __name__ == "__main__":
    main()
