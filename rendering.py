from __future__ import annotations

from .wiki_service import RestraintProfile, SkillEntry, WikiEntry


WIKI_CARD_TEMPLATE = """
<html>
<head>
  <meta charset="utf-8" />
  <style>
    html, body {
      margin: 0;
      padding: 0;
      overflow: hidden;
    }

    :root {
      --bg: linear-gradient(135deg, #f8f6ef 0%, #eef7ff 55%, #fff3ea 100%);
      --panel: rgba(255, 255, 255, 0.92);
      --text: #1f2a37;
      --muted: #526071;
      --line: rgba(59, 88, 120, 0.14);
      --accent: #0f766e;
      --accent-soft: rgba(15, 118, 110, 0.12);
      --chip: #f4efe2;
      --shadow: 0 20px 50px rgba(31, 42, 55, 0.12);
    }

    * { box-sizing: border-box; }

    body {
      font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
      background: var(--bg);
      color: var(--text);
    }

    .page {
      width: 1180px;
      padding: 24px 12px 24px 108px;
    }

    .card {
      position: relative;
      overflow: hidden;
      border-radius: 28px;
      padding: 28px 30px;
      background: var(--panel);
      border: 1px solid rgba(255, 255, 255, 0.75);
      box-shadow: var(--shadow);
    }

    .card::before {
      content: "";
      position: absolute;
      inset: 0;
      background:
        radial-gradient(circle at top right, rgba(15, 118, 110, 0.14), transparent 36%),
        radial-gradient(circle at bottom left, rgba(249, 115, 22, 0.12), transparent 32%);
      pointer-events: none;
    }

    .topbar {
      display: grid;
      grid-template-columns: 1fr;
      gap: 18px;
      position: relative;
      z-index: 1;
      align-content: start;
    }

    .hero-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 18px;
    }

    .hero-main {
      min-width: 0;
      flex: 1 1 auto;
    }

    .hero {
      display: grid;
      grid-template-columns: 260px auto;
      gap: 24px;
      align-items: start;
      position: relative;
      z-index: 1;
      width: fit-content;
      margin-left: 36px;
    }

    .hero.no-image {
      grid-template-columns: 1fr;
      width: auto;
      margin-left: 0;
    }

    .preview-wrap {
      border-radius: 24px;
      background: linear-gradient(180deg, rgba(255,255,255,0.9), rgba(240,248,255,0.92));
      border: 1px solid var(--line);
      min-height: 250px;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 16px;
      overflow: hidden;
    }

    .preview-wrap img {
      width: 100%;
      height: 100%;
      max-height: 320px;
      object-fit: contain;
      display: block;
    }

    .eyebrow {
      display: inline-block;
      padding: 8px 14px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 20px;
      font-weight: 700;
      letter-spacing: 0.04em;
    }

    h1 {
      margin: 14px 0 0;
      font-size: 52px;
      line-height: 1.08;
    }

    .type-list {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }

    .type-chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      border-radius: 999px;
      background: var(--chip);
      border: 1px solid rgba(31, 42, 55, 0.08);
      font-size: 22px;
      font-weight: 700;
    }

    .type-chip img {
      width: 36px;
      height: 36px;
      object-fit: contain;
      display: block;
    }

    .variant-gallery {
      flex: 0 0 auto;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      min-width: 438px;
    }

    .variant-card {
      padding: 10px;
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.78);
      border: 1px solid var(--line);
      box-shadow: 0 10px 24px rgba(31, 42, 55, 0.08);
    }

    .variant-label {
      margin-bottom: 6px;
      font-size: 16px;
      color: var(--muted);
      font-weight: 700;
      text-align: center;
    }

    .variant-figure {
      width: 100%;
      height: 108px;
      border-radius: 16px;
      background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(247,243,255,0.92));
      border: 1px solid rgba(15, 118, 110, 0.10);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 10px;
      overflow: hidden;
    }

    .variant-figure img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }

    .evo-panel {
      display: flex;
      align-items: center;
      gap: 18px;
      padding: 18px 20px;
      border-radius: 22px;
      background: rgba(255, 255, 255, 0.76);
      border: 1px solid var(--line);
      width: fit-content;
      max-width: 100%;
    }

    .evo-title {
      margin: 0;
      font-size: 22px;
      color: var(--muted);
      font-weight: 700;
      flex: 0 0 auto;
    }

    .evo-chain {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 14px;
    }

    .evo-node {
      width: 112px;
      height: 112px;
      padding: 10px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid rgba(15, 118, 110, 0.12);
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }

    .evo-node img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }

    .evo-arrow {
      font-size: 36px;
      color: var(--accent);
      font-weight: 700;
      line-height: 1;
    }

    .summary {
      position: relative;
      z-index: 1;
      margin-top: 20px;
      padding: 20px 22px;
      border-radius: 22px;
      background: rgba(255, 255, 255, 0.78);
      border: 1px solid var(--line);
      font-size: 24px;
      line-height: 1.6;
      white-space: pre-wrap;
    }

    .grid {
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-top: 18px;
    }

    .meta-panel {
      position: relative;
      z-index: 1;
      margin-top: 18px;
      padding: 20px 22px;
      border-radius: 22px;
      background: rgba(255, 255, 255, 0.82);
      border: 1px solid var(--line);
    }

    .meta-title {
      margin: 0 0 16px;
      font-size: 28px;
    }

    .total-species {
      display: inline-flex;
      align-items: baseline;
      gap: 10px;
      margin-bottom: 16px;
      padding: 10px 16px;
      border-radius: 999px;
      background: rgba(15, 118, 110, 0.1);
      border: 1px solid rgba(15, 118, 110, 0.14);
    }

    .total-species-label {
      font-size: 18px;
      color: var(--muted);
    }

    .total-species-value {
      font-size: 30px;
      font-weight: 700;
      color: var(--accent);
    }

    .stat-grid {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 12px;
    }

    .stat-item {
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(244, 239, 226, 0.55);
      border: 1px solid rgba(31, 42, 55, 0.08);
    }

    .stat-label {
      font-size: 18px;
      color: var(--muted);
    }

    .stat-value {
      margin-top: 6px;
      font-size: 26px;
      font-weight: 700;
      color: var(--text);
    }

    .profile-list {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 16px;
    }

    .profile-chip {
      padding: 10px 16px;
      border-radius: 999px;
      background: rgba(15, 118, 110, 0.08);
      color: var(--text);
      font-size: 20px;
      border: 1px solid rgba(15, 118, 110, 0.12);
    }

    .panel {
      padding: 20px 22px;
      border-radius: 22px;
      background: rgba(255, 255, 255, 0.82);
      border: 1px solid var(--line);
      min-height: 170px;
    }

    .panel h2 {
      margin: 0 0 14px;
      font-size: 28px;
    }

    .trait-name {
      display: inline-flex;
      align-items: center;
      gap: 14px;
      font-size: 28px;
      font-weight: 700;
      color: var(--accent);
      margin-bottom: 10px;
    }

    .trait-name img {
      width: 68px;
      height: 68px;
      object-fit: contain;
      display: block;
      border-radius: 18px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(237, 248, 246, 0.96) 100%);
      border: 1px solid rgba(15, 118, 110, 0.14);
      box-shadow: 0 8px 20px rgba(15, 118, 110, 0.08);
      padding: 4px;
    }

    .trait-desc {
      font-size: 22px;
      line-height: 1.7;
      color: var(--muted);
      white-space: pre-wrap;
    }

    .restraint-row {
      display: grid;
      grid-template-columns: 120px 1fr;
      gap: 10px;
      align-items: start;
      padding: 10px 0;
      border-top: 1px solid var(--line);
    }

    .restraint-row:first-of-type {
      border-top: 0;
      padding-top: 0;
    }

    .restraint-label {
      font-size: 22px;
      font-weight: 700;
      color: var(--accent);
    }

    .restraint-value {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      font-size: 22px;
      line-height: 1.7;
      color: var(--muted);
    }

    .restraint-item {
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    .restraint-item img {
      width: 28px;
      height: 28px;
      object-fit: contain;
      display: block;
    }

    .footer {
      position: relative;
      z-index: 1;
      margin-top: 14px;
      font-size: 18px;
      color: #6b7280;
      word-break: break-all;
    }
  </style>
</head>
<body>
  <div class="page">
    <div class="card">
      <div class="hero{% if not image_url %} no-image{% endif %}">
        {% if image_url %}
        <div class="preview-wrap">
          <img src="{{ image_url }}" alt="{{ title }}" />
        </div>
        {% endif %}

        <div class="topbar">
          <div class="hero-head">
            <div class="hero-main">
              <div class="eyebrow">洛克王国世界 Wiki</div>
              <h1>{{ title }}</h1>
              {% if types %}
              <div class="type-list">
                {% for item in type_items %}
                <div class="type-chip">
                  {% if item.icon_url %}
                  <img src="{{ item.icon_url }}" alt="{{ item.name }}" />
                  {% endif %}
                  <span>{{ item.name }}</span>
                </div>
                {% endfor %}
              </div>
              {% endif %}
            </div>
            {% if variant_items %}
            <div class="variant-gallery">
              {% for item in variant_items %}
              <div class="variant-card">
                <div class="variant-label">{{ item.label }}</div>
                <div class="variant-figure">
                  <img src="{{ item.image_url }}" alt="{{ title }}-{{ item.key }}" />
                </div>
              </div>
              {% endfor %}
            </div>
            {% endif %}
          </div>
          {% if evolution_image_urls %}
          <div class="evo-panel">
            <div class="evo-title">进化链</div>
            <div class="evo-chain">
              {% for item in evolution_image_urls %}
              <div class="evo-node"><img src="{{ item }}" alt="evolution-node-{{ loop.index }}" /></div>
              {% if not loop.last %}
              <div class="evo-arrow">→</div>
              {% endif %}
              {% endfor %}
            </div>
          </div>
          {% endif %}
        </div>
      </div>

      <div class="summary">{{ summary }}</div>

      {% if stats or profile_fields %}
      <div class="meta-panel">
        <h2 class="meta-title">基础数据</h2>
        {% if total_species_value %}
        <div class="total-species">
          <div class="total-species-label">种族值</div>
          <div class="total-species-value">{{ total_species_value }}</div>
        </div>
        {% endif %}
        {% if stats %}
        <div class="stat-grid">
          {% for item in stats %}
          <div class="stat-item">
            <div class="stat-label">{{ item.label }}</div>
            <div class="stat-value">{{ item.value }}</div>
          </div>
          {% endfor %}
        </div>
        {% endif %}
        {% if profile_fields %}
        <div class="profile-list">
          {% for item in profile_fields %}
          <div class="profile-chip">{{ item.label }}：{{ item.value }}</div>
          {% endfor %}
        </div>
        {% endif %}
      </div>
      {% endif %}

      <div class="grid">
        <div class="panel">
          <h2>特性</h2>
          {% if trait_name %}
          <div class="trait-name">
            {% if trait_icon_url %}
            <img src="{{ trait_icon_url }}" alt="{{ trait_name }}" />
            {% endif %}
            <span>{{ trait_name }}</span>
          </div>
          {% endif %}
          <div class="trait-desc">{{ trait_desc or '该词条暂时没有提取到特性描述。' }}</div>
        </div>

        <div class="panel">
          <h2>克制表</h2>
          {% for row in restraint_rows %}
          <div class="restraint-row">
            <div class="restraint-label">{{ row.label }}</div>
            <div class="restraint-value">
              {% for item in row.entries %}
              <span class="restraint-item">
                {% if item.icon_url %}
                <img src="{{ item.icon_url }}" alt="{{ item.name }}" />
                {% endif %}
                <span>{{ item.name }}</span>
              </span>
              {% endfor %}
              {% if not row.entries %}
              <span class="restraint-item">暂无</span>
              {% endif %}
            </div>
          </div>
          {% endfor %}
        </div>
      </div>

      <div class="footer">词条链接：{{ url }}</div>
    </div>
  </div>
</body>
</html>
"""


def build_card_context(entry: WikiEntry) -> dict:
    restraint = entry.restraint or RestraintProfile()
    variant_items = [
        {"key": "shiny", "label": "异色展示", "image_url": entry.shiny_image_url},
        {"key": "egg", "label": "精灵蛋", "image_url": entry.egg_image_url},
        {"key": "fruit", "label": "果实", "image_url": entry.fruit_image_url},
    ]
    restraint_rows = (
        [
            {
                "label": row.label,
                "entries": [{"name": name, "icon_url": icon_url} for name, icon_url in row.items],
            }
            for row in entry.restraint_icon_rows
        ]
        if entry.restraint_icon_rows
        else [
            {"label": "克制", "entries": [{"name": name, "icon_url": ""} for name in restraint.restrain]},
            {"label": "被克制", "entries": [{"name": name, "icon_url": ""} for name in restraint.restrained_by]},
            {"label": "抵抗", "entries": [{"name": name, "icon_url": ""} for name in restraint.resist]},
            {"label": "被抵抗", "entries": [{"name": name, "icon_url": ""} for name in restraint.resisted_by]},
        ]
    )
    return {
        "title": entry.title,
        "image_url": entry.image_url,
        "shiny_image_url": entry.shiny_image_url,
        "variant_items": [item for item in variant_items if item["image_url"]],
        "types": entry.types,
        "type_items": [
            {"name": name, "icon_url": icon_url}
            for name, icon_url in (entry.type_icons or [(type_name, "") for type_name in entry.types])
        ],
        "evolution_chain": entry.evolution_chain,
        "evolution_image_urls": entry.evolution_image_urls,
        "summary": entry.summary or entry.snippet or "该词条暂时没有可提取的摘要内容。",
        "total_species_value": entry.total_species_value,
        "stats": [{"label": label, "value": value} for label, value in entry.stats],
        "profile_fields": [{"label": label, "value": value} for label, value in entry.profile_fields],
        "trait_name": entry.trait_name,
        "trait_icon_url": entry.trait_icon_url,
        "trait_desc": entry.trait_desc,
        "restraint_rows": restraint_rows,
        "url": entry.url,
    }


SKILL_CARD_TEMPLATE = """
<html>
<head>
  <meta charset="utf-8" />
  <style>
    html, body {
      margin: 0;
      padding: 0;
      overflow: hidden;
    }

    :root {
      --bg: linear-gradient(135deg, #f7f4ec 0%, #ecf7f6 50%, #fef6ee 100%);
      --panel: rgba(255, 255, 255, 0.94);
      --text: #1f2a37;
      --muted: #5b6778;
      --accent: #0f766e;
      --line: rgba(59, 88, 120, 0.14);
      --shadow: 0 20px 50px rgba(31, 42, 55, 0.12);
      --chip: #f5efe2;
    }

    * { box-sizing: border-box; }

    body {
      font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
      background: var(--bg);
      color: var(--text);
    }

    .page {
      width: 1200px;
      padding: 65px 50px 50px 128px;
    }

    .card {
      position: relative;
      overflow: hidden;
      border-radius: 28px;
      padding: 30px;
      background: var(--panel);
      border: 1px solid rgba(255, 255, 255, 0.78);
      box-shadow: var(--shadow);
    }

    .card::before {
      content: "";
      position: absolute;
      inset: 0;
      background:
        radial-gradient(circle at top right, rgba(15, 118, 110, 0.12), transparent 34%),
        radial-gradient(circle at bottom left, rgba(249, 115, 22, 0.10), transparent 30%);
      pointer-events: none;
    }

    .hero {
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: 140px 1fr;
      gap: 22px;
      align-items: start;
    }

    .hero.no-image {
      grid-template-columns: 1fr;
    }

    .skill-icon {
      width: 140px;
      height: 140px;
      padding: 12px;
      border-radius: 26px;
      background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(237,248,246,0.94));
      border: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .skill-icon img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }

    .eyebrow {
      display: inline-block;
      padding: 8px 14px;
      border-radius: 999px;
      background: rgba(15, 118, 110, 0.12);
      color: var(--accent);
      font-size: 20px;
      font-weight: 700;
    }

    h1 {
      margin: 14px 0 0;
      font-size: 52px;
      line-height: 1.08;
    }

    .meta-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 18px;
    }

    .chip {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 10px 16px;
      border-radius: 999px;
      background: var(--chip);
      border: 1px solid rgba(31, 42, 55, 0.08);
      font-size: 22px;
      font-weight: 700;
    }

    .chip img {
      width: 34px;
      height: 34px;
      object-fit: contain;
      display: block;
    }

    .stat-row {
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
      margin-top: 20px;
    }

    .stat-card, .panel {
      border-radius: 22px;
      background: rgba(255, 255, 255, 0.8);
      border: 1px solid var(--line);
    }

    .stat-card {
      padding: 18px 20px;
    }

    .stat-label {
      font-size: 20px;
      color: var(--muted);
      margin-bottom: 8px;
    }

    .stat-value {
      font-size: 36px;
      font-weight: 700;
      color: var(--accent);
    }

    .grid {
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 16px;
      margin-top: 18px;
    }

    .panel {
      padding: 22px;
    }

    .panel h2 {
      margin: 0 0 14px;
      font-size: 28px;
    }

    .effect {
      font-size: 24px;
      line-height: 1.65;
      white-space: pre-wrap;
    }

    .learner-list {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .learner-chip {
      padding: 8px 14px;
      border-radius: 999px;
      background: rgba(15, 118, 110, 0.08);
      border: 1px solid rgba(15, 118, 110, 0.12);
      font-size: 20px;
    }

    .footer {
      position: relative;
      z-index: 1;
      margin-top: 18px;
      font-size: 18px;
      color: var(--muted);
      word-break: break-all;
    }
  </style>
</head>
<body>
  <div class="page">
    <div class="card">
      <div class="hero{% if not skill_icon_url %} no-image{% endif %}">
        {% if skill_icon_url %}
        <div class="skill-icon"><img src="{{ skill_icon_url }}" alt="{{ title }}" /></div>
        {% endif %}
        <div>
          <div class="eyebrow">洛克王国世界 Wiki 技能</div>
          <h1>{{ title }}</h1>
          <div class="meta-chips">
            {% if type_name %}
            <div class="chip">
              {% if type_icon_url %}<img src="{{ type_icon_url }}" alt="{{ type_name }}" />{% endif %}
              <span>{{ type_name }}</span>
            </div>
            {% endif %}
            {% if category_name %}
            <div class="chip">
              {% if category_icon_url %}<img src="{{ category_icon_url }}" alt="{{ category_name }}" />{% endif %}
              <span>{{ category_name }}</span>
            </div>
            {% endif %}
          </div>
        </div>
      </div>

      <div class="stat-row">
        <div class="stat-card">
          <div class="stat-label">耗能</div>
          <div class="stat-value">{{ cost or '暂无' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">技能威力</div>
          <div class="stat-value">{{ power or '暂无' }}</div>
        </div>
      </div>

      <div class="grid">
        <div class="panel">
          <h2>技能效果</h2>
          <div class="effect">{{ effect or snippet or '该技能词条暂时没有提取到技能效果。' }}</div>
        </div>
        <div class="panel">
          <h2>可学精灵</h2>
          <div class="learner-list">
            {% for learner in learners %}
            <span class="learner-chip">{{ learner }}</span>
            {% endfor %}
            {% if not learners %}
            <span class="learner-chip">暂无</span>
            {% endif %}
          </div>
        </div>
      </div>

      <div class="footer">词条链接: {{ url }}</div>
    </div>
  </div>
</body>
</html>
"""


def build_skill_card_context(entry: SkillEntry) -> dict:
    return {
        "title": entry.title,
        "skill_icon_url": entry.skill_icon_url,
        "type_name": entry.type_name,
        "type_icon_url": entry.type_icon_url,
        "category_name": entry.category_name,
        "category_icon_url": entry.category_icon_url,
        "cost": entry.cost,
        "power": entry.power,
        "effect": entry.effect,
        "snippet": entry.snippet,
        "learners": entry.learners[:10],
        "url": entry.url,
    }


def _join_or_fallback(values: list[str]) -> str:
    return "、".join(values) if values else "暂无"
