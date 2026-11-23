---
id: case_sea_khmu_0002162
title: Khmu 录音目录 · Histoire khamoue de Cheuang
aliases:
- Histoire khamoue de Cheuang
- Khmu Cheuang story
node_type: case
z_layer: 1
genre: unclassified
credibility_tier: B
is_fictional_quarantine: false
spatial:
  lat: null
  lng: null
  precision: culture_region
  location_name: Khmu 语馆藏（单条录音地点待核）
  culture_region: Khmu 语录音馆藏
temporal: null
standards:
  atu_types: []
  thompson_motifs: []
  berezkin_codes: []
  ocm_codes: []
  macro_phylogeny: null
mechanisms: []
relations:
- type: PART_OF_MACRO_TREND
  target: corpus_sea_khmu_pangloss
  weight: 1.0
  note: 同一馆藏目录的录音资源；不表示同一故事、采录地点或传播关系。
  status: null
- type: COMPARED_WITH
  target: case_sea_khmu_0001986
  weight: 1.0
  note: 目录题名涉及 Chuang 或 Cheuang，但包含叙事、访谈和问答等不同材料；不能视为同一故事或历史事件。
  status: null
sources:
- citation: CNRS-LACITO，Pangloss Khmu 馆藏目录，保留目录网页快照。
  type: pangloss_khmu_catalogue
  url: https://pangloss.cnrs.fr/corpus/Khmu
  doi: null
  locator: Khmu / DOI 0002162
  local_path: .local/import-sources/asia-sea-pangloss-khmu-2026-11-22.html
  content_sha256: 392ee320fd8fce58fd67d4fa65eb085d2d90a0b23b0bf26c63feb2e2188065ee
- citation: CNRS-LACITO，Pangloss 单条录音元数据；具体许可见原字段。
  type: pangloss_khmu_detail
  url: https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-7507cc66-05cc-3c73-b5c1-b9af23e2b716&corpus=Khmu
  doi: 10.24397/pangloss-0002162
  locator: 录音 0002162
  local_path: .local/import-sources/pangloss-khmu-detail-2026-11-22-v1/records/0002162/page.html
  content_sha256: a827f3cebc21f21ce15cc8b0bf2b89e0955ab5980abdb359d9b45311cf1f331b
- citation: Astraia 首轮详情选取索引；分组只表示选取方法。
  type: pangloss_khmu_selection
  url: https://pangloss.cnrs.fr/corpus/Khmu
  doi: null
  locator: 目录题名含 Chuang 或 Cheuang 的录音
  local_path: reference/khmu_first_detail_selection.json
  content_sha256: 0bab5d7331a8fc6d9dd1a6e79cb996238a984e8941cb98ba5596f409ad6c0592
- citation: Astraia 目录字段对照索引；关系仅供人工核查。
  type: pangloss_khmu_comparison
  url: https://pangloss.cnrs.fr/corpus/Khmu
  doi: null
  locator: Chuang / Cheuang：题名主题对照候选
  local_path: reference/khmu_recording_comparisons.json
  content_sha256: 84ebd4f33a287c9bfbe97e84ca08b007c69538772b1ba06de2f6b0b162bfe270
audit:
  created_at: '2026-11-22'
  reviewed_by_human: false
  ai_confidence: null
  is_sample: false
  reviewer: null
  reviewed_at: null
  review_note: null
---

## 馆方录音目录字段

```
{
  "馆方目录题名": "Histoire khamoue de Cheuang",
  "馆方目录研究者": "Ferlus, Michel — Sy Sayarack, David",
  "馆方目录讲述者": "A local erudite",
  "馆方目录录音日期": "1970",
  "馆方时长": "00:07:24",
  "馆方媒介图标": [
    "audio"
  ],
  "馆方转写图标": false,
  "详情采集状态": "已保存并核验详情元数据",
  "详情选取依据": "目录题名含 Chuang 或 Cheuang 的录音",
  "馆方详情字段": {
    "alternate_titles": [
      {
        "language_as_displayed": "(en)",
        "title": "Khmu Cheuang story"
      }
    ],
    "researchers": "Ferlus, Michel; Sy Sayarack, David",
    "speakers": "A local erudite",
    "recorded": "1970",
    "recording_location": "Vientiane",
    "deposit_affiliation": "Centre de recherches linguistiques sur l'Asie orientale",
    "license": "http://spdx.org/licenses/CC-BY-NC-SA-2.5"
  },
  "目录与详情研究者字段是否对应": true,
  "目录与详情讲述者字段是否对应": true,
  "目录与详情录音日期是否一致": true
}
```

## 目录对照候选（待复核）

```
{
  "id": "chuang_topic",
  "label": "Chuang / Cheuang：题名主题对照候选",
  "note": "目录题名涉及 Chuang 或 Cheuang，但包含叙事、访谈和问答等不同材料；不能视为同一故事或历史事件。",
  "members": [
    {
      "id": "0001986",
      "title": "Histoire de Chuang aux pouvoirs magnifiques",
      "speakers": "unknown",
      "recorded": "1965",
      "doi": "https://doi.org/10.24397/pangloss-0001986",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-81b0152c-646d-30cf-a9fa-c85402f14687&corpus=Khmu",
      "node_id": "case_sea_khmu_0001986"
    },
    {
      "id": "0002058",
      "title": "Histoire de Chuang",
      "speakers": "Kham Mi",
      "recorded": "1967-07-03",
      "doi": "https://doi.org/10.24397/pangloss-0002058",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-b2bacfa9-b3eb-32f8-838b-8efe9439ba04&corpus=Khmu",
      "node_id": "case_sea_khmu_0002058"
    },
    {
      "id": "0002059",
      "title": "Questionnaire sur l'Histoire de Chuang (fin)",
      "speakers": "Kham Mi",
      "recorded": "1967-07-03",
      "doi": "https://doi.org/10.24397/pangloss-0002059",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-daf17b88-fb7b-3477-8568-cb1837c6c7f4&corpus=Khmu",
      "node_id": "case_sea_khmu_0002059"
    },
    {
      "id": "0002085",
      "title": "Histoire khamoue des jarres du Chuang",
      "speakers": "Ma' Mouan",
      "recorded": "1970-06-07",
      "doi": "https://doi.org/10.24397/pangloss-0002085",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-f97a42a4-c292-30b2-9d87-dcba9cc6eb38&corpus=Khmu",
      "node_id": "case_sea_khmu_0002085"
    },
    {
      "id": "0002103",
      "title": "Entretien sur le mouvement messianique Chuang",
      "speakers": "Cha Khoun",
      "recorded": "1970-08",
      "doi": "https://doi.org/10.24397/pangloss-0002103",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-9bbc0895-c4af-36ab-9a99-48f1ab4ab955&corpus=Khmu",
      "node_id": "case_sea_khmu_0002103"
    },
    {
      "id": "0002128",
      "title": "Histoire khamoue des amulettes Chuang",
      "speakers": "Cha Khoun",
      "recorded": "1970-09-07",
      "doi": "https://doi.org/10.24397/pangloss-0002128",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-2e7bea87-4625-32b7-965d-1b66b1781a5a&corpus=Khmu",
      "node_id": "case_sea_khmu_0002128"
    },
    {
      "id": "0002161",
      "title": "Questionnaire sur les rites de Cheuang",
      "speakers": "unknown",
      "recorded": "1970",
      "doi": "https://doi.org/10.24397/pangloss-0002161",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-13f1349f-58df-34c1-9a42-e8bc5b3d3af9&corpus=Khmu",
      "node_id": "case_sea_khmu_0002161"
    },
    {
      "id": "0002162",
      "title": "Histoire khamoue de Cheuang",
      "speakers": "A local erudite",
      "recorded": "1970",
      "doi": "https://doi.org/10.24397/pangloss-0002162",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-7507cc66-05cc-3c73-b5c1-b9af23e2b716&corpus=Khmu",
      "node_id": "case_sea_khmu_0002162"
    }
  ]
}
```

## 原音、转写与复核

本卡只索引一条馆藏录音，不自动判定为一篇故事；一条录音可能包含多个故事、片段、歌唱、祈祷或访谈。相似题名与分段提示须回听，不证明同一演述、母题、传播或历史事件。讲述者籍贯与具体录音地点不是同一字段；录音日期不是叙事年代，馆藏名称不保证每段都只用 Khmu 语。音视频与转写正文未复制；具体许可和相关社区要求须逐项核查。
