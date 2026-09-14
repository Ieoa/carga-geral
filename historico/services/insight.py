"""Análise local e explicável dos registros de operações portuárias.

O módulo não usa APIs externas. As regras são determinísticas e, quando existe
uma amostra mínima, um Isolation Forest é treinado em memória com os próprios
registros do LOGGERAL.
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from statistics import median
from threading import RLock

from django.conf import settings

logger = logging.getLogger(__name__)

FEATURE_LABELS = {
    "espera_pob_horas": "intervalo entre ETA e POB",
    "espera_inicio_horas": "intervalo entre POB e início",
    "duracao_operacao_horas": "duração da operação",
    "ternos": "quantidade de ternos",
    "loa": "comprimento do navio (LOA)",
    "boca": "largura do navio (boca)",
    "peso_total": "peso total movimentado",
    "volume_total": "volume total movimentado",
    "produtividade_peso_hora": "produtividade por hora",
    "produtividade_peso_terno_hora": "produtividade por terno/hora",
}

# Volume fica disponível para conferência, mas não participa do modelo até que
# a organização padronize sua unidade de medida.
MODEL_FEATURES = (
    "espera_pob_horas",
    "espera_inicio_horas",
    "duracao_operacao_horas",
    "ternos",
    "loa",
    "boca",
    "peso_total",
    "produtividade_peso_hora",
    "produtividade_peso_terno_hora",
)

SEVERITY_ORDER = {"alta": 0, "media": 1, "baixa": 2}
RISK_LABELS = {"alto": "Alto", "medio": "Médio", "baixo": "Baixo"}
_MODEL_CACHE = {}
_MODEL_CACHE_LOCK = RLock()


def parse_localized_number(value):
    """Converte números nos formatos brasileiro e internacional para float."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float, Decimal)):
        number = float(value)
        return number if math.isfinite(number) else None

    text = str(value).strip().replace("\u00a0", " ")
    match = re.search(r"[-+]?\d[\d\s.,]*", text)
    if not match:
        return None
    number = match.group(0).replace(" ", "")

    if "," in number and "." in number:
        decimal_separator = "," if number.rfind(",") > number.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        number = number.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif "," in number:
        number = _normalize_single_separator(number, ",")
    elif "." in number:
        number = _normalize_single_separator(number, ".")

    try:
        parsed = float(number)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _normalize_single_separator(number, separator):
    pieces = number.split(separator)
    if len(pieces) > 2:
        return (
            "".join(pieces)
            if all(len(piece) == 3 for piece in pieces[1:])
            else "".join(pieces[:-1]) + "." + pieces[-1]
        )
    integer, decimals = pieces
    if len(decimals) == 3 and len(integer.lstrip("+-")) >= 1:
        return integer + decimals
    return integer + "." + decimals


def _hours(delta):
    if delta is None:
        return None
    return round(delta.total_seconds() / 3600, 4)


def _sum_known(*values):
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def extract_features(navio):
    duration = None
    if navio.inicio_operacao and navio.fim_operacao:
        duration = _hours(navio.fim_operacao - navio.inicio_operacao)

    peso_descarga = parse_localized_number(navio.peso_descarga)
    peso_embarque = parse_localized_number(navio.peso_embarque)
    volume_descarga = parse_localized_number(navio.volume_descarga)
    volume_embarque = parse_localized_number(navio.volume_embarque)
    peso_total = _sum_known(peso_descarga, peso_embarque)
    volume_total = _sum_known(volume_descarga, volume_embarque)
    ternos = float(navio.ternos) if navio.ternos is not None else None

    produtividade = None
    produtividade_terno = None
    if duration and duration > 0 and peso_total is not None and peso_total >= 0:
        produtividade = peso_total / duration
        if ternos and ternos > 0:
            produtividade_terno = produtividade / ternos

    return {
        "espera_pob_horas": _hours(navio.pob - navio.eta)
        if navio.eta and navio.pob
        else None,
        "espera_inicio_horas": _hours(navio.inicio_operacao - navio.pob)
        if navio.pob and navio.inicio_operacao
        else None,
        "duracao_operacao_horas": duration,
        "ternos": ternos,
        "loa": parse_localized_number(navio.loa),
        "boca": parse_localized_number(navio.boca),
        "peso_total": peso_total,
        "volume_total": volume_total,
        "produtividade_peso_hora": produtividade,
        "produtividade_peso_terno_hora": produtividade_terno,
    }


def _alert(code, severity, message, fields=()):
    return {
        "codigo": code,
        "severidade": severity,
        "mensagem": message,
        "campos": list(fields),
        "origem": "regra",
    }


def evaluate_rules(navio, features=None, duplicate=False):
    features = features or extract_features(navio)
    alerts = []

    timeline = (
        (
            "pob_inicio_invertidos",
            navio.pob,
            navio.inicio_operacao,
            "O início da operação foi registrado antes do POB.",
            ("pob", "inicio_operacao"),
        ),
        (
            "inicio_fim_invertidos",
            navio.inicio_operacao,
            navio.fim_operacao,
            "O término foi registrado antes do início da operação.",
            ("inicio_operacao", "fim_operacao"),
        ),
    )
    for code, first, second, message, fields in timeline:
        if first and second and second < first:
            alerts.append(_alert(code, "alta", message, fields))

    if navio.eta and navio.pob:
        eta_difference = _hours(navio.pob - navio.eta)
        if abs(eta_difference) > 24:
            severity = "alta" if abs(eta_difference) > 72 else "media"
            direction = "depois" if eta_difference > 0 else "antes"
            alerts.append(
                _alert(
                    "desvio_eta_pob",
                    severity,
                    f"O POB ocorreu {abs(eta_difference):.1f} h {direction} da ETA informada; confira a previsão e o horário realizado.",
                    ("eta", "pob"),
                )
            )

    informed_duration = (
        _hours(navio.tempo_operacao)
        if isinstance(navio.tempo_operacao, timedelta)
        else None
    )
    calculated_duration = features["duracao_operacao_horas"]
    if (
        informed_duration is not None
        and calculated_duration is not None
        and calculated_duration >= 0
    ):
        difference = abs(informed_duration - calculated_duration)
        tolerance = max(0.5, calculated_duration * 0.1)
        if difference > tolerance:
            alerts.append(
                _alert(
                    "duracao_divergente",
                    "media",
                    f"O tempo informado difere {difference:.1f} h do intervalo calculado entre início e término.",
                    ("tempo_operacao", "inicio_operacao", "fim_operacao"),
                )
            )

    numeric_fields = (
        ("peso_descarga", navio.peso_descarga),
        ("peso_embarque", navio.peso_embarque),
        ("volume_descarga", navio.volume_descarga),
        ("volume_embarque", navio.volume_embarque),
    )
    for field, raw_value in numeric_fields:
        if raw_value not in (None, ""):
            parsed = parse_localized_number(raw_value)
            if parsed is None:
                alerts.append(
                    _alert(
                        "valor_nao_numerico",
                        "media",
                        f"O campo {field.replace('_', ' ')} não contém um valor numérico reconhecível.",
                        (field,),
                    )
                )
            elif parsed < 0:
                alerts.append(
                    _alert(
                        "valor_negativo",
                        "alta",
                        f"O campo {field.replace('_', ' ')} possui valor negativo.",
                        (field,),
                    )
                )

    if navio.ternos is not None and navio.ternos <= 0:
        alerts.append(
            _alert(
                "ternos_invalidos",
                "alta",
                "A quantidade de ternos deve ser maior que zero.",
                ("ternos",),
            )
        )

    if (
        features["loa"] is not None
        and features["boca"] is not None
        and features["loa"] <= features["boca"]
    ):
        alerts.append(
            _alert(
                "dimensoes_inconsistentes",
                "alta",
                "O LOA deve ser maior que a boca do navio.",
                ("loa", "boca"),
            )
        )

    if duplicate:
        alerts.append(
            _alert(
                "possivel_duplicidade",
                "media",
                "Existe outro registro com o mesmo navio e a mesma ETA.",
                ("navio", "eta"),
            )
        )

    if navio.inicio_operacao and not navio.fim_operacao:
        alerts.append(
            _alert(
                "operacao_em_aberto",
                "baixa",
                "A operação possui início, mas ainda não possui horário de término.",
                ("fim_operacao",),
            )
        )
    elif not navio.inicio_operacao or not navio.fim_operacao:
        alerts.append(
            _alert(
                "dados_temporais_incompletos",
                "baixa",
                "Não há dados suficientes para calcular a duração da operação.",
                ("inicio_operacao", "fim_operacao"),
            )
        )

    alerts.sort(key=lambda item: (SEVERITY_ORDER[item["severidade"]], item["codigo"]))
    return alerts


def _normalized_name(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    return " ".join(
        normalized.encode("ascii", "ignore").decode("ascii").lower().split()
    )


def _duplicate_keys(navios):
    grouped = {}
    duplicates = {navio.pk: False for navio in navios}
    for navio in navios:
        name = _normalized_name(navio.navio)
        if name and navio.eta:
            grouped.setdefault(name, []).append(navio)
    for same_name in grouped.values():
        same_name.sort(key=lambda item: item.eta)
        for index, current in enumerate(same_name):
            for candidate in same_name[index + 1 :]:
                distance = candidate.eta - current.eta
                if distance > timedelta(hours=6):
                    break
                duplicates[current.pk] = True
                duplicates[candidate.pk] = True
    return duplicates


def _rule_score(alerts):
    weights = {"alta": 70, "media": 35, "baixa": 10}
    if not alerts:
        return 0
    values = sorted((weights[alert["severidade"]] for alert in alerts), reverse=True)
    return min(100, values[0] + sum(min(value, 15) for value in values[1:]))


def _risk(score):
    if score >= 70:
        return "alto"
    if score >= 35:
        return "medio"
    return "baixo"


def _robust_deviation(value, values):
    center = median(values)
    absolute_deviations = [abs(item - center) for item in values]
    mad = median(absolute_deviations)
    if mad > 0:
        return abs(0.6745 * (value - center) / mad)
    spread = max(values) - min(values)
    return abs(value - center) / spread if spread else 0.0


def _prepare_model_data(rows):
    eligible = [
        row
        for row in rows
        if row["features"]["duracao_operacao_horas"] is not None
        and row["features"]["duracao_operacao_horas"] > 0
        and sum(row["features"][feature] is not None for feature in MODEL_FEATURES) >= 4
        and not any(alert["severidade"] == "alta" for alert in row["alertas"])
    ]
    minimum_present = max(5, math.ceil(len(eligible) * 0.5)) if eligible else 5
    active_features = []
    distributions = {}
    for feature in MODEL_FEATURES:
        values = [
            row["features"][feature]
            for row in eligible
            if row["features"][feature] is not None
        ]
        if (
            len(values) >= minimum_present
            and len({round(value, 8) for value in values}) > 1
        ):
            active_features.append(feature)
            distributions[feature] = values
    return eligible, active_features, distributions


def _run_local_model(rows, statistical_minimum, ml_minimum, contamination):
    eligible, active_features, distributions = _prepare_model_data(rows)
    metadata = {
        "status": "coletando_dados",
        "algoritmo": "Regras explicáveis",
        "amostras": len(eligible),
        "minimo_amostras": statistical_minimum,
        "minimo_modelo_ml": ml_minimum,
        "recursos": [],
        "mensagem": f"São necessários pelo menos {statistical_minimum} registros com dados suficientes para ativar a análise estatística.",
    }
    if not getattr(settings, "INSIGHT_ML_ENABLED", True):
        metadata.update(
            status="desativado",
            mensagem="A análise estatística local está desativada pela configuração.",
        )
        return {}, metadata
    if len(eligible) < statistical_minimum:
        return {}, metadata

    if len(active_features) < 2:
        metadata.update(
            status="dados_insuficientes",
            mensagem="Os registros ainda não possuem variedade em pelo menos dois indicadores operacionais.",
        )
        return {}, metadata

    if len(eligible) < ml_minimum:
        analyses = {}
        for row in eligible:
            factors = []
            for feature in active_features:
                value = row["features"][feature]
                if value is None:
                    continue
                deviation = _robust_deviation(value, distributions[feature])
                factors.append((deviation, FEATURE_LABELS[feature]))
            factors.sort(reverse=True)
            maximum_deviation = factors[0][0] if factors else 0
            is_outlier = maximum_deviation >= 3.5
            score = (
                min(85, round(55 + min(30, (maximum_deviation - 3.5) * 8)))
                if is_outlier
                else 0
            )
            analyses[row["navio_id"]] = {
                "anomalo": is_outlier,
                "pontuacao": score,
                "fatores": [
                    label for deviation, label in factors[:3] if deviation >= 2.0
                ],
                "origem": "estatistica_local",
            }
        metadata.update(
            status="estatistica_robusta",
            algoritmo="Estatística robusta local (mediana/MAD)",
            minimo_amostras=ml_minimum,
            recursos=active_features,
            mensagem=f"Análise estatística local ativa. Com {ml_minimum} registros válidos, o Isolation Forest será habilitado.",
        )
        return analyses, metadata

    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        metadata.update(
            status="indisponivel",
            mensagem="A biblioteca scikit-learn não está instalada; as regras continuam ativas.",
        )
        return {}, metadata

    medians = {feature: median(distributions[feature]) for feature in active_features}
    matrix = [
        [
            row["features"][feature]
            if row["features"][feature] is not None
            else medians[feature]
            for feature in active_features
        ]
        for row in eligible
    ]
    fingerprint = sha256(
        repr((active_features, matrix, contamination)).encode("utf-8")
    ).hexdigest()
    try:
        with _MODEL_CACHE_LOCK:
            cached = _MODEL_CACHE.get(fingerprint)
            if cached is None:
                estimator = IsolationForest(
                    n_estimators=200,
                    contamination=contamination,
                    random_state=42,
                    n_jobs=1,
                )
                predictions = estimator.fit_predict(matrix)
                decisions = estimator.decision_function(matrix)
                _MODEL_CACHE.clear()
                _MODEL_CACHE[fingerprint] = (predictions, decisions)
            else:
                predictions, decisions = cached
    except Exception:  # noqa: BLE001 - falha do modelo nunca deve parar o sistema operacional
        logger.exception("Falha ao executar o modelo local do LOGGERAL Insight.")
        metadata.update(
            status="indisponivel",
            algoritmo="Regras explicáveis",
            mensagem="O modelo local não pôde ser calculado; as regras continuam funcionando normalmente.",
        )
        return {}, metadata
    raw_scores = [-float(value) for value in decisions]
    ordered_scores = sorted(raw_scores)
    analyses = {}

    for row, prediction, raw_score in zip(eligible, predictions, raw_scores):
        rank = sum(candidate <= raw_score for candidate in ordered_scores) / len(
            ordered_scores
        )
        is_outlier = int(prediction) == -1
        score = round(max(60, 60 + 40 * rank) if is_outlier else 0)
        factors = []
        for feature in active_features:
            value = row["features"][feature]
            if value is None:
                continue
            deviation = _robust_deviation(value, distributions[feature])
            factors.append((deviation, FEATURE_LABELS[feature], feature))
        factors.sort(reverse=True)
        analyses[row["navio_id"]] = {
            "anomalo": is_outlier,
            "pontuacao": min(100, score),
            "fatores": [
                label for deviation, label, _ in factors[:3] if deviation >= 1.5
            ],
            "origem": "modelo_local",
        }

    metadata.update(
        status="modelo_local_ativo",
        algoritmo="Isolation Forest local",
        amostras=len(eligible),
        minimo_amostras=ml_minimum,
        recursos=active_features,
        mensagem="Modelo treinado localmente com os registros disponíveis; nenhum dado foi enviado para a internet.",
    )
    return analyses, metadata


def analyze_navios(
    navios, *, statistical_minimum=None, ml_minimum=None, contamination=None
):
    navios = list(navios)
    statistical_minimum = int(
        statistical_minimum
        if statistical_minimum is not None
        else getattr(settings, "INSIGHT_STATISTICAL_MIN_SAMPLES", 30)
    )
    ml_minimum = int(
        ml_minimum
        if ml_minimum is not None
        else getattr(settings, "INSIGHT_ML_MIN_SAMPLES", 100)
    )
    statistical_minimum = max(10, statistical_minimum)
    ml_minimum = max(statistical_minimum, ml_minimum)
    contamination = float(
        contamination
        if contamination is not None
        else getattr(settings, "INSIGHT_CONTAMINATION", 0.1)
    )
    contamination = min(0.5, max(0.01, contamination))
    duplicates = _duplicate_keys(navios)

    rows = []
    for navio in navios:
        features = extract_features(navio)
        alerts = evaluate_rules(navio, features, duplicates.get(navio.pk, False))
        rows.append(
            {
                "navio_id": navio.pk,
                "navio": navio.navio or "Não informado",
                "armador": navio.armador or "Não informado",
                "agencia": navio.agencia or "Não informada",
                "eta": navio.eta.isoformat() if navio.eta else None,
                "features": features,
                "alertas": alerts,
                "pontuacao_regras": _rule_score(alerts),
            }
        )

    model_analyses, model_metadata = _run_local_model(
        rows, statistical_minimum, ml_minimum, contamination
    )
    for row in rows:
        model_result = model_analyses.get(
            row["navio_id"], {"anomalo": False, "pontuacao": 0, "fatores": []}
        )
        if model_result["anomalo"]:
            factors = model_result["fatores"] or [
                "combinação incomum dos indicadores operacionais"
            ]
            severity = "alta" if model_result["pontuacao"] >= 85 else "media"
            row["alertas"].append(
                {
                    "codigo": "padrao_operacional_atipico",
                    "severidade": severity,
                    "mensagem": "Padrão atípico identificado pelo modelo local: "
                    + ", ".join(factors)
                    + ".",
                    "campos": [],
                    "origem": model_result.get("origem", "modelo_local"),
                }
            )
            row["alertas"].sort(
                key=lambda item: (SEVERITY_ORDER[item["severidade"]], item["codigo"])
            )
        combined = max(row["pontuacao_regras"], model_result["pontuacao"])
        if row["pontuacao_regras"] and model_result["anomalo"]:
            combined = min(100, combined + 10)
        row["pontuacao"] = combined
        row["risco"] = _risk(combined)
        row["risco_rotulo"] = RISK_LABELS[row["risco"]]
        row["anomalia_modelo"] = model_result["anomalo"]
        row["fatores_modelo"] = model_result["fatores"]
        row["total_alertas"] = len(row["alertas"])

    rows.sort(
        key=lambda item: (
            -item["pontuacao"],
            item["navio"].lower(),
            item["navio_id"] or 0,
        )
    )
    summary = {
        "total": len(rows),
        "alto": sum(row["risco"] == "alto" for row in rows),
        "medio": sum(row["risco"] == "medio" for row in rows),
        "baixo": sum(row["risco"] == "baixo" for row in rows),
        "com_alertas": sum(bool(row["alertas"]) for row in rows),
    }
    return {"resultados": rows, "resumo": summary, "modelo": model_metadata}
