# Examples of prompts for MedTrust quick buttons

This file contains example prompt templates for the frontend quick buttons. The goal is to help the registrar ask a complete, operational question and make follow-up questions retain the original topic.

> Important: a template does not guarantee an answer. The result depends on the current Wiki content and, for questions requiring up-to-date external information, on whether SearXNG returns a relevant, approved source. MedTrust must not invent clinic rules, appointment availability, preparation instructions, or clinical recommendations. If the evidence is missing, it should report the gap or use the configured fallback.

## Suggested quick-button templates

### 1. Routing a patient to a specialist

**Button label:** `Куда записать пациента`

**Prompt:**

> Как записать пациента к {специалисту}, если причина обращения — {причина обращения}? Учитывай правила маршрутизации из Wiki MedTrust и укажи, что регистратору нужно уточнить.

**Example:** `Как записать пациента к травматологу, если он обратился с острой болью в колене?`

### 2. Patient already has a referral

**Button label:** `Есть направление`

**Prompt for a follow-up (send with the existing conversation_id):**

> По предыдущему вопросу о записи пациента к {специалисту} по поводу {причины обращения}: что меняется, если у пациента уже есть направление?

**Example:** `По предыдущему вопросу о записи к травматологу из-за острой боли в колене: что меняется, если у пациента уже есть направление?`

### 3. Repeat or previous visit

**Button label:** `Повторное обращение`

**Prompt:**

> Как действовать регистратору, если пациент повторно обращается по поводу {причины обращения}? Какие условия предыдущего обращения нужно уточнить согласно Wiki MedTrust?

**Follow-up pattern:** `По предыдущему вопросу о {теме}: если пациент уже обращался ранее, как меняется порядок записи?`

### 4. Injury occurred several days ago

**Button label:** `Срок после травмы`

**Prompt:**

> Что меняется в маршрутизации пациента, если травма произошла {срок назад}? Укажи условия из Wiki MedTrust и какие сведения нужно уточнить перед записью.

**Example:** `Что меняется, если травма произошла несколько дней назад?`

### 5. Preparation for a procedure from the clinic's instructions

**Button label:** `Подготовка к процедуре`

**Prompt:**

> Что регистратор должен сообщить пациенту о подготовке к {процедуре/исследованию} согласно Wiki MedTrust? Перечисли только подтверждённые ограничения и документы; отдельно укажи, если инструкция зависит от назначения врача или типа процедуры.

**Example:** `Что указано в Wiki MedTrust о подготовке к КТ?`

### 6. Ongoing medication or another safety-sensitive detail

**Button label:** `Постоянные лекарства`

**Prompt for a follow-up (send with the existing conversation_id):**

> По предыдущему вопросу о подготовке к {процедуре}: что указано для пациента, который постоянно принимает лекарства? Не предполагай, что общая памятка покрывает это условие; проверь отдельное подтверждение в Wiki или надёжном внешнем источнике.

**Example:** `По предыдущему вопросу об ограничениях перед процедурой под седацией: что делать, если пациент принимает постоянные лекарства?`

**Expected behavior:** if the knowledge base and accepted web results do not cover this detail, the system must not invent an instruction. It should explicitly report the evidence gap.

### 7. Rephrase the last answer

**Button label:** `Сделать ответ короче`

**Prompt for a follow-up (send with the existing conversation_id):**

> Сформулируй предыдущий ответ более коротко и вежливо, сохранив смысл инструкции, все условия, ограничения и ссылки на источники.

**Expected behavior:** this is a text-editing request, not a new knowledge search. The previous assistant answer should be sent to GigaChat together with the editing instruction; no new Wiki/web retrieval should run. If the previous answer is the exact fail-closed message `нужные данные не найдены`, keep that message unchanged.

### 8. Current clinical recommendations

**Button label:** `Актуальные рекомендации`

**Prompt:**

> Какие актуальные официальные рекомендации опубликованы по {клинической теме} для {группы пациентов}? Используй свежие проверяемые источники; отличай рекомендации профильной организации от информации из Wiki MedTrust.

**Example:** `Какие современные рекомендации по диагностике мигрени у взрослых?`

**Expected behavior:** always require online verification. If no relevant source passes validation, return `нужные данные не найдены`. This is a safe fallback, not proof that the topic has no recommendations.

### 9. Compare the local instruction with current external guidance

**Button label:** `Wiki и актуальные рекомендации`

**Prompt:**

> Что указано в Wiki MedTrust о подготовке к {процедуре/исследованию}, и какие актуальные рекомендации по этой подготовке публикуют профильные медицинские организации? Раздели ответ на две части: сведения из Wiki и сведения из внешнего источника. Если подтверждена только одна часть, всё равно изложи её и явно отметь, что не удалось подтвердить.

**Example:** `Что указано в Wiki о подготовке к процедуре КТ и какие актуальные рекомендации по этой подготовке публикует профильная медицинская организация?`

**Expected behavior:** answer the supported Wiki part even if no current external source is found; do not present the missing current-guidance part as verified.

### 10. Ask how a changed condition affects the answer

**Button label:** `Уточнить условие`

**Prompt for a follow-up (send with the existing conversation_id):**

> По предыдущему вопросу о {теме/маршрутизации}: что меняется, если {новое условие}? Укажи только те отличия, которые подтверждены источниками.

**Example:** `По предыдущему вопросу о маршрутизации после травмы: что меняется, если травма произошла несколько дней назад?`

## Frontend integration notes

- A follow-up or an editing instruction must be sent with the same `conversation_id` as the original question. Without it, MedTrust cannot reliably know which answer the user is clarifying or editing.
- For ordinary quick buttons, put the clinic-specific context in the prompt itself (`{specialist}`, `{service}`, `{procedure}`, `{reason}`, `{condition}`); do not rely on an implicit topic known only to the frontend.
- The UI should present `нужные данные не найдены` or an uncovered-evidence note as a limitation of the available verified sources, not as a clinical conclusion that no guideline or instruction exists.
- Never show a made-up specialist, appointment time, preparation restriction, medicine instruction, or external reference when no source supports it.
