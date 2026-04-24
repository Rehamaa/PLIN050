import argparse
import csv
import os
import re
import sys
from collections import Counter

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

WORD_RE = re.compile(r"[a-záčďéěíňóřšťúůýž]+", re.IGNORECASE)

def normalize_filename(path):
    return os.path.basename(path)


def tokenize(text):
    return [token.lower() for token in WORD_RE.findall(text)]


def load_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def load_keywords_from_csv(csv_path, filename, top_n):
    keywords = []
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("filename") == filename:
                keyword = row.get("keyword")
                if keyword:
                    keywords.append(keyword.lower())
                if len(keywords) >= top_n:
                    break
    return keywords


def available_keywords_filenames(csv_path, limit=10):
    names = []
    seen = set()
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("filename")
            if name and name not in seen:
                seen.add(name)
                names.append(name)
            if len(names) >= limit:
                break
    return names


def build_filename_keyword_map(csv_path, top_n):
    mapping = {}
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("filename")
            keyword = row.get("keyword")
            if not filename or not keyword:
                continue
            mapping.setdefault(filename, []).append(keyword.lower())
            if len(mapping[filename]) >= top_n:
                continue
    return mapping


def compute_segment_counts(tokens, keywords, segments):
    if segments <= 0:
        raise ValueError("Number of segments must be positive")
    boundaries = [int(round(i * len(tokens) / segments)) for i in range(segments + 1)]
    frequency_series = {keyword: [] for keyword in keywords}

    for segment_index in range(segments):
        start = boundaries[segment_index]
        end = boundaries[segment_index + 1]
        segment_tokens = tokens[start:end]
        counts = Counter(segment_tokens)
        length = len(segment_tokens) or 1
        for keyword in keywords:
            frequency_series[keyword].append(counts[keyword] / length)

    return frequency_series


def plot_frequency(frequency_series, output_file, title, show_plot):
    if plt is None:
        raise ImportError("matplotlib is required for plotting. Install it with 'pip install matplotlib'.")

    segments = len(next(iter(frequency_series.values()), []))
    x = list(range(1, segments + 1))

    plt.figure(figsize=(10, 5))
    for keyword, frequencies in frequency_series.items():
        plt.plot(x, frequencies, marker="o", label=keyword)

    plt.xlabel("Text segment")
    plt.ylabel("Relative keyword frequency")
    plt.title(title)
    plt.xticks(x)
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    print(f"Saved keyword frequency plot to {output_file}")
    if show_plot:
        plt.show()


def generate_plot(input_file, output_file, keywords, segments, show_plot):
    text = load_text(input_file)
    tokens = tokenize(text)
    if not tokens:
        raise ValueError(f"No tokens found in {input_file}")

    frequency_series = compute_segment_counts(tokens, [kw.lower() for kw in keywords], segments)
    plot_title = f"Keyword frequency progression for {normalize_filename(input_file)}"
    plot_frequency(frequency_series, output_file, plot_title, show_plot)


def main():
    parser = argparse.ArgumentParser(
        description="Visualize keyword frequency progression within Czech book texts."
    )
    parser.add_argument("--input-file", help="Cleaned text file to analyze")
    parser.add_argument("--input-dir", help="Directory of cleaned text files to analyze")
    parser.add_argument("--output-file", default="keyword_frequency.png", help="Image file to save the plot for single file mode")
    parser.add_argument("--output-dir", default="keyword_plots", help="Directory to save plots in batch mode")
    parser.add_argument("--keywords", nargs="+", help="Keywords to plot")
    parser.add_argument("--keywords-file", help="CSV with keywords, typically produced by tfidf_keywords.py")
    parser.add_argument("--top-n", type=int, default=10, help="Number of top keywords to load from keywords file")
    parser.add_argument("--segments", type=int, default=10, help="Number of text segments for frequency progression")
    parser.add_argument("--show", action="store_true", help="Show the plot interactively")
    args = parser.parse_args()

    if not args.input_file and not args.input_dir:
        parser.error("Either --input-file or --input-dir must be provided.")
    if args.input_file and args.input_dir:
        parser.error("Only one of --input-file or --input-dir may be provided.")
    if args.keywords is None and args.keywords_file is None:
        parser.error("Either --keywords or --keywords-file must be provided.")

    if args.input_file:
        if args.keywords_file:
            filename = normalize_filename(args.input_file)
            args.keywords = load_keywords_from_csv(args.keywords_file, filename, args.top_n)
            if not args.keywords:
                available = available_keywords_filenames(args.keywords_file, limit=8)
                available_list = ", ".join(available)
                parser.error(
                    f"No keywords found for '{filename}' in {args.keywords_file}. Available filenames: {available_list}"
                )
        generate_plot(args.input_file, args.output_file, args.keywords, args.segments, args.show)
        return

    if args.input_dir:
        if not os.path.isdir(args.input_dir):
            parser.error(f"Input directory does not exist: {args.input_dir}")

        os.makedirs(args.output_dir, exist_ok=True)
        keyword_map = {}
        if args.keywords_file:
            keyword_map = build_filename_keyword_map(args.keywords_file, args.top_n)

        text_files = sorted(
            f for f in os.listdir(args.input_dir)
            if f.lower().endswith(".txt") and os.path.isfile(os.path.join(args.input_dir, f))
        )
        if not text_files:
            parser.error(f"No text files found in {args.input_dir}")

        generated = 0
        for text_file in text_files:
            input_path = os.path.join(args.input_dir, text_file)
            if args.keywords_file:
                keywords = keyword_map.get(text_file, [])
                if not keywords:
                    print(f"Skipping {text_file}: no keywords found in {args.keywords_file}")
                    continue
            else:
                keywords = args.keywords

            safe_name = os.path.splitext(text_file)[0]
            output_path = os.path.join(args.output_dir, f"{safe_name}.png")
            print(f"Generating plot for {text_file} -> {output_path}")
            generate_plot(input_path, output_path, keywords, args.segments, False)
            generated += 1

        print(f"Generated {generated}/{len(text_files)} plots in {args.output_dir}")


if __name__ == "__main__":
    main()
