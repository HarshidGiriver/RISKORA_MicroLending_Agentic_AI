"""Fetch and audit the pinned Kaggle default dataset without changing runtime data.

python scripts/prepare_external_dataset.py --archive path/to/download.zip
python scripts/prepare_external_dataset.py              # pinned public download
python scripts/prepare_external_dataset.py --check      # audit existing local copy

Only Python's standard library is required. No model is loaded or trained.
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'data' / 'external' / 'kaggle_loan_default'
URL = 'https://www.kaggle.com/api/v1/datasets/download/nikhil1e9/loan-default?datasetVersionNumber=2'
CSV_HASH = '1d7556a9071e7f9e872dc05a0cad174229fb1164b1cf3470ad35eed195c24278'
CSV_SIZE = 24834870
MEMBER = 'Loan_default.csv'
COLUMNS = ['LoanID', 'Age', 'Income', 'LoanAmount', 'CreditScore', 'MonthsEmployed',
           'NumCreditLines', 'InterestRate', 'LoanTerm', 'DTIRatio', 'Education',
           'EmploymentType', 'MaritalStatus', 'HasMortgage', 'HasDependents',
           'LoanPurpose', 'HasCoSigner', 'Default']
NUMERIC = COLUMNS[1:10]


def verify_bytes(data):
    if len(data) != CSV_SIZE or hashlib.sha256(data).hexdigest() != CSV_HASH:
        raise ValueError('Dataset differs from the reviewed version. Do not accept it without a new source review.')


def read_archive(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        member = archive.getinfo(MEMBER)
        if member.file_size != CSV_SIZE:
            raise ValueError('Unexpected CSV size in archive.')
        raw = archive.read(member)  # Read this member only; never extract arbitrary paths.
    verify_bytes(raw)
    return raw


def profile(data):
    verify_bytes(data)
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
    if reader.fieldnames != COLUMNS:
        raise ValueError('Unexpected dataset columns or column order.')
    counts = {key: Counter() for key in COLUMNS[10:]}
    missing = Counter({key: 0 for key in COLUMNS})
    ranges = {key: [float('inf'), float('-inf')] for key in NUMERIC}
    seen_ids, seen_rows = set(), set()
    duplicates = duplicate_ids = row_count = 0
    flags = Counter()
    for row in reader:
        row_count += 1
        values = tuple(row.get(key, '') for key in COLUMNS)
        duplicates += values in seen_rows
        seen_rows.add(values)
        duplicate_ids += row['LoanID'] in seen_ids
        seen_ids.add(row['LoanID'])
        for key, value in row.items():
            missing[key] += value is None or not value.strip()
        for key in NUMERIC:
            value = float(row[key])
            ranges[key] = [min(ranges[key][0], value), max(ranges[key][1], value)]
        for key in counts:
            counts[key][row[key]] += 1
        if row['EmploymentType'] not in ('Salaried', 'Self-employed', 'Contract', 'Unemployed'):
            flags['employment_category_not_in_application_schema'] += 1
        if float(row['MonthsEmployed']) > (float(row['Age']) - 16) * 12:
            flags['employment_exceeds_application_working_lifetime_rule'] += 1
        if row['EmploymentType'] == 'Unemployed' and float(row['MonthsEmployed']) > 0:
            flags['unemployed_with_positive_employment_months'] += 1
        if float(row['Income']) < 50000:
            flags['below_application_annual_income_warning_threshold'] += 1
        if float(row['LoanAmount']) > 2.5 * float(row['Income']) and row['HasCoSigner'] != 'Yes':
            flags['loan_exceeds_application_income_multiple_without_cosigner'] += 1
    return {
        'dataset': 'nikhil1e9/loan-default', 'version': 2,
        'sha256': CSV_HASH, 'rows': row_count, 'columns': COLUMNS,
        'missing_values': dict(missing), 'duplicate_rows': duplicates,
        'duplicate_loan_ids': duplicate_ids, 'numeric_ranges': ranges,
        'category_counts': {k: dict(sorted(v.items())) for k, v in counts.items()},
        'application_compatibility_flags': dict(flags),
        'default_rate': counts['Default']['1'] / row_count,
        'runtime_replacement_ready': False,
        'blocking_questions': [
            'Currency denomination is not specified in the source feature dictionary; application money is INR.',
            'Full-time and Part-time do not mean Salaried and Contract; no automatic mapping has been applied.',
            'Cohort origin, observation period and default horizon are not established by the available source documentation.',
            'Input-quality inconsistencies require review before model training or deployment.',
        ],
    }


def write_atomic(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, suffix='.tmp') as stream:
        temporary = Path(stream.name)
        stream.write(raw)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--archive', type=Path)
    group.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    target = DIRECTORY / MEMBER
    if args.check or target.exists():
        raw = target.read_bytes()
        verify_bytes(raw)  # A changed local file is never overwritten automatically.
    else:
        if args.archive:
            archive = args.archive.read_bytes()
        else:
            with urlopen(URL, timeout=90) as response:
                archive = response.read(32 * 1024 * 1024 + 1)
            if len(archive) > 32 * 1024 * 1024:
                raise ValueError('Download exceeded the size limit.')
        raw = read_archive(archive)
        write_atomic(target, raw)
    report = profile(raw)
    write_atomic(DIRECTORY / 'quality_report.json', (json.dumps(report, indent=2) + '\n').encode())
    print(f"Verified {report['rows']:,} rows and {len(report['columns'])} columns: {target}")
    print('Research dataset prepared. Runtime dataset and model artifacts were not changed.')


if __name__ == '__main__':
    main()
