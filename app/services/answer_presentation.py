"""Formatting and safe no-evidence messages for registrar-facing answers."""
from __future__ import annotations

import re


def renumber_ordered_lists(answer: str) -> str:
    """Renumber Markdown ordered lists consistently, even when items have blank lines.

    A blank line between list items is valid Markdown and should not restart the list.
    A normal paragraph or heading does start a new list context.
    """
    output: list[str] = []
    counters: dict[int, int] = {}
    pattern = re.compile(r"^(\s*)(\d+)([.)])(\s+.*)$")

    for line in (answer or "").splitlines():
        if not line.strip():
            output.append(line)
            continue

        match = pattern.match(line)
        if match:
            indent, _number, punctuation, rest = match.groups()
            depth = len(indent.expandtabs(4))
            for old_depth in [value for value in counters if value > depth]:
                counters.pop(old_depth, None)
            counters[depth] = counters.get(depth, 0) + 1
            output.append(f"{indent}{counters[depth]}{punctuation}{rest}")
            continue

        stripped = line.lstrip()
        if stripped.startswith("#"):
            counters.clear()
        elif not stripped.startswith(("- ", "* ", "+ ")):
            # Any intervening prose ends the previous ordered list. Blank lines alone
            # do not: Markdown commonly separates ordered list items with blank lines.
            counters.clear()
        output.append(line)

    return "\n".join(output).strip()


def ensure_bullet_format(answer: str) -> str:
    """Convert standalone prose paragraphs to bullets while preserving Markdown lists."""
    text = (answer or "").strip()
    if not text:
        return text
    output: list[str] = []
    paragraph: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        if not paragraph:
            return
        content = " ".join(part.strip() for part in paragraph).strip()
        if content:
            if re.match(r"^(?:[-*+]\s+|\d+[.)]\s+|\|)", content):
                output.append(content)
            else:
                output.append(f"- {content}")
        paragraph.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            in_code = not in_code
            output.append(line)
            continue
        if in_code:
            output.append(line)
            continue
        if not stripped:
            flush_paragraph()
            if output and output[-1] != "":
                output.append("")
            continue
        if stripped.startswith("#") or re.match(r"^(?:[-*+]\s+|\d+[.)]\s+|\|)", stripped):
            flush_paragraph()
            output.append(line)
            continue
        paragraph.append(line)

    flush_paragraph()
    while output and not output[-1].strip():
        output.pop()
    return renumber_ordered_lists("\n".join(output).strip())


def safe_no_evidence_response(question: str) -> str:
    """Explain local Wiki evidence gaps without implying an external search occurred."""
    value = (question or "").casefold().replace("ё", "е")
    price_intent = bool(re.search(
        r"цен\w*|стоимост\w*|сколько\s+стоит|почем|тариф\w*|price|cost|pricing", value
    ))
    contraindication_intent = bool(re.search(
        r"противопоказ\w*|кому\s+нельзя|когда\s+нельзя|что\s+нельзя|"
        r"contraindicat\w*|who\s+should\s+not|safety\s+concern", value
    ))

    if price_intent:
        service = "гастроскопии" if re.search(r"гастроскоп\w*|фгдс|эзофагогастродуоденоскоп\w*", value) else "указанной услуги"
        return (
            f"В локальной базе знаний MedTrust не удалось найти материал, "
            f"подтверждающий стоимость {service}. Не могу назвать цену без прайс-листа конкретной "
            "клиники. Уточните тариф у регистратуры выбранной клиники."
        )

    if contraindication_intent:
        is_mri = bool(re.search(r"\bмрт\b|магнитно.?резонанс", value))
        procedure = "МРТ с контрастированием" if is_mri else "указанной процедуры"
        responsible = (
            "кабинета МРТ или врача-рентгенолога" if is_mri
            else "ответственного медицинского специалиста"
        )
        return (
            "В локальной базе знаний MedTrust не найден материал, "
            f"подтверждающий перечень противопоказаний именно для {procedure}. Чтобы не вводить "
            "в заблуждение, не буду перечислять неподтверждённые ограничения. Перед записью "
            f"уточните актуальные требования у {responsible}."
        )

    return (
        "В локальной базе знаний MedTrust не найдено достаточно материалов для подтверждения ответа. "
        "Чтобы не вводить в заблуждение, не буду приводить неподтверждённые утверждения. "
        "Проверьте внутреннюю инструкцию или уточните вопрос у ответственного специалиста."
    )
