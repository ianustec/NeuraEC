from __future__ import annotations

from neuraec.features import load_catalog_descriptions


def test_catalog_covers_original_keys():
    cat = load_catalog_descriptions()
    assert set(cat["fig"]) == {
        "ceo_titolare",
        "dirigente",
        "manager",
        "impiegato",
        "operaio",
    }
    assert set(cat["fun"]) == {
        "direzione_generale",
        "risorse_umane",
        "amministrazione_finanza_ufficiolegale",
        "it",
        "acquisti",
        "logistica",
        "marketing_vendite",
        "ricerca_sviluppo",
        "produzione",
    }
    assert set(cat["set"]) == {
        "alimentare",
        "educazione",
        "media_pubblicita_intrattenimento",
        "farmaceutico_sanitario",
        "ict_telecomunicazioni",
        "manifatturiero",
        "retail",
        "sport",
        "assicurazioni_finanza_legale",
        "logistica_trasporti",
        "pubblica_amministrazione",
        "turismo",
        "altro",
    }
    for group in cat.values():
        for text in group.values():
            assert len(text) > 20
