from app.utils.pagination import get_total_pages, get_total_records, parse_worldbank_response


class TestParseWorldBankResponse:
    def test_valid_response(self) -> None:
        raw = [{"page": 1, "pages": 3, "per_page": 100, "total": 250}, [{"id": "ESP"}]]
        metadata, data = parse_worldbank_response(raw)
        assert metadata["page"] == 1
        assert metadata["pages"] == 3
        assert len(data) == 1

    def test_empty_response(self) -> None:
        metadata, data = parse_worldbank_response([])
        assert metadata == {}
        assert data == []

    def test_non_list_response(self) -> None:
        metadata, data = parse_worldbank_response("invalid")
        assert metadata == {}
        assert data == []

    def test_single_element_list(self) -> None:
        metadata, data = parse_worldbank_response([{"page": 1}])
        assert metadata == {}
        assert data == []


class TestGetTotalPages:
    def test_from_metadata(self) -> None:
        assert get_total_pages({"pages": 5}) == 5

    def test_missing_pages(self) -> None:
        assert get_total_pages({}) == 1


class TestGetTotalRecords:
    def test_from_metadata(self) -> None:
        assert get_total_records({"total": 250}) == 250

    def test_missing_total(self) -> None:
        assert get_total_records({}) == 0
