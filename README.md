
# Book Analysis: Vibe Coding for Computational Linguists

## Overview
This project demonstrates how vibe coding methodologies can enhance and support computational linguists in their research and development workflows.

## Purpose
To explore the intersection of intuitive, flow-based coding practices and computational linguistics tasks, making linguistic analysis more accessible and efficient.

## Features
- Vibe-coding driven approach to linguistic analysis
- Support for common NLP tasks
- Streamlined workflow for computational linguists

## Installation
No additional Python dependencies are required for the Gutenberg downloader script.

## Usage
```bash
python download_czech_gutenberg.py --output-dir data/czech_books --summary-file data/czech_summary.csv
python tfidf_keywords.py --input-dir data/czech_books --output-file data/tfidf_keywords.csv --top-n 10 --stoplist-file stoplist.txt
python visualize_keyword_frequency.py --input-file data/czech_books/13083_R.U.R._by_Karel_Čapek_-_Project_Gutenberg.txt --keywords-file data/tfidf_keywords.csv --output-file data/keyword_progression.png --segments 10
python visualize_keyword_frequency.py --input-dir data/czech_books --output-dir data/keyword_plots --keywords-file data/tfidf_keywords.csv --segments 10
```

## Gutenberg downloader
A new script `download_czech_gutenberg.py` downloads Czech books from Project Gutenberg when plain text versions are available.
It cleans the Project Gutenberg header/footer metadata and writes a CSV summary with:
- title
- author
- word count
- character count
- cleaned text filename

## TF-IDF keyword extraction
A new script `tfidf_keywords.py` reads cleaned Czech book texts and ranks keywords using TF-IDF.
It creates a CSV file with the top keywords per document.

## Keyword frequency visualization
A new script `visualize_keyword_frequency.py` plots how keyword frequency changes over the length of a book.
It can use manually supplied keywords or top keywords extracted from `tfidf_keywords.py`.

## Source
This script scrapes the Czech language page on Project Gutenberg:
https://www.gutenberg.org/browse/languages/cs


## Project Structure
```
book_analysis/
├── src/          # Source code
├── tests/        # Test files
├── data/         # Sample data
└── README.md     # This file
```

## Contributing
Contributions are welcome. Please fork and submit pull requests.

## License
[Specify your license]

## References
- Add relevant papers or resources on computational linguistics and vibe coding
