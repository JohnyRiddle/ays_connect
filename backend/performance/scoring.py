from decimal import Decimal


def calculate_score(metrics, policy):
    """Return an explainable 0..100 score, never pretending sparse data is certainty."""
    components = []
    for code, weight in policy.weights.items():
        metric = metrics.get(code)
        if not metric or metric.sample_size < policy.minimum_samples or metric.value is None:
            components.append({"metric": code, "status": "insufficient_data", "weight": weight})
            continue
        threshold = Decimal(str(policy.thresholds.get(code, 100)))
        raw = Decimal(metric.value)
        normalized = max(Decimal(0), min(Decimal(100), raw * 100 / threshold if threshold else Decimal(0)))
        components.append({"metric": code, "status": "included", "weight": weight, "value": float(raw), "normalized": float(normalized)})
    included = [item for item in components if item["status"] == "included"]
    total_weight = sum(Decimal(str(item["weight"])) for item in included)
    if not included or not total_weight:
        return None, "insufficient_data", components
    score = sum(Decimal(str(item["normalized"])) * Decimal(str(item["weight"])) for item in included) / total_weight
    return round(float(score), 2), "measured", components
