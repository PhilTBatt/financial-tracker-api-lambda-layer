import io
from lambda_function import process_file
from qifparse.parser import QifParser

def test_process_file():
    with open("tests/data/Statements09012954183252.qif", "r", encoding="utf-8") as f:
        qif_text = f.read()

    qifParsed = QifParser.parse(io.StringIO(qif_text))

    df = process_file(qifParsed)

    assert not df.empty
    assert len(df) == 599

    assert df.iloc[0]["description"] == "EAST LEEDS SNOOKER CLU (VIA GOOGLE PAY), ON 30-07-2025, 4.80"
    assert df.iloc[0]["amount"] == -4.80