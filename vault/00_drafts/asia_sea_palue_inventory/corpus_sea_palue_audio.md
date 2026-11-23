---
id: corpus_sea_palue_audio
title: 印尼 Palu’e 口述资料馆藏 · 目录筛查
aliases: []
node_type: myth_corpus
z_layer: 2
genre: unclassified
credibility_tier: B
is_fictional_quarantine: false
spatial:
  lat: null
  lng: null
  precision: culture_region
  location_name: 印尼馆藏总体范围；单条采录与叙事地点待核
  culture_region: Southeast Asia · Indonesia
temporal: null
standards:
  atu_types: []
  thompson_motifs: []
  berezkin_codes: []
  ocm_codes: []
  macro_phylogeny: null
mechanisms: []
relations: []
sources:
- citation: University of Hawai‘i, Kaipuleohone 馆藏检索字段索引。
  type: palue_index
  url: https://scholarspace.manoa.hawaii.edu/server/api/discover/search/objects?scope=8e4c3ded-2f0b-44ad-98ff-6d93969f029e&sort=dc.title%2CASC&size=50&page=0
  doi: null
  locator: 目录检索页 0 / SD1-000
  local_path: .local/source-snapshots/palue-inventory-20261123/page-000.json
  content_sha256: 880c9f4034d35aebec47cb14763157bb99d39037adbe5491a97f9582c02d73a7
- citation: Palu’e 馆藏本地字段索引清单；原始响应、媒体和转写未保存。
  type: palue_manifest
  url: https://scholarspace.manoa.hawaii.edu/collections/8e4c3ded-2f0b-44ad-98ff-6d93969f029e
  doi: null
  locator: 公开检索与字段索引清单
  local_path: .local/source-snapshots/palue-inventory-20261123/manifest.json
  content_sha256: 946663d33c533ddf1a1c9a2b0bf7b955938e94475598d472fb007cc38c4f793d
audit:
  created_at: '2026-11-22'
  reviewed_by_human: false
  ai_confidence: null
  is_sample: false
  reviewer: null
  reviewed_at: null
  review_note: null
---

## 馆藏筛查字段

```
{
  "馆藏目录对象数": 353,
  "类型字段显式含 Sound": 323,
  "类型字段未列 Sound": 30,
  "计数说明": "目录对象、音频文件及独立故事不是相同单位；未列 Sound 不代表没有录音。",
  "主题语种字段计数": {
    "Sara Lio": 2,
    "Sara Lu'a": 330,
    "sara Lu'a": 21
  },
  "采集核验": "本地字段索引逐页校验；采集期间仅重复核验首页与末页。",
  "原响应哈希说明": "未保留原始响应，不能从本地字段重算原响应哈希。",
  "权利说明": "权限须逐件及按相关社区要求复核，字段为空不等于无限制。"
}
```

## 复核范围

公开目录对象混合体裁，不能将 Sound 字段或目录对象数直接当作故事数。日期与地区原字段的具体性质待核，采录时间与地点不等于叙事发生时间与地点；主题语种和内容语言须分别核实。仅保存必要目录字段，不保存叙事描述、音频或转写。权限字段为空不等于开放，请回查[馆方使用说明](https://manoa.hawaii.edu/library/research/scholarly-communication/repositories/policies-guidelines/copyright-policy/)与每条记录及相关社区要求；中间分页未重复抽验。
