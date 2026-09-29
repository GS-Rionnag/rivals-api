from rivalsdata import hero_id, hero_name
from rivalsdata.models import DataModel


def test_hero_lookup_accepts_id_and_name() -> None:
    assert hero_name(1016) == "Loki"
    assert hero_id("loki") == 1016
    assert hero_name(9999) is None
    assert hero_id("not a hero") is None


def test_model_mapping_and_serialization_include_resolved_hero() -> None:
    row = DataModel({"hero_id": 1016, "kills": 15})

    assert row.hero_name == "Loki"
    assert dict(row) == {"hero_id": 1016, "kills": 15, "hero_name": "Loki"}
    assert row.to_dict() == dict(row)
    assert row.raw == {"hero_id": 1016, "kills": 15}


def test_nested_models_resolve_hero_names_and_ignore_unknown_ids() -> None:
    model = DataModel({
        "players": [{"top_hero_id": "1016"}, {"hero_id": 9999}],
    })

    assert model.to_dict() == {
        "players": [
            {"top_hero_id": "1016", "top_hero_name": "Loki"},
            {"hero_id": 9999},
        ],
    }
