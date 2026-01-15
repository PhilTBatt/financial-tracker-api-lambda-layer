import io
from lambda_function import process_file
from qifparse.parser import QifParser

def test_process_file():
    with open("tests/data/fb250351-0f39-42b5-a6d8-1a9bb274dba7_Statements09012954183252.qif", "r", encoding="utf-8") as f:
        qif_text = f.read()

    qifParsed = QifParser.parse(io.StringIO(qif_text))

    df = process_file(qifParsed)

    assert not df.empty
    assert len(df) == 600

    assert df.iloc[0]["payee"] == "FASTER PAYMENTS RECEIPT REF.Phil FROM P Battersby, 1200.01"
    assert df.iloc[0]["amount"] == 1200.01

    print(df.head())