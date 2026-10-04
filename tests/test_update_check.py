import json
from nenolink_ai_marker.update_check import check_for_update, is_approved_update_url, APPROVED_UPDATE_URL
def test_update_service_comparison_and_url_policy():
    payload={"schema":1,"latest_version":"1.0.2","release_date":"2026-09-10","update_url":APPROVED_UPDATE_URL,"minimum_supported_version":"1.0.1"}
    class R:
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def read(self,n): return json.dumps(payload).encode()
    assert check_for_update("1.0.1", opener=lambda *a, **k:R()).update_available
    assert is_approved_update_url(APPROVED_UPDATE_URL)
