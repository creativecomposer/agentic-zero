import os
import argparse

from ingest import ingest_file


def main():
    parser = argparse.ArgumentParser(
        description='Ingest the given file to Qdrant vector database')
    parser.add_argument('filepath', type=str,
                        help='The path to the file to ingest.')
    args = parser.parse_args()
    file_path = args.filepath
    if os.path.isfile(file_path):
        print(f'Processing file: {file_path}')
        ingest_file(file_path=file_path)
    else:
        print("The given filepath is not a valid file. :(")


if __name__ == '__main__':
    main()
