"""Content-based, collaborative and explanation tests on a small, hand-made catalogue.

The catalogue has two clear "clusters": Zelda games on Switch and racing games
on PC. Users only interact within one cluster, so every sensible model should
recommend the unseen item of the user's own cluster.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp

from cartsense_ml.data.dataset import build_dataset
from cartsense_ml.explain import Explainer
from cartsense_ml.models.collaborative import ALS, ItemKNN, top_n_per_row
from cartsense_ml.models.content import ContentTfidf, product_documents
from cartsense_ml.models.popularity import CategoryPopular, RecentPopular

T = 1_600_000_000_000
DAY = 86_400_000


@pytest.fixture
def ds():
    products = pd.DataFrame(
        {
            "item_id": ["Z1", "Z2", "Z3", "R1", "R2", "R3", "NEW"],
            "title": [
                "Zelda Breath of the Wild",
                "Zelda Tears of the Kingdom",
                "Zelda Links Awakening",
                "Forza Racing Horizon",
                "Racing Grand Prix Simulator",
                "Rally Racing Championship",
                "Zelda Skyward Sword HD",
            ],
            "brand": ["Nintendo", "Nintendo", "Nintendo", "Microsoft", "Codemasters", "Codemasters", "Nintendo"],
            "categories": [["Video Games", "Nintendo Switch", "Games"]] * 3
            + [["Video Games", "PC", "Games"]] * 3
            + [["Video Games", "Nintendo Switch", "Games"]],
            "features": [["open world adventure"]] * 3 + [["racing wheel support"]] * 3 + [["adventure"]],
            "description": ["Explore Hyrule as Link."] * 3 + ["Drive fast cars on tracks."] * 3 + ["Hyrule sky."],
            # NEW has no interactions but was released before the cutoff
            "date_first_available": [date(2015, 1, 1)] * 6 + [date(2019, 1, 1)],
        }
    )
    rows = []
    for u in range(12):  # Zelda players
        seen = ["Z1", "Z2", "Z3"]
        for i in (seen[: 3 if u < 6 else 2]):
            rows.append((f"Z{u:02d}", i, T - (u + 1) * DAY))
    for u in range(12):  # racing players
        seen = ["R1", "R2", "R3"]
        for i in (seen[: 3 if u < 6 else 2]):
            rows.append((f"R{u:02d}", i, T - (u + 1) * DAY))
    history = pd.DataFrame(rows, columns=["user_id", "item_id", "timestamp"]).assign(rating=5.0)
    return build_dataset(history, products, cutoff_ms=T)


def _first_rec(model, ds, user):
    return ds.item_ids[model.recommend(ds.encode_users([user]), k=1)[0, 0]]


def test_top_n_per_row():
    m = sp.csr_matrix(np.array([[0, 3, 1, 2], [0, 0, 0, 0], [5, 0, 0, 4]], dtype=np.float32))
    pruned = top_n_per_row(m, 2).toarray()
    assert pruned.tolist() == [[0, 3, 0, 2], [0, 0, 0, 0], [5, 0, 0, 4]]


@pytest.mark.parametrize("model_cls", [ItemKNN, ALS, ContentTfidf])
def test_models_recommend_within_users_cluster(ds, model_cls):
    kwargs = {"min_df": 1} if model_cls is ContentTfidf else {}
    if model_cls is ALS:
        kwargs = {"factors": 4, "iterations": 15, "num_threads": 1}
    model = model_cls(**kwargs).fit(ds)
    # users 6.. have seen two of three items in their cluster
    assert _first_rec(model, ds, "Z07") in {"Z3", "NEW"}
    assert _first_rec(model, ds, "R07") == "R3"


def test_content_reaches_new_items_and_cf_cannot(ds):
    new = ds.item_index["NEW"]
    content = ContentTfidf(min_df=1).fit(ds)
    knn = ItemKNN().fit(ds)
    u = ds.encode_users(["Z00"])  # has seen all three Zelda games
    assert ds.item_ids[content.recommend(u, k=1)[0, 0]] == "NEW"
    # item-kNN has no co-occurrence for NEW; its score is only the tiny prior
    assert knn.score(u)[0, new] < 0.01


def test_content_similar_items_and_terms(ds):
    content = ContentTfidf(min_df=1).fit(ds)
    z1 = ds.item_index["Z1"]
    similar = [ds.item_ids[i] for i, _ in content.similar_items(z1, k=3)]
    assert set(similar) <= {"Z2", "Z3", "NEW"} and similar
    terms = content.shared_terms(z1, ds.item_index["Z2"])
    assert "zelda" in terms


def test_tfidf_vocabulary_ignores_unavailable_items():
    products = pd.DataFrame(
        {
            "item_id": ["A", "B"],
            "title": ["alpha game", "futuristic unreleased"],
            "categories": [["Video Games"]] * 2,
            "date_first_available": [date(2000, 1, 1), date(2099, 1, 1)],
        }
    )
    history = pd.DataFrame({"user_id": ["U"], "item_id": ["A"], "rating": [5.0], "timestamp": [T]})
    model = ContentTfidf(min_df=1).fit(build_dataset(history, products))
    assert "futuristic" not in model.vectorizer.vocabulary_


def test_cold_users_get_popularity(ds):
    cold = np.array([-1])
    pop = RecentPopular().fit(ds).recommend(cold, k=3)
    for model in (ItemKNN().fit(ds), ContentTfidf(min_df=1).fit(ds)):
        assert model.recommend(cold, k=3).tolist() == pop.tolist()


def test_product_documents_include_tags():
    doc = product_documents(pd.DataFrame({"title": ["T"], "brand": ["Big Co."], "categories": [["Video Games", "PC"]],
                                          "features": [[]], "description": [None]}))[0]
    assert "brand_big_co" in doc and "cat_pc" in doc


def test_explanations_per_model(ds):
    u = int(ds.encode_users(["Z07"])[0])
    z3 = ds.item_index["Z3"]

    knn_reasons = Explainer(ItemKNN().fit(ds)).explain(u, z3)
    assert knn_reasons[0].type == "also_reviewed_with"
    assert knn_reasons[0].item_id in {"Z1", "Z2"}

    content_reasons = Explainer(ContentTfidf(min_df=1).fit(ds)).explain(u, z3)
    assert content_reasons[0].type == "similar_content"
    assert "zelda" in content_reasons[0].details["shared_terms"]

    cat_reasons = Explainer(CategoryPopular().fit(ds)).explain(u, z3)
    assert cat_reasons[0].type == "popular_on_platform"
    assert cat_reasons[0].details["platform"] == "Nintendo Switch"

    als_reasons = Explainer(ALS(factors=4, iterations=10, num_threads=1).fit(ds)).explain(u, z3)
    assert als_reasons[0].type in {"similar_taste", "popular_on_platform"}


def test_cold_user_explanation_is_popularity(ds):
    reasons = Explainer(ItemKNN().fit(ds)).explain(-1, ds.item_index["R1"])
    assert len(reasons) == 1 and reasons[0].type == "trending"
    d = reasons[0].to_dict()
    assert d["details"]["rank"] >= 1 and "item_id" not in d
