import tempfile

import data_loaders as loaders


def test_load_members_dataframe_csv_basic():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
        tmp.write("Name,Member_ID,Membership_Type,Adult,Child\n")
        tmp.write("John Doe,ID123,Family,2,1\n")
        path = tmp.name

    df = loaders.load_members_dataframe(path)
    assert list(df.columns) == ["Name", "Member_ID", "Membership_Type", "Adult", "Child"]
    assert len(df) == 1
    assert df.iloc[0]["Member_ID"] == "ID123"


class _FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.headers = {}
        self.content = b"{}"
        self.text = ""

    def json(self):
        return self._payload


class _FakeRequests:
    def __init__(self, payload):
        self._payload = payload

    def post(self, *args, **kwargs):
        return _FakeResp(200, self._payload)


def test_load_members_dataframe_appsheet_accepts_list_response(monkeypatch):
    # Avoid sleeps in retry logic
    monkeypatch.setattr(loaders, "time", type("T", (), {"sleep": staticmethod(lambda *_a, **_k: None)})(), raising=False)
    # Inject fake requests into sys.modules so the loader's local import picks it up.
    import sys
    sys.modules["requests"] = _FakeRequests(
        [
            {
                "Member ID": "ID1",
                "Full Name": "Alice",
                "Membership Type": "Family",
                "Adult": 2,
                "Child": 1,
            }
        ]
    )
    df = loaders.load_members_dataframe_appsheet(app_id="app", table_name="table", application_access_key="key", region="www.appsheet.com")
    assert len(df) == 1
    assert df.iloc[0]["Member_ID"] == "ID1"


def test_load_members_dataframe_appsheet_accepts_dict_rows_response(monkeypatch):
    monkeypatch.setattr(loaders, "time", type("T", (), {"sleep": staticmethod(lambda *_a, **_k: None)})(), raising=False)
    import sys
    sys.modules["requests"] = _FakeRequests(
        {
            "Rows": [
                {
                    "Member ID": "ID2",
                    "Full Name": "Bob",
                    "Membership Type": "Single",
                    "Adult": 1,
                    "Child": 0,
                }
            ]
        }
    )
    df = loaders.load_members_dataframe_appsheet(app_id="app", table_name="table", application_access_key="key", region="www.appsheet.com")
    assert len(df) == 1
    assert df.iloc[0]["Member_ID"] == "ID2"

